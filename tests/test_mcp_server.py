"""Focused contract tests for the optional MCP adapter."""

from __future__ import annotations

import importlib.util
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any
from unittest.mock import Mock, patch

from embed_context import load_catalog
from embed_context.mcp_server import MCP_INSTALL_HINT, build_server, main


MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None

if MCP_AVAILABLE:
    from mcp import Client


def schema_enums(value: object) -> set[str]:
    if isinstance(value, dict):
        direct = value.get("enum", ())
        return {
            item for item in direct if isinstance(item, str)
        } | set().union(*(schema_enums(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(schema_enums(item) for item in value))
    return set()


class FakeCatalog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_feature(
        self, identifier: str, *, include_codes: bool = False
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_feature",
                {"identifier": identifier, "include_codes": include_codes},
            )
        )
        return {
            "identifier": identifier,
            "meaning": "Synthetic feature",
            "codes_included": include_codes,
        }

    def search_features(
        self,
        query: str,
        *,
        profile: str | None = None,
        table: str | None = None,
        grain: str | None = None,
        domain: str | None = None,
        feature_kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "search_features",
                {
                    "query": query,
                    "profile": profile,
                    "table": table,
                    "grain": grain,
                    "domain": domain,
                    "feature_kind": feature_kind,
                    "limit": limit,
                },
            )
        )
        return {
            "matches": [
                {
                    "name": "synthetic_table.synthetic_column",
                    "meaning": "Synthetic match",
                }
            ],
            "count": 1,
        }

    def lookup_code(
        self, feature_or_vocabulary: str, code: str
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "lookup_code",
                {
                    "feature_or_vocabulary": feature_or_vocabulary,
                    "code": code,
                },
            )
        )
        return {
            "feature_or_vocabulary": feature_or_vocabulary,
            "code": code,
            "meaning": "Synthetic code",
        }


