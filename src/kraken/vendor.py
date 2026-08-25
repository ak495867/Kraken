from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .io import load_corporate_actions, load_distributions, load_earnings_events, load_observations, load_option_adjustments, load_option_quotes, load_vendor_manifest
from .models import CorporateAction, DistributionRecord, EarningsEvent, LicensedVendorManifest, Observation, OptionContractAdjustment, OptionQuote


@dataclass(frozen=True)
class LicensedPointInTimeDataset:
    manifest: LicensedVendorManifest
    equity: tuple[Observation, ...]
    options: tuple[OptionQuote, ...]
    corporate_actions: tuple[CorporateAction, ...]
    option_adjustments: tuple[OptionContractAdjustment, ...]
    distributions: tuple[DistributionRecord, ...]
    earnings_events: tuple[EarningsEvent, ...]


class PointInTimeVendorAdapter(Protocol):
    def load(self) -> LicensedPointInTimeDataset:
        raise NotImplementedError


class FilePointInTimeVendorAdapter:
    def __init__(self, manifest_path: str | Path):
        self._manifest_path = Path(manifest_path)

    def load(self) -> LicensedPointInTimeDataset:
        manifest = load_vendor_manifest(self._manifest_path)
        if manifest.mapping_path:
            from .normalizers import load_mapping_file

            mapping_name, _ = load_mapping_file(manifest.mapping_path)
            if manifest.normalizer_profile and mapping_name != manifest.normalizer_profile:
                raise ValueError("Vendor manifest normalizer_profile does not match the referenced mapping file name")
        equity = load_observations(manifest.equity_path)
        options = load_option_quotes(manifest.options_path)
        corporate_actions = load_corporate_actions(manifest.corporate_actions_path) if manifest.corporate_actions_path else ()
        option_adjustments = load_option_adjustments(manifest.option_adjustments_path) if manifest.option_adjustments_path else ()
        distributions = load_distributions(manifest.distributions_path) if manifest.distributions_path else ()
        earnings_events = load_earnings_events(manifest.earnings_path) if manifest.earnings_path else ()
        if equity[-1].timestamp_ms > manifest.snapshot_as_of_ms or options[-1].timestamp_ms > manifest.snapshot_as_of_ms:
            raise ValueError("Vendor manifest snapshot_as_of predates the supplied data")
        return LicensedPointInTimeDataset(manifest, equity, options, corporate_actions, option_adjustments, distributions, earnings_events)
