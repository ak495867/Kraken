from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable, Sequence

from .analysis import DEFAULT_HORIZONS, analyze_regime_risk
from .audit import configuration_fingerprint, validate_post_cutoff_observations
from .calendar import validate_market_data_quality
from .corporate_actions import validate_corporate_action_integrity
from .distributions import validate_distribution_integrity
from .dynamics import analyze_marine_dynamics
from .earnings import validate_earnings_event_integrity
from .models import (
    CorporateAction,
    DistributionRecord,
    EarningsEvent,
    EquityOptionsBacktestReport,
    EquityOptionsBacktestWindow,
    ExchangeSession,
    MarketDataQualityPolicy,
    Observation,
    OptionContractAdjustment,
    OptionQuote,
)
from .provenance import create_run_manifest
from .vendor import FilePointInTimeVendorAdapter


def _known_chain_at_cutoff(
    quotes: tuple[OptionQuote, ...], cutoff: int, underlying: str | None
) -> tuple[OptionQuote, ...]:
    if any(
        quote.timestamp_ms <= cutoff and quote.available_at_ms > cutoff
        for quote in quotes
    ):
        raise ValueError(
            "Option input contains a quote unavailable at the decision cutoff"
        )
    known = tuple(
        quote
        for quote in quotes
        if quote.timestamp_ms <= cutoff
        and quote.available_at_ms <= cutoff
        and quote.expiration_ms > cutoff
        and (underlying is None or quote.underlying == underlying)
    )
    if not known:
        raise ValueError(
            "No eligible unexpired option quote is available at the decision cutoff"
        )
    latest_timestamp = max(quote.timestamp_ms for quote in known)
    return tuple(quote for quote in known if quote.timestamp_ms == latest_timestamp)


def _select_research_contract(
    chain: tuple[OptionQuote, ...], underlying_close: float, target_expiration_ms: int
) -> OptionQuote:
    return min(
        chain,
        key=lambda quote: (
            abs(quote.expiration_ms - target_expiration_ms),
            abs(quote.strike - underlying_close),
            -quote.open_interest,
            quote.contract,
        ),
    )