class MissingMCPDependencyTests(unittest.TestCase):
    def test_module_entry_point_reports_missing_extra_on_stderr(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "embed_context.mcp_server._require_mcp",
                side_effect=RuntimeError(MCP_INSTALL_HINT),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = main([])

        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("optional MCP dependency", stderr.getvalue())

    @unittest.skipIf(MCP_AVAILABLE, "MCP SDK is installed")
    def test_build_server_explains_how_to_enable_mcp(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "optional MCP dependency"):
            build_server(FakeCatalog())
        self.assertIn("mcp==2.0.0", MCP_INSTALL_HINT)


class ModuleEntryPointTests(unittest.TestCase):
    def test_main_runs_the_built_server_over_stdio(self) -> None:
        catalog = FakeCatalog()
        server = Mock()
        with (
            patch(
                "embed_context.mcp_server._require_mcp",
                return_value=(Mock, Mock),
            ),
            patch(
                "embed_context.mcp_server._load_catalog",
                return_value=catalog,
            ) as load_catalog,
            patch(
                "embed_context.mcp_server.build_server",
                return_value=server,
            ) as build_server_mock,
        ):
            result = main([])

        self.assertEqual(result, 0)
        load_catalog.assert_called_once_with(None)
        build_server_mock.assert_called_once_with(catalog)
        server.run.assert_called_once_with(transport="stdio")


@unittest.skipUnless(MCP_AVAILABLE, "optional MCP SDK is not installed")
class MCPServerContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.catalog = FakeCatalog()
        self.server = build_server(self.catalog)

    async def test_lists_only_read_only_closed_world_tools(self) -> None:
        async with Client(self.server) as client:
            result = await client.list_tools()

        self.assertEqual(
            {tool.name for tool in result.tools},
            {"get_feature", "search_features", "lookup_code"},
        )
        for tool in result.tools:
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertTrue(tool.annotations.idempotent_hint)
            self.assertFalse(tool.annotations.open_world_hint)
            self.assertIsNotNone(tool.output_schema)
        schemas = {tool.name: tool.input_schema for tool in result.tools}
        self.assertEqual(
            set(schemas["get_feature"]["properties"]),
            {"identifier", "include_codes"},
        )
        self.assertEqual(
            set(schemas["search_features"]["properties"]),
            {
                "query",
                "profile",
                "table",
                "grain",
                "domain",
                "feature_kind",
                "limit",
            },
        )
        self.assertEqual(
            set(schemas["lookup_code"]["properties"]),
            {"feature_or_vocabulary", "code"},
        )
        search_properties = schemas["search_features"]["properties"]
        self.assertIn("pathology_finding", schema_enums(search_properties["grain"]))
        self.assertIn(
            "social_determinants_of_health",
            schema_enums(search_properties["domain"]),
        )
        self.assertIn(
            "model_output",
            schema_enums(search_properties["feature_kind"]),
        )

    async def test_get_feature_returns_structured_content(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool(
                "get_feature",
                {
                    "identifier": "synthetic_table.synthetic_column",
                    "include_codes": True,
                },
            )

        self.assertFalse(result.is_error)
        self.assertEqual(
            result.structured_content,
            {
                "identifier": "synthetic_table.synthetic_column",
                "meaning": "Synthetic feature",
                "codes_included": True,
            },
        )
        self.assertEqual(
            self.catalog.calls,
            [
                (
                    "get_feature",
                    {
                        "identifier": "synthetic_table.synthetic_column",
                        "include_codes": True,
                    },
                )
            ],
        )

    async def test_search_returns_core_result_unchanged(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool(
                "search_features",
                {
                    "query": "",
                    "profile": "open-v2",
                    "table": "synthetic_table",
                    "grain": "exam",
                    "domain": "demographics",
                    "feature_kind": "categorical",
                    "limit": 3,
                },
            )

        self.assertFalse(result.is_error)
        self.assertEqual(
            result.structured_content,
            {
                "matches": [
                    {
                        "name": "synthetic_table.synthetic_column",
                        "meaning": "Synthetic match",
                    }
                ],
                "count": 1,
            },
        )
        self.assertEqual(
            self.catalog.calls[-1],
            (
                "search_features",
                {
                    "query": "",
                    "profile": "open-v2",
                    "table": "synthetic_table",
                    "grain": "exam",
                    "domain": "demographics",
                    "feature_kind": "categorical",
                    "limit": 3,
                },
            ),
        )

    async def test_lookup_code_preserves_exact_code(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool(
                "lookup_code",
                {
                    "feature_or_vocabulary": "synthetic_vocabulary",
                    "code": "MiXeD,Value",
                },
            )

        self.assertFalse(result.is_error)
        self.assertEqual(
            result.structured_content,
            {
                "feature_or_vocabulary": "synthetic_vocabulary",
                "code": "MiXeD,Value",
                "meaning": "Synthetic code",
            },
        )

    async def test_invalid_limit_from_core_is_a_tool_error(self) -> None:
        server = build_server(load_catalog())
        async with Client(server) as client:
            result = await client.call_tool(
                "search_features",
                {"query": "density", "limit": 501},
            )

        self.assertTrue(result.is_error)

    async def test_invalid_controlled_filter_is_a_schema_error(self) -> None:
        async with Client(self.server) as client:
            result = await client.call_tool(
                "search_features",
                {"query": "density", "grain": "not-a-grain"},
            )

        self.assertTrue(result.is_error)
        self.assertEqual(self.catalog.calls, [])

    async def test_empty_query_without_filters_is_a_tool_error(self) -> None:
        server = build_server(load_catalog())
        async with Client(server) as client:
            result = await client.call_tool("search_features", {})

        self.assertTrue(result.is_error)


@unittest.skipUnless(MCP_AVAILABLE, "optional MCP SDK is not installed")
class MCPRealCatalogIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_tool_describes_catalog_specific_filters(self) -> None:
        server = build_server(load_catalog())
        async with Client(server) as client:
            result = await client.list_tools()

        search = next(
            tool for tool in result.tools if tool.name == "search_features"
        )
        self.assertIn("profiles in this catalog: open-v2", search.description)
        self.assertIn("tables in this catalog:", search.description)
        self.assertIn("pathology_findings_anon", search.description)

    async def test_all_tools_query_the_checked_in_catalog(self) -> None:
        server = build_server(load_catalog())
        async with Client(server) as client:
            feature = await client.call_tool(
                "get_feature",
                {"identifier": "exam.accession_identifier"},
            )
            search = await client.call_tool(
                "search_features",
                {"domain": "social_determinants_of_health"},
            )
            code = await client.call_tool(
                "lookup_code",
                {
                    "feature_or_vocabulary": "imaging.assessment",
                    "code": "N",
                },
            )

        self.assertFalse(feature.is_error)
        self.assertEqual(
            feature.structured_content["concept"]["id"],
            "exam.accession_identifier",
        )
        self.assertFalse(search.is_error)
        identifiers = [
            match["identifier"]
            for match in search.structured_content["matches"]
        ]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertIn("demographics.race", identifiers)
        self.assertFalse(code.is_error)
        self.assertEqual(code.structured_content["meaning"], "Negative")


if __name__ == "__main__":
    unittest.main()
