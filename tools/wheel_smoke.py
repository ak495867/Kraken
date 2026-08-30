import json
import subprocess
import sys
import tempfile
from pathlib import Path

from kraken.execution import LiveBrokerNotConfigured, OrderRequest, PaperBroker
from kraken.normalizers import available_profiles, normalize_provider_exports
from kraken.production import ProductionRuntime
from kraken.risk import load_risk_limits

root = Path(__file__).resolve().parents[1]
fixture = root / "fixtures" / "illustrative_market_data.csv"
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "kraken",
        "integrity",
        "audit",
        "--input",
        str(fixture),
        "--format",
        "json",
    ],
    check=True,
    capture_output=True,
    text=True,
)
payload = json.loads(result.stdout)
if not payload["valid"] or not payload["configuration_fingerprint"]:
    raise SystemExit("Packaged Kraken wheel did not return a valid integrity audit")
if "snapshot_v1" not in available_profiles():
    raise SystemExit(
        "Packaged Kraken wheel did not include the built-in vendor plugins"
    )
if (
    load_risk_limits(
        root / "configs" / "production_risk_limits.json"
    ).max_order_notional
    != 10000.0
):
    raise SystemExit("Packaged Kraken wheel failed risk-policy loading")
if not hasattr(ProductionRuntime, "poll_once") or not hasattr(PaperBroker, "submit"):
    raise SystemExit("Packaged Kraken wheel failed production runtime imports")
try:
    LiveBrokerNotConfigured().submit(
        OrderRequest("TEST", "buy", 1, 100, 1, "wheel-smoke")
    )
except RuntimeError:
    pass
else:
    raise SystemExit("Packaged Kraken wheel failed live-broker safety gate")
with tempfile.TemporaryDirectory() as directory:
    normalized = normalize_provider_exports(
        "snapshot_v1",
        root / "fixtures" / "illustrative_snapshot_equity.csv",
        root / "fixtures" / "illustrative_snapshot_options.csv",
        directory,
    )
    if normalized.equity_row_count <= 0 or normalized.option_row_count <= 0:
        raise SystemExit("Packaged Kraken wheel failed vendor normalization")
print("wheel-smoke: ok")
