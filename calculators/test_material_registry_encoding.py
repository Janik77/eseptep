"""The registry must not depend on Windows ANSI locale defaults."""
import runpy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


class MaterialRegistryEncodingTests(TestCase):
    def test_registry_loads_with_explicit_utf8_under_non_utf8_default(self):
        module = Path(__file__).with_name("material_keys.py")
        original = Path.read_text
        reads = []

        def read_with_ansi_default(path, *args, **kwargs):
            if path.name == "material_registry.json":
                reads.append(kwargs.get("encoding"))
                if not kwargs.get("encoding"):
                    return path.read_bytes().decode("cp1251")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read_with_ansi_default):
            loaded = runpy.run_path(str(module))
        self.assertEqual(reads, ["utf-8"])
        self.assertTrue(loaded["REGISTRY"])
        self.assertEqual(len(loaded["BY_KEY"]), len(loaded["REGISTRY"]))
        for row in loaded["REGISTRY"]:
            self.assertEqual(loaded["material_key"](row["name"], row["unit"]), row["key"])
