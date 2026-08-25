# Model and Data Validation Contract

Kraken’s forecast bands are empirical intervals, not fixed normal-theory bands. For each horizon, the native core builds the historical distribution of all eligible horizon log returns, then reports interpolated lower, median, and upper quantiles at the requested central coverage. Each band includes the number of historical outcomes supporting the interval. A run fails when fewer than four outcomes are available for a requested horizon.

The `kraken calibration forecast` command performs chronological evaluation. At each decision point it fits the band only on observations available at that point, then evaluates the later horizon outcome. It reports nominal coverage, realized empirical coverage, observation counts, covered counts, and mean interval width. This allows users to reject a configuration whose observed coverage is materially different from its nominal target.

Regime anomaly contribution is mapped through the standard normal error function, and distance confidence uses a two-degree-of-freedom chi-square survival probability for the standardized feature distance. These transformations provide defined statistical meanings for the probability-like fields. Regime labels remain descriptive thresholds over a composite research score and must not be interpreted as investment recommendations.

Marine-dynamics values are normalized descriptive market-structure indices. They are not probability estimates, and their use requires empirical validation against a user-defined target before any research conclusion is made. The toolkit does not claim that any score predicts returns or produces a tradable edge.

## Licensed-data lineage

Authorized licensed-data acceptance requires an explicit, non-expired attestation. The attestation identifies the authorizer and license, binds to the exact vendor manifest with a SHA-256 digest, and lists an exact SHA-256 digest for every input referenced by that manifest. The acceptance report carries those hashes and the authorization metadata so downstream artifacts retain the lineage evidence.

Hash verification proves that the accepted files are the files that were reviewed. It does not grant a license, verify legal entitlement, or determine whether a vendor’s historical universe is economically complete. Those decisions remain governance responsibilities of the data owner.

## Portable build contract

The CI workflow retains the full native-quality job on Ubuntu and adds an independent wheel-build and wheel-smoke matrix for Ubuntu, macOS, and Windows using CPython 3.12. The CMake install target places the extension in the correct runtime destination for shared-library and Windows module layouts. The smoke test verifies integrity auditing, packaged vendor-plugin discovery, and provider normalization.
