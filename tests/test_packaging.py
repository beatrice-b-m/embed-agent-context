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
            force_include["catalog/catalog.json"],
            "embed_context/_data/catalog.json",
        )
        self.assertEqual(
            force_include["catalog/catalog.schema.json"],
            "embed_context/_data/catalog.schema.json",
        )

    def test_default_catalog_is_present_and_loadable(self) -> None:
        path = default_catalog_path()

        self.assertTrue(path.is_file(), path)
        self.assertEqual(load_catalog().schema_version, 6)


if __name__ == "__main__":
    unittest.main()
