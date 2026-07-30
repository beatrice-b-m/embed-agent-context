"""Focused contract tests for the schema-v5 MCP adapter."""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any
from unittest.mock import Mock, patch

from embed_context import __version__
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
    profiles = ("open-v2",)

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def discover(
        self,
        query: str,
        *,
        profile: str | None = None,
        kinds: list[str] | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        arguments = {
            "query": query,
            "profile": profile,
            "kinds": kinds,
            "domain": domain,
            "limit": limit,
        }
        self.calls.append(("discover", arguments))
        return {
            "query": query,
            "filters": {
                "profile": profile,
                "kinds": kinds,
                "domain": domain,
            },
            "count": 1,
            "total": 1,
            "matches": [
                {
                    "kind": "guardrail",
                    "identifier": "pathology.null-not-negative",
                    "score": 12,
                    "label": "Null is not negative",
                    "entity": {"id": "pathology.null-not-negative"},
                    "match_reasons": [
                        {"field": "label", "terms": ["negative"]}
                    ],
                    "matched_terms": ["negative"],
                    "unmatched_terms": [],
                }
            ],
            "diagnostics": {
                "filters_excluded_matches": False,
                "unknown_filter_or_vocabulary_value": [],
                "unsupported_in_profile": [],
                "no_catalog_coverage": False,
            },
        }

    def get_clinical_object(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_clinical_object",
            identifier,
            "clinical_object",
        )

    def get_feature(
        self,
        identifier: str,
        *,
        include_codes: bool = False,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_feature",
                {"identifier": identifier, "include_codes": include_codes},
            )
        )
        return {
            "kind": "feature",
            "identifier": identifier,
            "feature": {"id": identifier},
            "codes_included": include_codes,
        }

    def get_semantic_relationship(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_semantic_relationship",
            identifier,
            "semantic_relationship",
        )

    def get_temporal_semantic(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_temporal_semantic",
            identifier,
            "temporal_semantic",
        )

    def get_aggregation(self, identifier: str) -> dict[str, Any]:
        return self._exact("get_aggregation", identifier, "aggregation")

    def get_guardrail(self, identifier: str) -> dict[str, Any]:
        return self._exact("get_guardrail", identifier, "guardrail")

    def get_coverage(self, identifier: str) -> dict[str, Any]:
        return self._exact("get_coverage", identifier, "coverage")

    def get_context(self, identifier: str) -> dict[str, Any]:
        return self._exact("get_context", identifier, "context")

    def lookup_code(
        self,
        feature_or_vocabulary: str,
        code: str,
    ) -> dict[str, Any]:
        arguments = {
            "feature_or_vocabulary": feature_or_vocabulary,
            "code": code,
        }
        self.calls.append(("lookup_code", arguments))
        return {
            **arguments,
            "meaning": "Synthetic meaning",
        }

    def get_profile_table(self, profile: str, table: str) -> dict[str, Any]:
        arguments = {"profile": profile, "table": table}
        self.calls.append(("get_profile_table", arguments))
        return {
            "kind": "profile_table",
            "identifier": f"{profile}:{table}",
            "table": {"id": table},
        }

    def get_relationship_binding(self, identifier: str) -> dict[str, Any]:
        return self._exact(
            "get_relationship_binding",
            identifier,
            "relationship_binding",
        )

    def search_relationship_bindings(
        self,
        *,
        profile: str | None = None,
        table: str | None = None,
        source_table: str | None = None,
        target_table: str | None = None,
        kind: str | None = None,
        semantic_relationship: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        arguments = {
            "profile": profile,
            "table": table,
            "source_table": source_table,
            "target_table": target_table,
            "kind": kind,
            "semantic_relationship": semantic_relationship,
            "limit": limit,
        }
        self.calls.append(("search_relationship_bindings", arguments))
        return {
            "filters": {
                key: value for key, value in arguments.items() if key != "limit"
            },
            "count": 1,
            "total": 1,
            "matches": [{"id": "synthetic.binding"}],
        }

    def _exact(
        self,
        method: str,
        identifier: str,
        key: str,
    ) -> dict[str, Any]:
        self.calls.append((method, {"identifier": identifier}))
        return {
            "kind": key,
            "identifier": identifier,
            key: {"id": identifier},
        }


class RelationshipBindingKindSchemaStabilityTests(unittest.TestCase):
    def test_kind_order_does_not_depend_on_python_hash_seed(self) -> None:
        script = (
            "from typing import get_args; "
            "from embed_context.mcp_server import RelationshipBindingKindFilter; "
            "print(','.join(get_args(RelationshipBindingKindFilter)))"
        )
        orders = set()
        for seed in ("1", "2", "3"):
            environment = dict(os.environ)
            environment["PYTHONHASHSEED"] = seed
            completed = subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                capture_output=True,
                env=environment,
                text=True,
            )
            orders.add(completed.stdout.strip())

        self.assertEqual(orders, {"hierarchy,projection,reference"})


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
    def test_version_uses_package_version(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            main(("--version",))

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(
            stdout.getvalue().strip(),
            f"embed-context-mcp {__version__}",
        )

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

    def test_server_metadata_is_clinical_semantic_first(self) -> None:
        self.assertEqual(self.server.version, __version__)
        self.assertIn("clinical-semantic context", self.server.description)
        self.assertIn("Begin with discover", self.server.instructions)
        self.assertIn("Use get_context", self.server.instructions)
        self.assertIn("No date is a universal diagnosis date", self.server.instructions)
        self.assertIn(
            "longitudinal pathology candidates across the patient timeline",
            self.server.instructions,
        )
        self.assertIn(
            "must not be forced equal to the index accession",
            self.server.instructions,
        )
        self.assertIn(
            "must not be coalesced or fallback-substituted",
            self.server.instructions,
        )
        self.assertIn(
            "separately named endpoints or sensitivity analyses",
            self.server.instructions,
        )
        self.assertIn(
            "unsuitable for probability-calibration metrics until validated",
            self.server.instructions,
        )
        self.assertIn("secondary", self.server.instructions)
        self.assertNotIn("analysis patterns", self.server.instructions.lower())

    async def test_lists_only_read_only_closed_input_schema_tools(self) -> None:
        async with Client(self.server) as client:
            result = await client.list_tools()

        expected_properties = {
            "discover": {"query", "profile", "kinds", "domain", "limit"},
            "get_clinical_object": {"identifier"},
            "get_feature": {"identifier", "include_codes"},
            "get_semantic_relationship": {"identifier"},
            "get_temporal_semantic": {"identifier"},
            "get_aggregation": {"identifier"},
            "get_guardrail": {"identifier"},
            "get_coverage": {"identifier"},
            "get_context": {"identifier"},
            "lookup_code": {"feature_or_vocabulary", "code"},
            "get_profile_table": {"profile", "table"},
            "get_relationship_binding": {"identifier"},
            "search_relationship_bindings": {
                "profile",
                "table",
                "source_table",
                "target_table",
                "kind",
                "semantic_relationship",
                "limit",
            },
        }
        self.assertEqual(
            {tool.name for tool in result.tools},
            set(expected_properties),
        )
        for tool in result.tools:
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertTrue(tool.annotations.idempotent_hint)
            self.assertFalse(tool.annotations.open_world_hint)
            self.assertIsNotNone(tool.output_schema)
            self.assertEqual(
                set(tool.input_schema["properties"]),
                expected_properties[tool.name],
            )
            self.assertIs(tool.input_schema["additionalProperties"], False)

        schemas = {tool.name: tool.input_schema for tool in result.tools}
        discover_properties = schemas["discover"]["properties"]
        self.assertEqual(
            schema_enums(discover_properties["kinds"]),
            {
                "clinical_object",
                "feature",
                "semantic_relationship",
                "temporal_semantic",
                "aggregation",
                "guardrail",
                "coverage",
                "context",
            },
        )
        self.assertIn(
            "pathology",
            schema_enums(discover_properties["domain"]),
        )
        binding_kind = schemas["search_relationship_bindings"]["properties"][
            "kind"
        ]
        self.assertEqual(
            schema_enums(binding_kind),
            {"hierarchy", "projection", "reference"},
        )

    async def test_discover_returns_core_result_unchanged(self) -> None:
        arguments = {
            "query": "negative pathology",
            "profile": "open-v2",
            "kinds": ["guardrail", "coverage"],
            "domain": "pathology",
            "limit": 3,
        }
        async with Client(self.server) as client:
            result = await client.call_tool("discover", arguments)

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["count"], 1)
        self.assertEqual(
            result.structured_content["matches"][0]["match_reasons"],
            [{"field": "label", "terms": ["negative"]}],
        )
        self.assertEqual(
            self.catalog.calls,
            [("discover", arguments)],
        )

    async def test_exact_semantic_tools_dispatch_without_reinterpretation(self) -> None:
        cases = (
            ("get_clinical_object", "imaging_finding"),
            ("get_semantic_relationship", "finding.pathology"),
            ("get_temporal_semantic", "pathology.report_date"),
            ("get_aggregation", "pathology.exam_severity"),
            ("get_guardrail", "pathology.null-not-negative"),
            ("get_coverage", "pathology.specimen_time"),
            ("get_context", "open-v2.pathology-workflow"),
        )
        async with Client(self.server) as client:
            for tool_name, identifier in cases:
                result = await client.call_tool(
                    tool_name,
                    {"identifier": identifier},
                )
                self.assertFalse(result.is_error)
                self.assertEqual(
                    result.structured_content["identifier"],
                    identifier,
                )

        self.assertEqual(
            self.catalog.calls,
            [
                (tool_name, {"identifier": identifier})
                for tool_name, identifier in cases
            ],
        )

    async def test_feature_and_code_tools_preserve_explicit_arguments(self) -> None:
        async with Client(self.server) as client:
            feature = await client.call_tool(
                "get_feature",
                {
                    "identifier": "pathology.severity",
                    "include_codes": True,
                },
            )
            code = await client.call_tool(
                "lookup_code",
                {
                    "feature_or_vocabulary": "pathology-severity",
                    "code": "MiXeD,Value",
                },
            )

        self.assertFalse(feature.is_error)
        self.assertTrue(feature.structured_content["codes_included"])
        self.assertFalse(code.is_error)
        self.assertEqual(code.structured_content["code"], "MiXeD,Value")
        self.assertEqual(
            self.catalog.calls,
            [
                (
                    "get_feature",
                    {
                        "identifier": "pathology.severity",
                        "include_codes": True,
                    },
                ),
                (
                    "lookup_code",
                    {
                        "feature_or_vocabulary": "pathology-severity",
                        "code": "MiXeD,Value",
                    },
                ),
            ],
        )

    async def test_profile_binding_tools_are_explicit_and_secondary(self) -> None:
        arguments = {
            "profile": "open-v2",
            "table": "exam_level_anon",
            "source_table": "exam_level_anon",
            "target_table": "clinical_data_anon",
            "kind": "hierarchy",
            "semantic_relationship": "clinical.exam-patient",
            "limit": 3,
        }
        async with Client(self.server) as client:
            table = await client.call_tool(
                "get_profile_table",
                {"profile": "open-v2", "table": "exam_level_anon"},
            )
            binding = await client.call_tool(
                "get_relationship_binding",
                {"identifier": "exam.patient"},
            )
            bindings = await client.call_tool(
                "search_relationship_bindings",
                arguments,
            )
            tools = await client.list_tools()

        self.assertFalse(table.is_error)
        self.assertFalse(binding.is_error)
        self.assertFalse(bindings.is_error)
        self.assertEqual(bindings.structured_content["count"], 1)
        descriptions = {tool.name: tool.description for tool in tools.tools}
        self.assertIn(
            "patient-timeline traversal",
            descriptions["get_semantic_relationship"],
        )
        self.assertIn(
            "not necessarily the index exam",
            descriptions["get_semantic_relationship"],
        )
        self.assertIn(
            "Never coalesce or fallback-substitute",
            descriptions["get_temporal_semantic"],
        )
        self.assertIn(
            "separately named endpoints and sensitivity analyses",
            descriptions["get_temporal_semantic"],
        )
        self.assertIn(
            "do not support probability-calibration metrics until validated",
            descriptions["get_feature"],
        )
        self.assertIn(
            "preclude probability-calibration metrics until validated",
            descriptions["get_coverage"],
        )
        self.assertIn("secondary", descriptions["get_profile_table"])
        self.assertIn(
            "not clinical relationships or executable joins",
            descriptions["search_relationship_bindings"],
        )
        self.assertIn(
            "do not force a candidate pathology accession to equal the index "
            "accession",
            descriptions["search_relationship_bindings"],
        )
        self.assertEqual(
            self.catalog.calls,
            [
                (
                    "get_profile_table",
                    {"profile": "open-v2", "table": "exam_level_anon"},
                ),
                (
                    "get_relationship_binding",
                    {"identifier": "exam.patient"},
                ),
                ("search_relationship_bindings", arguments),
            ],
        )

    async def test_invalid_controlled_filters_are_schema_errors(self) -> None:
        async with Client(self.server) as client:
            invalid_discovery_kind = await client.call_tool(
                "discover",
                {"query": "pathology", "kinds": ["table"]},
            )
            invalid_domain = await client.call_tool(
                "discover",
                {"query": "pathology", "domain": "cohort"},
            )
            invalid_binding_kind = await client.call_tool(
                "search_relationship_bindings",
                {"kind": "foreign_key"},
            )

        self.assertTrue(invalid_discovery_kind.is_error)
        self.assertTrue(invalid_domain.is_error)
        self.assertTrue(invalid_binding_kind.is_error)
        self.assertEqual(self.catalog.calls, [])

    async def test_unknown_arguments_are_schema_errors_for_every_surface(self) -> None:
        async with Client(self.server) as client:
            discovery = await client.call_tool(
                "discover",
                {"query": "pathology", "table": "pathology_findings_anon"},
            )
            getter = await client.call_tool(
                "get_guardrail",
                {"identifier": "guardrail", "include_sources": True},
            )
            binding = await client.call_tool(
                "search_relationship_bindings",
                {"sourceTable": "exam_level_anon"},
            )

        self.assertTrue(discovery.is_error)
        self.assertTrue(getter.is_error)
        self.assertTrue(binding.is_error)
        self.assertEqual(self.catalog.calls, [])


if __name__ == "__main__":
    unittest.main()
