import argparse
import hashlib
import re
import tarfile
import zipfile
from pathlib import Path


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_version(pyproject: Path) -> str:
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r"^version\s*=\s*\"([^\"]+)\"$", text, re.MULTILINE)
    if not match:
        raise ValueError("Unable to read project version")
    return match.group(1)


def validate_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
    if not any(name.endswith("/pyproject.toml") for name in names):
        raise ValueError("Source distribution is missing pyproject.toml")
    if not any("vendor_plugins/" in name for name in names):
        raise ValueError("Source distribution is missing vendor plugins")
    if any(name.endswith((".pyc", ".so", ".o", ".a")) or "/__pycache__/" in name for name in names):
        raise ValueError("Source distribution contains generated artifacts")


def validate_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        bad = [name for name in names if name.endswith((".pyc", ".so", ".o", ".a")) and "/_core" not in name]
        if bad:
            raise ValueError(f"Wheel contains unexpected generated artifacts: {bad}")
        if not any(name.startswith("kraken/vendor_plugins/") for name in names):
            raise ValueError("Wheel is missing vendor plugins")
        if not any(name.startswith("kraken/_core") for name in names):
            raise ValueError("Wheel is missing the native extension")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Kraken release artifacts")
    parser.add_argument("--dist", required=True)
    parser.add_argument("--pyproject", default="pyproject.toml")
    parser.add_argument("--tag")
    args = parser.parse_args()
    dist = Path(args.dist).expanduser().resolve()
    version = read_version(Path(args.pyproject).expanduser().resolve())
    if args.tag and args.tag.removeprefix("v") != version:
        raise ValueError(f"Release tag {args.tag} does not match project version {version}")
    artifacts = sorted(path for path in dist.iterdir() if path.is_file() and (path.name.endswith(".tar.gz") or path.name.endswith(".whl")))
    sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
    wheels = [path for path in artifacts if path.name.endswith(".whl")]
    if len(sdists) != 1 or not wheels:
        raise ValueError("Release must contain exactly one source distribution and at least one wheel")
    validate_sdist(sdists[0])
    for wheel in wheels:
        validate_wheel(wheel)
    checksum_path = dist / "SHA256SUMS"
    checksum_path.write_text("".join(f"{digest(path)}  {path.name}\n" for path in artifacts), encoding="utf-8")
    print(f"release-check: {version} {len(wheels)} wheels and 1 source distribution")


if __name__ == "__main__":
    main()
