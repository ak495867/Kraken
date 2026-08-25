# Kraken architecture

Kraken has a deliberately narrow architecture. The package accepts locally supplied, timestamped observations; Python validates the file schema; the C++ layer independently validates chronology and numerical invariants; and the Python layer renders structured reports and CLI output. The native layer is the authoritative implementation of feature computation and integrity gates, so a caller cannot bypass point-in-time validation by calling lower-level Python helpers.

| Layer | Responsibility | Boundary |
| --- | --- | --- |
| Input layer | Parse local CSV or JSON, normalize UTC timestamps, and reject missing or malformed fields. | Does not perform network I/O or credential handling. |
| C++ core | Validate chronology, compute sonar features, calibrate distance, classify regime risk, and construct native integrity results. | Deterministic C++17 calculations without randomness, threads, mutable global state, or remote calls. |
| Python API | Convert typed dataclasses to and from native values, attach run metadata, build fingerprints, and run walk-forward evaluations. | Preserves native exceptions and does not add trading semantics. |
| CLI | Provide `sonar track`, `regime report`, `research run`, and `integrity audit` commands in JSON or concise terminal output. | Does not accept secrets, perform orders, or access integrations. |

## Point-in-time protocol

Every observation has two time axes: `timestamp` is when the market measurement belongs, while `available_at` is when a researcher could have known it. A decision cutoff includes only observations where both values are at or before the cutoff. The core rejects all other records rather than silently filtering them, making the data boundary visible to the caller.

Walk-forward runs create a contiguous training segment, an embargo, a validation segment, a second embargo, and an evaluation segment. The decision cutoff falls before the first evaluation observation. Each window receives an independent integrity audit, and a failed availability condition rejects that window. The evaluation return is calculated only after the decision cutoff.

## Feature semantics

The Sonar Tracker converts log-price changes into multi-horizon echoes. Each echo reports return displacement, volatility-normalized signal strength, and a robust anomaly score. Forecast bands use the current mean and dispersion of eligible log returns and are marked with nominal coverage. Distance Calibration compares evaluation-window return, volatility, liquidity, and liquidity-return correlation characteristics to a historical reference distribution. The composite distance maps to uncertainty and calibration drift, then a deterministic rule maps the combined state into one of four risk labels.

The methodology is intentionally interpretable. The output exposes component distances, confidence, uncertainty, drift, input count, cutoff, feature windows, warnings, and configuration fingerprints. It does not treat the classifications as instructions to buy, sell, or hold an asset.

