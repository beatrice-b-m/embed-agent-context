"""Focused contract and real-catalog tests for the composable MCP adapter."""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any
from unittest.mock import Mock, patch
from pathlib import Path

from embed_context import __version__, load_catalog
from embed_context.mcp_server import MCP_INSTALL_HINT, build_server, main
from tests.test_cli import _outdated_module_arguments


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
        profile: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_feature",
                {
                    "identifier": identifier,
                    "include_codes": include_codes,
                    "profile": profile,
                },
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
        *,
        profile: str | None = None,
    ) -> dict[str, Any]:
        arguments = {
            "feature_or_vocabulary": feature_or_vocabulary,
            "code": code,
            "profile": profile,
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
        self.assertIn(
            "git+https://github.com/beatrice-b-m/"
            "embedv2-agent-context.git",
            MCP_INSTALL_HINT,
        )


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

    def test_help_requires_schema_v8_modules(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            main(("--help",))

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("schema-v8 catalog-set manifest", stdout.getvalue())
        self.assertIn("outdated modules are fatal", stdout.getvalue())

    def test_outdated_modules_fail_before_server_construction(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            cases = _outdated_module_arguments(Path(raw_directory))
            for kind, cli_arguments in cases:
                arguments = tuple(
                    value for value in cli_arguments if value != "validate"
                )
                stdout = io.StringIO()
                stderr = io.StringIO()
                with (
                    self.subTest(kind=kind),
                    patch(
                        "embed_context.mcp_server._require_mcp",
                        return_value=(Mock, Mock),
                    ),
                    patch("embed_context.mcp_server.build_server") as dispatch,
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    status = main(arguments)

                self.assertEqual(status, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("MCP server error:", stderr.getvalue())
                dispatch.assert_not_called()

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
        load_catalog.assert_called_once_with(
            None,
            profile_paths=(),
            extension_paths=(),
            include_default_profiles=True,
            include_default_extensions=False,
        )
        build_server_mock.assert_called_once_with(catalog)
        server.run.assert_called_once_with(transport="stdio")

    def test_main_forwards_repeatable_module_selection_options(self) -> None:
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
            ),
        ):
            result = main(
                (
                    "--catalog", "set.json",
                    "--profile-file", "v1.json",
                    "--profile-file", "v2.json",
                    "--extension-file", "project.json",
                    "--no-default-profiles",
                    "--include-default-extensions",
                )
            )

        self.assertEqual(result, 0)
        load_catalog.assert_called_once()
        positional, keywords = load_catalog.call_args
        self.assertEqual(str(positional[0]), "set.json")
        self.assertEqual(tuple(map(str, keywords["profile_paths"])), ("v1.json", "v2.json"))
        self.assertEqual(tuple(map(str, keywords["extension_paths"])), ("project.json",))
        self.assertFalse(keywords["include_default_profiles"])
        self.assertTrue(keywords["include_default_extensions"])


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
            "get_feature": {"identifier", "include_codes", "profile"},
            "get_semantic_relationship": {"identifier"},
            "get_temporal_semantic": {"identifier"},
            "get_aggregation": {"identifier"},
            "get_guardrail": {"identifier"},
            "get_coverage": {"identifier"},
            "get_context": {"identifier"},
            "lookup_code": {"feature_or_vocabulary", "code", "profile"},
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
                    "profile": "open-v2",
                },
            )
            code = await client.call_tool(
                "lookup_code",
                {
                    "feature_or_vocabulary": "pathology-severity",
                    "code": "MiXeD,Value",
                    "profile": "open-v2",
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
                        "profile": "open-v2",
                    },
                ),
                (
                    "lookup_code",
                    {
                        "feature_or_vocabulary": "pathology-severity",
                        "code": "MiXeD,Value",
                        "profile": "open-v2",
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


@unittest.skipUnless(MCP_AVAILABLE, "optional MCP SDK is not installed")
class MCPServerRealCatalogRegressionTests(unittest.IsolatedAsyncioTestCase):
    """Exercise reviewed discovery and exact-getter flows through MCP."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()
        cls.server = build_server(cls.catalog)

    @staticmethod
    def constraint_ids(
        result: dict[str, Any],
        category: str,
    ) -> set[str]:
        return {
            str(entry.get("id", entry.get("identifier")))
            for entry in result["constraints"][category]
            if entry.get("id") or entry.get("identifier")
        }

    async def test_canonical_review_prompts_preserve_core_discovery(
        self,
    ) -> None:
        cases = (
            (
                "nearest subsequent ipsilateral cancer",
                {
                    "guardrail.longitudinal-search-is-patient-scoped": 5,
                    "clinical.patient-pathology-observation": 8,
                },
            ),
            (
                "most recent prior cancer",
                {
                    "guardrail.longitudinal-search-is-patient-scoped": 5,
                    "clinical.patient-pathology-observation": 8,
                },
            ),
            (
                "procedure report exam fallback coalesce",
                {
                    "guardrail.timestamps-answer-different-questions": 4,
                    "coverage.open-v2.downstream-availability-time": 8,
                },
            ),
            (
                "risk probability calibration Brier score",
                {
                    "guardrail.risk-probability-readiness": 4,
                    (
                        "coverage.open-v2."
                        "risk-probability-calibration-readiness"
                    ): 6,
                },
            ),
            (
                "one row per finding finding key",
                {"imaging.finding_number": 4},
            ),
            (
                "laterality null side bside",
                {
                    "breast.side": 6,
                    "pathology.biopsy_side": 6,
                    "clinical.side-finding": 8,
                },
            ),
            (
                "finding pathology severity aggregate",
                {
                    "aggregation.pathology-severity-to-finding": 4,
                    "guardrail.explicit-attribution-policy": 8,
                },
            ),
            (
                "represented binary cancer endpoint",
                {
                    "guardrail.incomplete-outcome-capture": 4,
                    "coverage.open-v2.outcome-capture": 8,
                },
            ),
        )
        async with Client(self.server) as client:
            for query, expected_windows in cases:
                with self.subTest(query=query):
                    arguments = {
                        "query": query,
                        "profile": "open-v2",
                        "limit": 8,
                    }
                    result = await client.call_tool("discover", arguments)
                    direct = self.catalog.discover(
                        query,
                        profile="open-v2",
                        limit=8,
                    )

                    self.assertFalse(result.is_error)
                    self.assertEqual(result.structured_content, direct)
                    identifiers = [
                        match["identifier"]
                        for match in result.structured_content["matches"]
                    ]
                    for identifier, window in expected_windows.items():
                        self.assertIn(
                            identifier,
                            identifiers[:window],
                            f"{identifier!r} was not in the top {window}: "
                            f"{identifiers}",
                        )

        longitudinal = self.catalog.discover(
            "most recent prior cancer",
            profile="open-v2",
            limit=8,
        )
        longitudinal_ids = [
            match["identifier"] for match in longitudinal["matches"]
        ]
        self.assertLess(
            longitudinal_ids.index(
                "guardrail.longitudinal-search-is-patient-scoped"
            ),
            longitudinal_ids.index(
                "clinical.patient-pathology-observation"
            ),
        )
        fallback = self.catalog.discover(
            "procedure report exam fallback coalesce",
            profile="open-v2",
            limit=8,
        )
        fallback_ids = [match["identifier"] for match in fallback["matches"]]
        for temporal_identifier in (
            "time.procedure-event",
            "time.pathology-report-documentation",
        ):
            self.assertLess(
                fallback_ids.index(
                    "guardrail.timestamps-answer-different-questions"
                ),
                fallback_ids.index(temporal_identifier),
            )

    async def test_real_exact_getters_preserve_structured_constraints(
        self,
    ) -> None:
        exact_cases = (
            (
                "get_semantic_relationship",
                "clinical.patient-pathology-observation",
                self.catalog.get_semantic_relationship,
            ),
            (
                "get_clinical_object",
                "imaging_finding",
                self.catalog.get_clinical_object,
            ),
            (
                "get_feature",
                "risk.ibis_ten_year",
                self.catalog.get_feature,
            ),
            (
                "get_feature",
                "open-v2:imaging_findings_anon.side",
                self.catalog.get_feature,
            ),
            (
                "get_feature",
                "open-v2:pathology_findings_anon.bside",
                self.catalog.get_feature,
            ),
            (
                "get_aggregation",
                "aggregation.pathology-severity-to-finding",
                self.catalog.get_aggregation,
            ),
            (
                "get_guardrail",
                "guardrail.incomplete-outcome-capture",
                self.catalog.get_guardrail,
            ),
        )
        responses: dict[str, dict[str, Any]] = {}
        async with Client(self.server) as client:
            for tool_name, identifier, getter in exact_cases:
                with self.subTest(tool=tool_name, identifier=identifier):
                    result = await client.call_tool(
                        tool_name,
                        {"identifier": identifier},
                    )
                    direct = getter(identifier)
                    self.assertFalse(result.is_error)
                    self.assertEqual(result.structured_content, direct)
                    responses[identifier] = result.structured_content

        relationship = responses["clinical.patient-pathology-observation"]
        paths = relationship["related"]["relationship_binding_paths"]
        self.assertTrue(
            any(
                path["relationship_bindings"]
                == [
                    "open-v2.pathology_findings_anon.exam",
                    "open-v2.exam_level_anon.patient",
                ]
                for path in paths
            )
        )
        self.assertIn(
            "guardrail.longitudinal-search-is-patient-scoped",
            self.constraint_ids(
                relationship,
                "high_priority_guardrails",
            ),
        )

        finding = responses["imaging_finding"]
        identities = [
            binding["instance_identity"]
            for binding in finding["related"]["object_bindings"]
            if binding.get("instance_identity")
        ]
        self.assertTrue(
            any(
                identity["columns"] == ["acc_anon", "numfind"]
                and identity["rows_per_instance"] == "one_or_more"
                and identity["longitudinal_identity"] is False
                and any(
                    exception["representation"] == "-9"
                    for exception in identity["reserved_exceptions"]
                )
                for identity in identities
            )
        )

        risk = responses["risk.ibis_ten_year"]
        self.assertIn(
            "coverage.open-v2.risk-probability-calibration-readiness",
            self.constraint_ids(risk, "unresolved_claims"),
        )
        self.assertIn(
            "guardrail.risk-probability-readiness",
            self.constraint_ids(risk, "high_priority_guardrails"),
        )

        finding_side = responses[
            "open-v2:imaging_findings_anon.side"
        ]["binding"]["occurrence_interpretations"]
        biopsy_side = responses[
            "open-v2:pathology_findings_anon.bside"
        ]["binding"]["occurrence_interpretations"]
        self.assertTrue(
            any(
                item["representation"] == "null"
                and "bilateral" in item["meaning"].lower()
                for item in finding_side
            )
        )
        self.assertTrue(
            any(
                item["representation"] == "null"
                and "unknown" in item["meaning"].lower()
                and "not bilateral" in item["meaning"].lower()
                for item in biopsy_side
            )
        )

        aggregation = responses[
            "aggregation.pathology-severity-to-finding"
        ]
        self.assertEqual(
            aggregation["aggregation"]["status"],
            "analyst_defined",
        )
        self.assertIn(
            "aggregation.pathology-severity-to-finding",
            self.constraint_ids(
                aggregation,
                "analyst_choices_required",
            ),
        )

        endpoint = responses["guardrail.incomplete-outcome-capture"]
        statement = endpoint["guardrail"]["statement"]
        self.assertIn("no represented biopsy or cancer event", statement)
        self.assertIn("must not be interpreted as never biopsied", statement)


if __name__ == "__main__":
    unittest.main()
