"""Optional stdio MCP adapter for the EMBED clinical-semantic catalog.

The MCP SDK is imported lazily so importing the core package or CLI does not
require the optional dependency.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from . import catalog as _catalog


BINDING_GRAINS = tuple(_catalog.BINDING_GRAINS)
FEATURE_KINDS = tuple(_catalog.FEATURE_KINDS)
DOMAINS = tuple(_catalog.DOMAINS)
SEMANTIC_RELATIONSHIP_KINDS = tuple(
    _catalog.SEMANTIC_RELATIONSHIP_KINDS
)
TEMPORAL_KINDS = tuple(_catalog.TEMPORAL_KINDS)
AGGREGATION_STATUSES = tuple(_catalog.AGGREGATION_STATUSES)
COVERAGE_STATUSES = tuple(_catalog.COVERAGE_STATUSES)
RELATIONSHIP_BINDING_KINDS = tuple(
    sorted(_catalog.RELATIONSHIP_BINDING_KINDS)
)
DISCOVERY_KINDS = tuple(_catalog.DISCOVERY_KINDS)

DomainFilter = Literal[*DOMAINS]
DiscoveryKindFilter = Literal[*DISCOVERY_KINDS]
_RELATIONSHIP_BINDING_KIND_VALUES = tuple(sorted(RELATIONSHIP_BINDING_KINDS))
RelationshipBindingKindFilter = Literal[*_RELATIONSHIP_BINDING_KIND_VALUES]


MCP_INSTALL_HINT = (
    "MCP support requires the optional MCP dependency. "
    "Install the project's MCP extra (or install `mcp==2.0.0`)."
)


class CatalogProtocol(Protocol):
    """Clinical-semantic catalog operations exposed through MCP."""

    def discover(
        self,
        query: str,
        *,
        profile: str | None = None,
        kinds: Sequence[str] | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    def get_clinical_object(self, identifier: str) -> dict[str, Any]: ...

    def get_feature(
        self,
        identifier: str,
        *,
        include_codes: bool = False,
    ) -> dict[str, Any]: ...

    def get_semantic_relationship(self, identifier: str) -> dict[str, Any]: ...

    def get_temporal_semantic(self, identifier: str) -> dict[str, Any]: ...

    def get_aggregation(self, identifier: str) -> dict[str, Any]: ...

    def get_guardrail(self, identifier: str) -> dict[str, Any]: ...

    def get_coverage(self, identifier: str) -> dict[str, Any]: ...

    def lookup_code(
        self,
        feature_or_vocabulary: str,
        code: str,
    ) -> dict[str, Any]: ...

    def get_profile_table(self, profile: str, table: str) -> dict[str, Any]: ...

    def get_relationship_binding(self, identifier: str) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...


def _require_mcp() -> tuple[type[Any], type[Any]]:
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError(MCP_INSTALL_HINT) from exc
    return MCPServer, ToolAnnotations


def _catalog_scope_description(catalog: CatalogProtocol) -> str:
    """Describe catalog-specific profiles without implying a semantic schema."""

    profiles: set[str] = set()
    raw_profiles = getattr(catalog, "profiles", ())
    if isinstance(raw_profiles, Mapping):
        profiles.update(
            value for value in raw_profiles if isinstance(value, str)
        )
    else:
        profiles.update(
            value for value in raw_profiles if isinstance(value, str)
        )

    raw_bindings = getattr(catalog, "profile_bindings", ())
    if isinstance(raw_bindings, Mapping):
        profiles.update(
            value for value in raw_bindings if isinstance(value, str)
        )
    else:
        for binding in raw_bindings:
            profile = (
                binding.get("profile")
                if isinstance(binding, Mapping)
                else getattr(binding, "profile", None)
            )
            if isinstance(profile, str):
                profiles.add(profile)
    if not profiles:
        return ""
    return f"profiles in this catalog: {', '.join(sorted(profiles))}"


def _require_exact_tool_arguments(server: Any, tool_name: str) -> None:
    """Reject undeclared arguments in one pinned-SDK function tool."""

    tool = server._tool_manager.get_tool(tool_name)
    if tool is None:  # pragma: no cover - called immediately after registration.
        raise RuntimeError(f"MCP tool {tool_name!r} was not registered")
    argument_model = tool.fn_metadata.arg_model
    argument_model.model_config["extra"] = "forbid"
    argument_model.model_rebuild(force=True)
    tool.parameters = argument_model.model_json_schema(by_alias=True)


def build_server(catalog: CatalogProtocol) -> Any:
    """Build a read-only MCP server over an already-loaded catalog."""

    MCPServer, ToolAnnotations = _require_mcp()
    catalog_scope = _catalog_scope_description(catalog)
    discovery_filter_description = "; ".join(
        part
        for part in (
            f"entity kinds: {', '.join(DISCOVERY_KINDS)}",
            f"domains: {', '.join(DOMAINS)}",
            catalog_scope,
        )
        if part
    )
    binding_filter_description = "; ".join(
        part
        for part in (
            (
                "physical relationship kinds: "
                f"{', '.join(_RELATIONSHIP_BINDING_KIND_VALUES)}"
            ),
            "semantic_relationship: stable portable relationship ID",
            catalog_scope,
        )
        if part
    )
    semantic_scope_description = (
        "semantic relationship kinds: "
        f"{', '.join(SEMANTIC_RELATIONSHIP_KINDS)}; temporal kinds: "
        f"{', '.join(TEMPORAL_KINDS)}; aggregation statuses: "
        f"{', '.join(AGGREGATION_STATUSES)}; coverage statuses: "
        f"{', '.join(COVERAGE_STATUSES)}; binding grains: "
        f"{', '.join(BINDING_GRAINS)}; feature kinds: "
        f"{', '.join(FEATURE_KINDS)}"
    )
    server = MCPServer(
        "embed-clinical-context",
        description=(
            "Read-only clinical-semantic context for the Emory Breast Imaging "
            "Dataset, with secondary release-specific implementation bindings"
        ),
        version="0.5.0",
        instructions=(
            "Begin with discover using a clinical question. Follow exact "
            "semantic references to understand clinical objects, features, "
            "relationships, competing time meanings, aggregation behavior, "
            "guardrails, coverage, provenance, and unresolved limitations. "
            "Do not infer that absent pathology is negative, treat an imaging "
            "assessment as pathology truth, or move between finding, side, "
            "exam, and patient grain without an explicit policy. No date is a "
            "universal diagnosis date. Use secondary profile-table and physical "
            "relationship-binding tools only after selecting semantic concepts; "
            "they describe storage implementation and never execute a join. "
            "The catalog does not emit SQL, pipelines, canonical cohorts, "
            "scientific-validity claims, clinical rows, or empirical counts. "
            f"Discovery filters — {discovery_filter_description}. "
            f"Binding filters — {binding_filter_description}. "
            f"Controlled semantic facets — {semantic_scope_description}."
        ),
    )
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(
        annotations=read_only,
        structured_output=True,
        description=(
            "Search the portable clinical-semantic model using a clinical "
            "question. Results explain why they matched and distinguish filter, "
            "vocabulary, profile-support, and catalog-coverage diagnostics. "
            f"Valid filters — {discovery_filter_description}."
        ),
    )
    def discover(
        query: str,
        profile: str | None = None,
        kinds: list[DiscoveryKindFilter] | None = None,
        domain: DomainFilter | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Discover relevant semantics without knowing tables or stable IDs."""

        return catalog.discover(
            query,
            profile=profile,
            kinds=kinds,
            domain=domain,
            limit=limit,
        )

    @server.tool(annotations=read_only, structured_output=True)
    def get_clinical_object(identifier: str) -> dict[str, Any]:
        """Get one clinical object, its grain, adjacency, and limitations."""

        return catalog.get_clinical_object(identifier)

    @server.tool(annotations=read_only, structured_output=True)
    def get_feature(
        identifier: str,
        include_codes: bool = False,
    ) -> dict[str, Any]:
        """Get one semantic feature and optional complete vocabulary code map."""

        return catalog.get_feature(identifier, include_codes=include_codes)

    @server.tool(annotations=read_only, structured_output=True)
    def get_semantic_relationship(identifier: str) -> dict[str, Any]:
        """Get a storage-independent clinical relationship and attribution limits."""

        return catalog.get_semantic_relationship(identifier)

    @server.tool(annotations=read_only, structured_output=True)
    def get_temporal_semantic(identifier: str) -> dict[str, Any]:
        """Get what a candidate event, documentation, or availability time means."""

        return catalog.get_temporal_semantic(identifier)

    @server.tool(annotations=read_only, structured_output=True)
    def get_aggregation(identifier: str) -> dict[str, Any]:
        """Get supplied or unresolved behavior across clinical grains."""

        return catalog.get_aggregation(identifier)

    @server.tool(annotations=read_only, structured_output=True)
    def get_guardrail(identifier: str) -> dict[str, Any]:
        """Get one reusable interpretation constraint, not a workflow recipe."""

        return catalog.get_guardrail(identifier)

    @server.tool(annotations=read_only, structured_output=True)
    def get_coverage(identifier: str) -> dict[str, Any]:
        """Get a supported, unsupported, unresolved, or uncataloged scope record."""

        return catalog.get_coverage(identifier)

    @server.tool(annotations=read_only, structured_output=True)
    def lookup_code(feature_or_vocabulary: str, code: str) -> dict[str, Any]:
        """Look up one exact code without interpreting missing values as negative."""

        return catalog.lookup_code(feature_or_vocabulary, code)

    @server.tool(annotations=read_only, structured_output=True)
    def get_profile_table(profile: str, table: str) -> dict[str, Any]:
        """Get one secondary profile-specific table implementation binding."""

        return catalog.get_profile_table(profile, table)

    @server.tool(annotations=read_only, structured_output=True)
    def get_relationship_binding(identifier: str) -> dict[str, Any]:
        """Get one secondary physical relationship binding by stable identifier."""

        return catalog.get_relationship_binding(identifier)

    @server.tool(
        annotations=read_only,
        structured_output=True,
        description=(
            "Filter secondary physical relationship bindings by profile and "
            "endpoint table. These are descriptive storage mappings, not "
            f"clinical relationships or executable joins. Valid filters — "
            f"{binding_filter_description}."
        ),
    )
    def search_relationship_bindings(
        profile: str | None = None,
        table: str | None = None,
        source_table: str | None = None,
        target_table: str | None = None,
        kind: RelationshipBindingKindFilter | None = None,
        semantic_relationship: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Filter physical relationship bindings without executing joins."""

        return catalog.search_relationship_bindings(
            profile=profile,
            table=table,
            source_table=source_table,
            target_table=target_table,
            kind=kind,
            semantic_relationship=semantic_relationship,
            limit=limit,
        )

    for tool_name in (
        "discover",
        "get_clinical_object",
        "get_feature",
        "get_semantic_relationship",
        "get_temporal_semantic",
        "get_aggregation",
        "get_guardrail",
        "get_coverage",
        "lookup_code",
        "get_profile_table",
        "get_relationship_binding",
        "search_relationship_bindings",
    ):
        _require_exact_tool_arguments(server, tool_name)
    return server


def _load_catalog(path: Path | None) -> CatalogProtocol:
    try:
        return _catalog.load_catalog(path)
    except _catalog.CatalogError as exc:
        raise RuntimeError(str(exc)) from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Run the read-only MCP server over stdio."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        help="catalog JSON path; defaults to the project's bundled catalog",
    )
    args = parser.parse_args(argv)
    try:
        _require_mcp()
        catalog = _load_catalog(args.catalog)
        server = build_server(catalog)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"MCP server error: {exc}", file=sys.stderr)
        return 2
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
