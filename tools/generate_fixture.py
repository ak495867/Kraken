import json
from datetime import datetime, timedelta, timezone
from math import sin
from pathlib import Path


fixtures = Path(__file__).resolve().parents[1] / "fixtures"
destination = fixtures / "illustrative_market_data.csv"
option_destination = fixtures / "illustrative_option_quotes.csv"
action_destination = fixtures / "illustrative_corporate_actions.csv"
adjustment_destination = fixtures / "illustrative_option_adjustments.csv"
distribution_destination = fixtures / "illustrative_distributions.csv"
earnings_destination = fixtures / "illustrative_earnings_events.csv"
manifest_destination = fixtures / "illustrative_vendor_manifest.json"
snapshot_equity_destination = fixtures / "illustrative_snapshot_equity.csv"
snapshot_options_destination = fixtures / "illustrative_snapshot_options.csv"
fixtures.mkdir(parents=True, exist_ok=True)
start = datetime(2025, 1, 2, tzinfo=timezone.utc)
rows = ["timestamp,available_at,close,volume,realized_volatility,liquidity"]
option_rows = ["timestamp,available_at,expiration,contract,option_type,strike,bid,ask,implied_volatility,open_interest,volume,underlying"]
snapshot_equity_rows = ["event_time,published_at,settle,shares,rv_20d,notional_liquidity"]
snapshot_option_rows = ["event_time,published_at,expiry,symbol,right,exercise_price,best_bid,best_ask,iv,open_int,contracts,root"]
for index in range(96):
    timestamp = start + timedelta(days=index)
    close = 100.0 + 0.22 * index + 1.3 * sin(index / 5.0)
    volume = 1_000_000.0 + 12_500.0 * index + 50_000.0 * sin(index / 7.0)
    volatility = 0.012 + 0.002 * abs(sin(index / 9.0))
    liquidity = 2_500_000.0 + 35_000.0 * index + 70_000.0 * sin(index / 6.0)
    iso = timestamp.isoformat().replace("+00:00", "Z")
    rows.append(f"{iso},{iso},{close:.8f},{volume:.8f},{volatility:.8f},{liquidity:.8f}")
    snapshot_equity_rows.append(f"{iso},{iso},{close:.8f},{volume:.8f},{volatility:.8f},{liquidity:.8f}")
    expiration = (timestamp + timedelta(days=45)).isoformat().replace("+00:00", "Z")
    strike = round(close, 2)
    implied_volatility = 0.18 + 0.03 * abs(sin(index / 8.0))
    bid = 2.0 + 0.01 * index
    ask = bid + 0.15
    open_interest = 500.0 + 8.0 * index
    option_volume = 100.0 + 3.0 * index
    option_rows.append(f"{iso},{iso},{expiration},ILLUS{index:03d}C,call,{strike:.2f},{bid:.6f},{ask:.6f},{implied_volatility:.8f},{open_interest:.2f},{option_volume:.2f},ILLUS")
    option_rows.append(f"{iso},{iso},{expiration},ILLUS{index:03d}P,put,{strike:.2f},{bid:.6f},{ask:.6f},{implied_volatility:.8f},{open_interest:.2f},{option_volume:.2f},ILLUS")
    snapshot_option_rows.append(f"{iso},{iso},{expiration},ILLUS{index:03d}C,call,{strike:.2f},{bid:.6f},{ask:.6f},{implied_volatility:.8f},{open_interest:.2f},{option_volume:.2f},ILLUS")
    snapshot_option_rows.append(f"{iso},{iso},{expiration},ILLUS{index:03d}P,put,{strike:.2f},{bid:.6f},{ask:.6f},{implied_volatility:.8f},{open_interest:.2f},{option_volume:.2f},ILLUS")
destination.write_text("\n".join(rows) + "\n", encoding="utf-8")
option_destination.write_text("\n".join(option_rows) + "\n", encoding="utf-8")
snapshot_equity_destination.write_text("\n".join(snapshot_equity_rows) + "\n", encoding="utf-8")
snapshot_options_destination.write_text("\n".join(snapshot_option_rows) + "\n", encoding="utf-8")
effective = start + timedelta(days=40)
available = start + timedelta(days=39)
effective_iso = effective.isoformat().replace("+00:00", "Z")
available_iso = available.isoformat().replace("+00:00", "Z")
action_destination.write_text(
    "effective_at,available_at,underlying,action_type,factor\n"
    f"{effective_iso},{available_iso},ILLUS,stock_split,2.0\n",
    encoding="utf-8",
)
adjustment_destination.write_text(
    "effective_at,available_at,underlying,pre_contract,post_contract,strike_factor,multiplier_factor\n"
    f"{effective_iso},{available_iso},ILLUS,ILLUS039C,ILLUS040C,0.5,2.0\n",
    encoding="utf-8",
)
distribution_destination.write_text(
    "effective_at,available_at,underlying,distribution_type,amount\n"
    f"{(start + timedelta(days=60)).isoformat().replace('+00:00', 'Z')},{(start + timedelta(days=59)).isoformat().replace('+00:00', 'Z')},ILLUS,cash_dividend,0.50\n"
    f"{(start + timedelta(days=70)).isoformat().replace('+00:00', 'Z')},{(start + timedelta(days=69)).isoformat().replace('+00:00', 'Z')},ILLUS,special_distribution,1.00\n",
    encoding="utf-8",
)
earnings_destination.write_text(
    "event_at,available_at,underlying,fiscal_period,event_type\n"
    f"{(start + timedelta(days=50)).isoformat().replace('+00:00', 'Z')},{(start + timedelta(days=50)).isoformat().replace('+00:00', 'Z')},ILLUS,2025Q1,earnings_release\n"
    f"{(start + timedelta(days=75)).isoformat().replace('+00:00', 'Z')},{(start + timedelta(days=75)).isoformat().replace('+00:00', 'Z')},ILLUS,2025Q2,guidance_update\n",
    encoding="utf-8",
)
snapshot = (start + timedelta(days=95)).isoformat().replace("+00:00", "Z")
manifest_destination.write_text(
    json.dumps(
        {
            "provider": "Illustrative Licensed Export",
            "dataset_id": "illustrative-pit-equity-options",
            "snapshot_as_of": snapshot,
            "price_basis": "split_adjusted",
            "equity_path": "illustrative_market_data.csv",
            "options_path": "illustrative_option_quotes.csv",
            "corporate_actions_path": "illustrative_corporate_actions.csv",
            "option_adjustments_path": "illustrative_option_adjustments.csv",
            "distributions_path": "illustrative_distributions.csv",
            "earnings_path": "illustrative_earnings_events.csv",
            "sector": "Illustrative Sector",
            "underlying_universe": "Illustrative Universe",
            "normalizer_profile": "licensed_snapshot_v1",
            "mapping_path": "../vendor_mappings/licensed_snapshot_v1.json",
        },
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)
