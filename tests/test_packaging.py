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
        cls.curator_configuration = tomllib.loads(
            (REPOSITORY_ROOT / "packages/curator/pyproject.toml").read_text(
                encoding="utf-8"
            )
        )

    def test_package_entry_points_share_one_release(self) -> None:
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
            "embed-agent-context#readme",
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
                "catalog/internal-v2-catalog-set.json": (
                    "embed_context/_data/internal-v2-catalog-set.json"
                ),
                "catalog/catalog-set.schema.json": (
                    "embed_context/_data/catalog-set.schema.json"
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
                "catalog/profiles/internal-v2.json": (
                    "embed_context/_data/profiles/internal-v2.json"
                ),
                "catalog/profiles/profile.schema.json": (
                    "embed_context/_data/profiles/profile.schema.json"
                ),
                "catalog/extensions/extension.schema.json": (
                    "embed_context/_data/extensions/extension.schema.json"
                ),
            },
        )

    def test_curator_is_an_optional_companion_distribution(self) -> None:
        optional = self.configuration["project"]["optional-dependencies"]

        self.assertEqual(
            optional["curator"],
            ["embedv2-agent-context-curator==0.10.0"],
        )
        self.assertEqual(
            self.configuration["tool"]["uv"]["sources"][
                "embedv2-agent-context-curator"
            ],
            {"workspace": True},
        )
        self.assertEqual(
            self.configuration["tool"]["uv"]["workspace"]["members"],
            ["packages/curator"],
        )

    def test_curator_companion_is_versioned_with_the_core(self) -> None:
        curator = self.curator_configuration

        self.assertEqual(curator["project"]["version"], __version__)
        self.assertEqual(
            curator["project"]["dependencies"],
            [f"embedv2-agent-context=={__version__}"],
        )
        self.assertEqual(
            curator["tool"]["hatch"]["build"]["targets"]["wheel"][
                "packages"
            ],
            ["src/embed_context_curator"],
        )
        self.assertEqual(curator["project"]["license-files"], ["LICENSE"])
        self.assertEqual(
            (REPOSITORY_ROOT / "packages/curator/LICENSE").read_text(),
            (REPOSITORY_ROOT / "LICENSE").read_text(),
        )

    def test_base_wheel_does_not_force_include_curator_assets(self) -> None:
        force_include = self.configuration["tool"]["hatch"]["build"][
            "targets"
        ]["wheel"]["force-include"]
        for name in ("index.html", "app.js", "styles.css"):
            source = f"embed_context/curator/static/{name}"
            with self.subTest(source=source):
                self.assertNotIn(source, force_include)

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
        self.assertEqual(load_catalog().schema_version, 8)


if __name__ == "__main__":
    unittest.main()
