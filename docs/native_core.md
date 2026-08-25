# Kraken Native Core

Kraken’s native extension is intentionally decomposed into focused deterministic C++17 modules. The pybind11 layer exposes the same public functions while the numerical and integrity responsibilities live in smaller units with explicit dependencies.

| Component | Responsibility |
| --- | --- |
| `cpp/numeric.cpp` | Stable scalar statistics, empirical quantiles, clamping, correlation, and finite-value checks. |
| `cpp/validation.cpp` | Point-in-time bar validation, chronology checks, and eligible-history filtering. |
| `cpp/features.cpp` | Return, volatility, liquidity, and correlation feature extraction. |
| `cpp/sonar.cpp` | Multi-horizon echoes, anomaly signals, and empirical forecast bands. |
| `cpp/calibration.cpp` | Regime-distance calibration, reference-fit probability, confidence, and drift. |
| `cpp/regime.cpp` | Deterministic stable, transitional, stressed, and dislocated classification. |
| `cpp/dynamics.cpp` | Hydrodynamic drag, tidal current, cavitation, buoyancy, and composite dynamics risk. |
| `cpp/instrumentation.cpp` | Deterministic temporary-buffer and copied-`Bar` workload metrics. |
| `cpp/bindings.cpp` | Typed pybind11 boundary only; it does not reimplement financial logic. |

All public computations continue to validate full supplied input at the native boundary. Future timestamps, unavailable observations, non-monotonic chronology, invalid market values, and insufficient history remain rejection conditions rather than silent exclusions.

The CMake target compiles every module with C++17 and deterministic floating-point settings. On non-MSVC toolchains, contraction is disabled through `-ffp-contract=off`; MSVC uses strict floating-point settings. Forecast bands are computed from historical horizon-return quantiles and expose their supporting sample count. Regime confidence is derived from a two-degree-of-freedom chi-square reference-fit probability. The package remains research-only: these modules produce tracking, forecast-band, calibration, and risk context, not trade instructions.

## Native Tests and Benchmarks

Configure the native project with CTest enabled to compile `kraken_native_tests`. The executable checks availability leakage rejection, sonar determinism, calibration and regime bounds, marine-dynamics bounds, versioned configuration roundtrips, and zero copied-`Bar` history metrics for sonar, dynamics, calibration, and regime composition.

```bash
cmake -S . -B build/native -DBUILD_TESTING=ON
cmake --build build/native
ctest --test-dir build/native --output-on-failure
```

Enable `KRAKEN_BUILD_BENCHMARKS` to build the deterministic large-history benchmark. It uses generated in-memory observations solely to measure native sonar, marine dynamics, calibration, and regime functions; it does not analyze real markets or claim production performance.

```bash
cmake -S . -B build/native -DBUILD_TESTING=ON -DKRAKEN_BUILD_BENCHMARKS=ON
cmake --build build/native
build/native/kraken_large_history_benchmark 200000 3 9
```

The benchmark prints `benchmark,observations,iterations,samples,p50_ms,p95_ms,checksum,compiler,input_bar_copy_count,input_bar_copy_bytes,temporary_double_buffer_count,temporary_double_buffer_bytes` CSV rows. The checksum detects an accidentally unused result without turning a timing run into a financial result. The copied-`Bar` metrics are expected to remain zero; temporary double-buffer metrics make feature-memory changes reviewable rather than invisible.

## Empirical Forecast Calibration

The Python `calibrate_forecast_bands` API and `kraken calibration forecast` command replay chronological decisions. Each band is fitted only on the history available at its decision cutoff and is evaluated against later observations. The resulting report includes nominal coverage, empirical coverage, covered and total outcomes, and mean interval width.

## Versioned Research Configuration

The native `ResearchConfig` contract is versioned through `schema_version`. Version 2 owns sonar horizons, native minimum-history requirements, liquidity and drag parameters, tidal windows, `calibration_decay`, and `forecast_coverage`. It uses a strict line-based `key=value` representation with no unknown keys, no duplicate keys, and no implicit defaults during parsing.

The example at [`configs/research_config.v2.kcfg`](../configs/research_config.v2.kcfg) roundtrips through `parse_research_config` and `serialize_research_config`. Legacy v1 documents are parsed, deterministically migrated to v2 defaults of `calibration_decay=0.25` and `forecast_coverage=0.90`, then serialized only as v2. Unsupported versions, unknown keys, duplicate keys, and invalid new fields are rejected. `compute_sonar_with_config`, `calibrate_distance_with_config`, `classify_regime_with_config`, and `compute_marine_dynamics_with_config` consume the same validated v2 contract.

## Performance Regression Policy

The large-history benchmark includes compiler identity, p50 and p95 samples, checksum, and explicit buffer metrics in each CSV result. `tools/compare_benchmarks.py` compares matching workload rows, requires an equal deterministic checksum, rejects copied-`Bar` history above policy limits, reports percentile deltas, and exits nonzero when a workload-specific threshold is exceeded. The CI policy at [`ci/performance_thresholds.json`](../ci/performance_thresholds.json) keeps same-compiler enforcement while defining p50, p95, and copied-history limits per workload.

For cross-compiler research, set `require_matching_compiler` to `false` in a separate policy file. The comparison report retains both compiler labels and checksums, so an engineering review can compare compiler versions without pretending that distinct compiler environments establish a CI regression gate.

```bash
python tools/compare_benchmarks.py \
  --baseline benchmarks/baseline_gcc13_linux.csv \
  --candidate build/native/benchmark.csv \
  --policy ci/performance_thresholds.json \
  --output build/native/performance_comparison.json
```
