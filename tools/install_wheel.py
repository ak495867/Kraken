import subprocess
import sys
from pathlib import Path

wheels = sorted((Path(__file__).resolve().parents[1] / "dist").glob("*.whl"))
if not wheels:
    raise SystemExit("No wheel found in dist")
subprocess.run([sys.executable, "-m", "pip", "install", str(wheels[-1])], check=True)