def run_equity_options_backtest(
    equity_observations: Iterable[Observation],
    option_quotes: Iterable[OptionQuote],
    train_size: int,
    validation_size: int,
    holding_size: int,
    embargo_size: int = 1,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    universe_id: str | None = None,
    survivorship_controlled: bool = False,
    corporate_actions: Iterable[CorporateAction] = (),
    option_adjustments: Iterable[OptionContractAdjustment] = (),
    distributions: Iterable[DistributionRecord] = (),
    earnings_events: Iterable[EarningsEvent] = (),
    price_basis: str = "split_adjusted",
    sector: str | None = None,
    underlying_universe: str | None = None,
    underlying: str | None = None,
    exchange_sessions: Sequence[ExchangeSession] | None = None,
    data_quality_policy: MarketDataQualityPolicy | None = None,
    halted_underlyings: Iterable[str] = (),
) -> EquityOptionsBacktestReport:
    equity = tuple(equity_observations)
    options = tuple(option_quotes)
    actions = tuple(corporate_actions)
    adjustments = tuple(option_adjustments)
    distribution_records = tuple(distributions)
    earnings_records = tuple(earnings_events)
    sessions = tuple(exchange_sessions) if exchange_sessions is not None else None
    quality_policy = data_quality_policy or MarketDataQualityPolicy()
    halted = tuple(sorted(set(halted_underlyings)))
    data_quality_warnings: list[str] = []
    if min(train_size, validation_size, holding_size) <= 0 or embargo_size < 1:
        raise ValueError(
            "train_size, validation_size, and holding_size must be positive and embargo_size must be at least one"
        )
    if any(
        options[index].timestamp_ms < options[index - 1].timestamp_ms
        for index in range(1, len(options))
    ):
        raise ValueError("Option quote timestamps must be non-decreasing")
    required = train_size + validation_size + holding_size + 2 * embargo_size
    if len(equity) < required:
        raise ValueError(
            "Equity input does not contain enough observations for one embargoed research window"
        )
    windows: list[EquityOptionsBacktestWindow] = []
    start = 0
    window_id = 1
    while start + required <= len(equity):
        train = equity[start : start + train_size]
        validation_start = start + train_size + embargo_size
        validation = equity[validation_start : validation_start + validation_size]
        evaluation_start = validation_start + validation_size + embargo_size
        evaluation = equity[evaluation_start : evaluation_start + holding_size]
        cutoff = validation[-1].available_at_ms
        history = train + validation
        evaluation = validate_post_cutoff_observations(evaluation, cutoff)
        if sessions is not None:
            quality = validate_market_data_quality(
                history, options, cutoff, sessions, quality_policy, halted
            )
            if not quality.valid:
                details = "; ".join(
                    issue.message
                    for issue in quality.issues
                    if issue.severity == "error"
                )
                raise ValueError(
                    f"Calendar and market-data quality validation failed: {details}"
                )
            data_quality_warnings.extend(quality.warnings)
            data_quality_warnings.extend(
                issue.message for issue in quality.issues if issue.severity == "warning"
            )
        corporate_integrity = validate_corporate_action_integrity(
            equity,
            options,
            actions,
            adjustments,
            cutoff,
            price_basis,
        )
        if not corporate_integrity.valid:
            details = "; ".join(issue.message for issue in corporate_integrity.issues)
            raise ValueError(f"Corporate-action integrity validation failed: {details}")
        distribution_integrity = validate_distribution_integrity(
            equity,
            distribution_records,
            cutoff,
            price_basis,
        )
        if not distribution_integrity.valid:
            details = "; ".join(
                issue.message for issue in distribution_integrity.issues
            )
            raise ValueError(f"Distribution integrity validation failed: {details}")
        earnings_integrity = validate_earnings_event_integrity(earnings_records, cutoff)
        if not earnings_integrity.valid:
            details = "; ".join(issue.message for issue in earnings_integrity.issues)
            raise ValueError(f"Earnings-event integrity validation failed: {details}")
        regime = analyze_regime_risk(
            history,
            cutoff,
            horizons=horizons,
            reference_size=len(train),
            universe_id=universe_id,
            survivorship_controlled=survivorship_controlled,
        )
        dynamics = analyze_marine_dynamics(
            history,
            cutoff,
            fast_window=min(5, max(1, validation_size // 2)),
            slow_window=min(20, len(history) - 1),
            universe_id=universe_id,
            survivorship_controlled=survivorship_controlled,
        )
        chain = _known_chain_at_cutoff(options, cutoff, underlying)
        eligible_chain = tuple(
            quote
            for quote in chain
            if quote.expiration_ms > evaluation[-1].timestamp_ms
        )
        if not eligible_chain:
            raise ValueError(
                "No eligible option quote remains unexpired through the evaluation horizon"
            )
        contract = _select_research_contract(
            eligible_chain, validation[-1].close, evaluation[-1].timestamp_ms
        )
        realized_log_return = math.log(evaluation[-1].close / validation[-1].close)
        implied_move = contract.implied_volatility * math.sqrt(
            float(holding_size) / 252.0
        )
        absolute_move_ratio = abs(realized_log_return) / max(implied_move, 1e-12)
        windows.append(
            EquityOptionsBacktestWindow(
                window_id=window_id,
                decision_cutoff_ms=cutoff,
                evaluation_start_ms=evaluation[0].timestamp_ms,
                evaluation_end_ms=evaluation[-1].timestamp_ms,
                selected_contract=contract.contract,
                selected_option_type=contract.option_type,
                selected_strike=contract.strike,
                selected_expiration_ms=contract.expiration_ms,
                quote_timestamp_ms=contract.timestamp_ms,
                implied_move=implied_move,
                realized_log_return=realized_log_return,
                absolute_move_ratio=absolute_move_ratio,
                implied_move_covered=abs(realized_log_return) <= implied_move,
                regime=regime.regime,
                composite_dynamics_risk=dynamics.composite_dynamics_risk,
                drag_adjusted_volatility=dynamics.drag.adjusted_volatility,
                tidal_current_strength=dynamics.tidal.current_strength,
                cavitation_score=dynamics.cavitation.cavitation_score,
                buoyancy_score=dynamics.buoyancy.buoyancy_score,
                integrity=regime.integrity,
            )
        )
        window_id += 1
        start += holding_size
    configuration = {
        "analysis": "equity_options_research_backtest",
        "train_size": train_size,
        "validation_size": validation_size,
        "holding_size": holding_size,
        "embargo_size": embargo_size,
        "horizons": tuple(int(item) for item in horizons),
        "universe_id": universe_id,
        "survivorship_controlled": survivorship_controlled,
        "price_basis": price_basis,
        "sector": sector,
        "underlying_universe": underlying_universe,
        "underlying": underlying,
        "distribution_count": len(distribution_records),
        "earnings_event_count": len(earnings_records),
        "exchange_calendar": (
            tuple(
                (item.session_date, item.open_ms, item.close_ms, item.is_half_day)
                for item in sessions
            )
            if sessions is not None
            else None
        ),
        "market_data_quality_policy": {
            "max_snapshot_lag_ms": quality_policy.max_snapshot_lag_ms,
            "minimum_option_strikes": quality_policy.minimum_option_strikes,
            "require_calls_and_puts": quality_policy.require_calls_and_puts,
            "strict": quality_policy.strict,
        },
        "halted_underlyings": halted,
    }
    report = EquityOptionsBacktestReport(
        configuration_fingerprint=configuration_fingerprint(configuration),
        train_size=train_size,
        validation_size=validation_size,
        holding_size=holding_size,
        embargo_size=embargo_size,
        sector=sector,
        underlying_universe=underlying_universe,
        windows=tuple(windows),
        warnings=tuple(
            dict.fromkeys(
                (
                    "This local research backtest reports forecast-band and implied-move calibration only; it does not model orders, positions, or P&L",
                    "Option quotes are admitted only when timestamp and available_at are both at or before each decision cutoff",
                    "Historical universe and survivorship controls remain user-supplied data responsibilities",
                    "Known corporate actions and option-contract split adjustments are validated at every decision cutoff",
                    "Known cash dividends and special distributions are validated at every decision cutoff",
                    "Known earnings events are validated at every decision cutoff",
                    (
                        "No explicit exchange calendar was supplied; session, stale-snapshot, halt, duplicate, and option-chain completeness controls were not evaluated"
                        if sessions is None
                        else "Exchange-calendar and market-data quality controls were evaluated at every decision cutoff"
                    ),
                    *data_quality_warnings,
                )
            )
        ),
    )
    manifest = create_run_manifest(
        configuration,
        {
            "equity_observations": equity,
            "option_quotes": options,
            "corporate_actions": actions,
            "option_adjustments": adjustments,
            "distributions": distribution_records,
            "earnings_events": earnings_records,
            "exchange_sessions": sessions,
        },
        report,
        report.windows[-1].decision_cutoff_ms if report.windows else None,
        warnings=report.warnings,
    )
    return replace(report, manifest=manifest)


def run_vendor_equity_options_backtest(
    manifest_path: str,
    train_size: int,
    validation_size: int,
    holding_size: int,
    embargo_size: int = 1,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    underlying: str | None = None,
) -> EquityOptionsBacktestReport:
    dataset = FilePointInTimeVendorAdapter(manifest_path).load()
    report = run_equity_options_backtest(
        dataset.equity,
        dataset.options,
        train_size=train_size,
        validation_size=validation_size,
        holding_size=holding_size,
        embargo_size=embargo_size,
        horizons=horizons,
        universe_id=dataset.manifest.dataset_id,
        survivorship_controlled=True,
        corporate_actions=dataset.corporate_actions,
        option_adjustments=dataset.option_adjustments,
        distributions=dataset.distributions,
        earnings_events=dataset.earnings_events,
        price_basis=dataset.manifest.price_basis,
        sector=dataset.manifest.sector,
        underlying_universe=dataset.manifest.underlying_universe,
        underlying=underlying,
    )
    manifest = create_run_manifest(
        {
            "analysis": "vendor_equity_options_research_backtest",
            "configuration_fingerprint": report.configuration_fingerprint,
        },
        {
            "equity_observations": dataset.equity,
            "option_quotes": dataset.options,
            "corporate_actions": dataset.corporate_actions,
            "option_adjustments": dataset.option_adjustments,
            "distributions": dataset.distributions,
            "earnings_events": dataset.earnings_events,
        },
        replace(report, manifest=None),
        report.windows[-1].decision_cutoff_ms if report.windows else None,
        vendor_manifest_path=manifest_path,
        warnings=report.warnings,
    )
    return replace(report, manifest=manifest)
