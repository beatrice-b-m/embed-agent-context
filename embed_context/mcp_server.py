"""Optional stdio MCP adapter for the EMBED V2 feature catalog.

The MCP SDK is imported lazily so importing the core package or CLI does not
require the optional dependency.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from .catalog import DOMAINS, FEATURE_KINDS, GRAINS, RELATIONSHIP_KINDS


GrainFilter = Literal[*GRAINS]
DomainFilter = Literal[*DOMAINS]
FeatureKindFilter = Literal[*FEATURE_KINDS]
RelationshipKindFilter = Literal[*RELATIONSHIP_KINDS]


MCP_INSTALL_HINT = (
    "MCP support requires the optional MCP dependency. "
    "Install the project's MCP extra (or install `mcp==2.0.0`)."
)


class CatalogProtocol(Protocol):
    """Catalog operations exposed through the protocol adapter."""

    def get_table(self, profile: str, table: str) -> dict[str, Any]: ...

    def get_relationship(self, identifier: str) -> dict[str, Any]: ...

    def search_relationships(
        self,
        *,
        profile: str | None = None,
        table: str | None = None,
        source_table: str | None = None,
        target_table: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...

    def get_feature(
        self, identifier: str, *, include_codes: bool = False
    ) -> dict[str, Any]: ...

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
    ) -> dict[str, Any]: ...

    def lookup_code(
        self, feature_or_vocabulary: str, code: str
    ) -> dict[str, Any]: ...


def _require_mcp() -> tuple[type[Any], type[Any]]:
    try:
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError(MCP_INSTALL_HINT) from exc
    return MCPServer, ToolAnnotations


def _catalog_filter_description(catalog: CatalogProtocol) -> str:
    """Describe controlled and catalog-specific filters without another tool."""

    parts = [
        f"grains: {', '.join(GRAINS)}",
        f"domains: {', '.join(DOMAINS)}",
        f"feature kinds: {', '.join(FEATURE_KINDS)}",
    ]
    profiles = sorted(
        {
            value
            for value in getattr(catalog, "profiles", ())
            if isinstance(value, str)
        }
    )
    if profiles:
        parts.append(f"profiles in this catalog: {', '.join(profiles)}")

    tables: set[str] = set()
    for binding in getattr(catalog, "bindings", ()):
        table = (
            binding.get("table")
            if isinstance(binding, Mapping)
            else getattr(binding, "table", None)
        )
        if isinstance(table, str):
            tables.add(table)
    if tables:
        parts.append(f"tables in this catalog: {', '.join(sorted(tables))}")
    return "; ".join(parts)


def build_server(catalog: CatalogProtocol) -> Any:
    """Build an MCP server over an already-loaded catalog.

    Accepting the catalog as a dependency keeps protocol tests in memory and
    leaves catalog loading and validation in the core package.
    """

    MCPServer, ToolAnnotations = _require_mcp()
    filter_description = _catalog_filter_description(catalog)
    server = MCPServer(
        "embed-v2-feature-context",
        description="Read-only EMBED V2 feature and table-linkage metadata lookup",
        version="0.2.0",
        instructions=(
            "Use these read-only tools for EMBED V2 feature meanings, table "
            "linkages, evidence, caveats, join hazards, and coded values. "
            "Relationships are descriptive metadata, not executable joins; honor "
            "their documented optionality, cardinality, and hazards. The catalog "
            "does not provide clinical rows, report text, or clinical advice. "
            f"Search filters — {filter_description}."
        ),
    )
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(annotations=read_only, structured_output=True)
    def get_feature(identifier: str, include_codes: bool = False) -> dict[str, Any]:
        """Get one concept ID or physical table-column feature alias."""

        return catalog.get_feature(identifier, include_codes=include_codes)

    @server.tool(
        annotations=read_only,
        structured_output=True,
        description=(
            "Search features by text and/or controlled facets. Valid filters — "
            f"{filter_description}."
        ),
    )
    def search_features(
        query: str = "",
        profile: str | None = None,
        table: str | None = None,
        grain: GrainFilter | None = None,
        domain: DomainFilter | None = None,
        feature_kind: FeatureKindFilter | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search features by text and/or profile, table, grain, domain, and kind."""

        return catalog.search_features(
            query,
            profile=profile,
            table=table,
            grain=grain,
            domain=domain,
            feature_kind=feature_kind,
            limit=limit,
        )

    @server.tool(annotations=read_only, structured_output=True)
    def lookup_code(feature_or_vocabulary: str, code: str) -> dict[str, Any]:
        """Look up a code using a vocabulary ID, concept ID, or physical feature."""

        return catalog.lookup_code(feature_or_vocabulary, code)

    @server.tool(annotations=read_only, structured_output=True)
    def get_table(profile: str, table: str) -> dict[str, Any]:
        """Get one profile-specific table, its keys, and incident relationships."""

        return catalog.get_table(profile, table)

    @server.tool(annotations=read_only, structured_output=True)
    def get_relationship(identifier: str) -> dict[str, Any]:
        """Get one table relationship by its stable identifier."""

        return catalog.get_relationship(identifier)

    @server.tool(
        annotations=read_only,
        structured_output=True,
        description=(
            "Filter table relationships by profile, either endpoint table, "
            "directional endpoint table, and/or relationship kind. Valid "
            f"relationship kinds: {', '.join(sorted(RELATIONSHIP_KINDS))}; "
            f"catalog filters — {filter_description}."
        ),
    )
    def search_relationships(
        profile: str | None = None,
        table: str | None = None,
        source_table: str | None = None,
        target_table: str | None = None,
        kind: RelationshipKindFilter | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Filter structured table relationships without executing joins."""

        return catalog.search_relationships(
            profile=profile,
            table=table,
            source_table=source_table,
            target_table=target_table,
            kind=kind,
            limit=limit,
        )

    return server


def _load_catalog(path: Path | None) -> CatalogProtocol:
    try:
        from .catalog import CatalogError, load_catalog
    except ImportError as exc:
        raise RuntimeError(
            "The core catalog loader is unavailable; install the complete project."
        ) from exc
    try:
        return load_catalog(path)
    except CatalogError as exc:
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
