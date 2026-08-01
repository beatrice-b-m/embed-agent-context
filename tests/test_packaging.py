"""Contracts for installable entry points and bundled catalog resources."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from embed_context import __version__, default_catalog_path, load_catalog


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration = tomllib.loads(
            (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

    def test_package_cli_and_mcp_versions_share_one_release(self) -> None:
        self.assertEqual(
            self.configuration["project"]["version"],
            __version__,
        )
        self.assertEqual(
            self.configuration["project"]["requires-python"],
            ">=3.11,<3.14",
        )
        self.assertEqual(
            self.configuration["project"]["authors"],
            [{"name": "Beatrice Brown-Mulry"}],
        )
        self.assertEqual(
            self.configuration["project"]["scripts"],
            {
                "embed-context": "embed_context.cli:main",
                "embed-context-mcp": "embed_context.mcp_server:main",
            },
        )

    def test_public_metadata_points_to_project_and_dataset_documentation(
        self,
    ) -> None:
        project = self.configuration["project"]

        self.assertEqual(
            project["urls"]["Documentation"],
            "https://github.com/beatrice-b-m/"
            "embedv2-agent-context#readme",
        )
        self.assertEqual(
            project["urls"]["EMBED Documentation"],
            "https://docs.hitilab.com/datasets/embed",
        )
        self.assertIn("EMBED", project["keywords"])
        self.assertIn(
            "Intended Audience :: Science/Research",
            project["classifiers"],
        )

    def test_wheel_configuration_bundles_catalog_and_schema(self) -> None:
        force_include = self.configuration["tool"]["hatch"]["build"][
            "targets"
        ]["wheel"]["force-include"]

        self.assertEqual(
            force_include,
            {
                "catalog/catalog-set.json": (
                    "embed_context/_data/catalog-set.json"
                ),
                "catalog/catalog-set.schema.json": (
                    "embed_context/_data/catalog-set.schema.json"
                ),
                "catalog/catalog.schema.json": (
                    "embed_context/_data/catalog.schema.json"
                ),
                "catalog/semantic/catalog.json": (
                    "embed_context/_data/semantic/catalog.json"
                ),
                "catalog/semantic/catalog.schema.json": (
                    "embed_context/_data/semantic/catalog.schema.json"
                ),
                "catalog/profiles/open-v2.json": (
                    "embed_context/_data/profiles/open-v2.json"
                ),
                "catalog/profiles/profile.schema.json": (
                    "embed_context/_data/profiles/profile.schema.json"
                ),
                "catalog/extensions/extension.schema.json": (
                    "embed_context/_data/extensions/extension.schema.json"
                ),
            },
        )

    def test_every_bundled_manifest_target_is_packaged(self) -> None:
        import json

        manifest = json.loads(
            (REPOSITORY_ROOT / "catalog/catalog-set.json").read_text(
                encoding="utf-8"
            )
        )
        locators = [
            manifest["semantic_catalog"],
            *manifest["profiles"],
            *manifest["extensions"],
        ]
        force_include = self.configuration["tool"]["hatch"]["build"][
            "targets"
        ]["wheel"]["force-include"]
        for locator in locators:
            if locator["kind"] != "bundled":
                continue
            source = f"catalog/{locator['resource']}"
            with self.subTest(source=source):
                self.assertIn(source, force_include)
                self.assertTrue((REPOSITORY_ROOT / source).is_file())

    def test_jsonschema_is_a_core_dependency(self) -> None:
        self.assertIn(
            "jsonschema==4.26.0",
            self.configuration["project"]["dependencies"],
        )
        self.assertNotIn(
            "jsonschema==4.26.0",
            self.configuration["dependency-groups"]["dev"],
        )

    def test_default_catalog_is_present_and_loadable(self) -> None:
        path = default_catalog_path()

        self.assertTrue(path.is_file(), path)
        self.assertEqual(load_catalog().schema_version, 7)


if __name__ == "__main__":
    unittest.main()
