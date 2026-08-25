import json
import tempfile
import unittest
from pathlib import Path

from kraken.normalizers import discover_vendor_plugins, load_vendor_plugin, normalize_provider_exports


ROOT = Path(__file__).resolve().parents[1]


class VendorPluginTests(unittest.TestCase):
    def test_builtin_plugins_are_versioned_and_provenanced(self):
        plugins = discover_vendor_plugins()
        self.assertEqual({(item.provider, item.version) for item in plugins}, {("canonical", "1.0.0"), ("snapshot_v1", "1.0.0")})
        for plugin in plugins:
            self.assertEqual(len(plugin.sha256), 64)
            self.assertTrue(Path(plugin.contract_path).is_file())

    def test_plugin_backed_normalization_records_version_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            report = normalize_provider_exports(
                "snapshot_v1",
                ROOT / "fixtures" / "illustrative_snapshot_equity.csv",
                ROOT / "fixtures" / "illustrative_snapshot_options.csv",
                directory,
            )
            plugin = load_vendor_plugin("snapshot_v1")
            self.assertEqual(report.plugin_version, "1.0.0")
            self.assertEqual(report.plugin_sha256, plugin.sha256)
            self.assertEqual(report.contract_path, plugin.contract_path)

    def test_plugin_discovery_rejects_missing_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "provider" / "1.0.0" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"provider": "provider", "version": "1.0.0", "schema": "kraken_vendor_mapping_plugin/v1", "mapping": load_vendor_plugin("canonical").mapping}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture contract is missing"):
                discover_vendor_plugins(directory)


if __name__ == "__main__":
    unittest.main()
