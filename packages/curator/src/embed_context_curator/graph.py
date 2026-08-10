"""Deterministic typed connection graph for the local curator.

The graph is derived from an already validated effective :class:`Catalog`.
It never reads source files and never mutates catalog records.  Authored-source
metadata which is not retained by ``Catalog`` (editability and draft state) is
accepted as a small overlay keyed by canonical ``kind:id`` node keys.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Mapping

from embed_context.catalog import Catalog, ContributionOrigin


_SEMANTIC_COLLECTIONS = {
    "clinical_object": "clinical_objects",
    "concept": "concepts",
    "semantic_relationship": "semantic_relationships",
    "temporal_semantic": "temporal_semantics",
    "aggregation": "aggregations",
    "guardrail": "guardrails",
    "coverage": "coverage",
    "vocabulary": "vocabularies",
    "source": "sources",
    "context": "contexts",
}

_BINDING_COLLECTIONS = {
    "feature_binding": "feature_bindings",
    "object_binding": "object_bindings",
    "table": "tables",
    "relationship_binding": "relationship_bindings",
    "relationship_binding_path": "relationship_binding_paths",
}


def _physical_column_id(table_id: str, column_name: str) -> str:
    return f"{table_id}::{column_name}"

_AUTHORED_REFERENCE_FIELDS = {
    "feature": (
        ("objects", "clinical_object", "owned_by", True),
        ("temporal_semantics", "temporal_semantic", "has_time_semantic", True),
        ("aggregations", "aggregation", "has_aggregation", True),
        ("vocabulary", "vocabulary", "uses_vocabulary", False),
    ),
    "clinical_object": (),
    "semantic_relationship": (
        ("source_object", "clinical_object", "source_object", False),
        ("target_object", "clinical_object", "target_object", False),
        ("temporal_semantics", "temporal_semantic", "has_time_semantic", True),
    ),
    "temporal_semantic": (
        ("objects", "clinical_object", "applies_to_object", True),
        ("feature_refs", "concept", "represented_by_concept", True),
        ("relative_to", "temporal_semantic", "relative_to", True),
    ),
    "aggregation": (
        ("source_object", "clinical_object", "source_object", False),
        ("target_object", "clinical_object", "target_object", False),
        ("source_concept", "concept", "source_concept", False),
        ("result_concept", "concept", "result_concept", False),
        ("semantic_relationships", "semantic_relationship", "uses_relationship", True),
    ),
    "guardrail": (
        ("objects", "clinical_object", "guards_object", True),
        ("concepts", "concept", "guards_concept", True),
        ("semantic_relationships", "semantic_relationship", "guards_relationship", True),
        ("temporal_semantics", "temporal_semantic", "guards_time_semantic", True),
        ("aggregations", "aggregation", "guards_aggregation", True),
        ("coverage", "coverage", "guards_coverage", True),
    ),
    "feature_binding": (
        ("concept", "concept", "binds_concept", False),
        ("vocabulary", "vocabulary", "uses_vocabulary", False),
    ),
    "object_binding": (("object", "clinical_object", "binds_object", False),),
    "relationship_binding": (
        ("semantic_relationships", "semantic_relationship", "implements_relationship", True),
    ),
    "relationship_binding_path": (
        ("semantic_relationship", "semantic_relationship", "implements_relationship", False),
        ("relationship_bindings", "relationship_binding", "path_step", True),
    ),
    "feature_lineage": (
        ("output_concept", "concept", "output_concept", False),
        ("input_concepts", "concept", "input_concept", True),
        ("input_bindings", "feature_binding", "input_binding", True),
    ),
}


def node_key(kind: str, identifier: str) -> str:
    """Return the canonical graph key for an effective contribution."""

    return f"{kind}:{identifier}"


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True, slots=True)
class GraphNode:
    key: str
    identifier: str
    label: str
    kind: str
    origin: Mapping[str, Any] | None
    profile: str | None
    lifecycle: str | None
    editable: bool
    draft_state: str
    missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    type: str
    direction: str
    source_pointer: str
    source_contribution: str
    origin: Mapping[str, Any] | None
    draft_state: str
    error: bool = False
    diagnostics: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["diagnostics"] = list(self.diagnostics)
        return result


@dataclass(frozen=True, slots=True)
class AuthoredGraphRecord:
    """An editable authored contribution overlaid on the effective graph."""

    kind: str
    identifier: str
    record: Mapping[str, Any] | None
    source_pointer: str
    origin: Mapping[str, Any] | None
    profile: str | None
    lifecycle: str | None
    draft_state: str


class GraphIndex:
    """An immutable, deterministically ordered graph derived from a catalog."""

    def __init__(
        self,
        catalog: Catalog,
        *,
        editable_keys: Iterable[str] = (),
        draft_states: Mapping[str, str] | None = None,
        authored_overlay: Iterable[AuthoredGraphRecord] = (),
        diagnostics: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        self._catalog = catalog
        self._editable = frozenset(editable_keys)
        self._draft_states = dict(draft_states or {})
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
        self._nodes = nodes
        self._edges_build = edges
        self._build_nodes()
        self._build_edges()
        overlay = tuple(authored_overlay)
        if overlay:
            self._apply_authored_overlay(overlay, tuple(diagnostics))
        unique_edges = {
            (edge.source, edge.target, edge.type, edge.source_pointer): edge
            for edge in edges
        }
        self._edges = tuple(
            unique_edges[key] for key in sorted(unique_edges)
        )
        self._ordered_nodes = tuple(nodes[key] for key in sorted(nodes))
        del self._edges_build

    @property
    def nodes(self) -> tuple[GraphNode, ...]:
        return self._ordered_nodes

    @property
    def edges(self) -> tuple[GraphEdge, ...]:
        return self._edges

    def get_node(self, kind: str, identifier: str) -> GraphNode | None:
        return self._nodes.get(node_key(kind, identifier))

    def incoming(self, kind: str, identifier: str) -> tuple[GraphEdge, ...]:
        key = node_key(kind, identifier)
        return tuple(edge for edge in self._edges if edge.target == key)

    def outgoing(self, kind: str, identifier: str) -> tuple[GraphEdge, ...]:
        key = node_key(kind, identifier)
        return tuple(edge for edge in self._edges if edge.source == key)

    def neighborhood(
        self, kind: str, identifier: str, *, depth: int = 1
    ) -> dict[str, Any]:
        """Return the focused one- or two-hop accessible graph payload."""

        if depth not in {1, 2}:
            raise ValueError("graph depth must be 1 or 2")
        focus = node_key(kind, identifier)
        if focus not in self._nodes:
            raise KeyError(focus)
        selected = {focus}
        frontier = {focus}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for edge in self._edges:
                if edge.source in frontier:
                    next_frontier.add(edge.target)
                if edge.target in frontier:
                    next_frontier.add(edge.source)
            next_frontier -= selected
            selected.update(next_frontier)
            frontier = next_frontier
        edges = tuple(
            edge
            for edge in self._edges
            if edge.source in selected and edge.target in selected
        )
        return {
            "focus": focus,
            "depth": depth,
            "nodes": [self._nodes[key].to_dict() for key in sorted(selected)],
            "edges": [edge.to_dict() for edge in edges],
            "incoming": [edge.to_dict() for edge in edges if edge.target == focus],
            "outgoing": [edge.to_dict() for edge in edges if edge.source == focus],
        }

    def _origin(self, kind: str, identifier: str) -> ContributionOrigin | None:
        origin_key = (
            f"binding:{identifier}"
            if kind in _BINDING_COLLECTIONS
            else f"{kind}:{identifier}"
        )
        return self._catalog.origins.get(origin_key)

    def _add_node(
        self,
        kind: str,
        identifier: str,
        label: str,
        *,
        origin: ContributionOrigin | None = None,
        profile: str | None = None,
        lifecycle: str | None = None,
        missing: bool = False,
    ) -> str:
        key = node_key(kind, identifier)
        resolved_origin = origin or self._origin(kind, identifier)
        if resolved_origin is not None:
            profile = profile or resolved_origin.target_profile
            lifecycle = lifecycle or resolved_origin.lifecycle_status
        self._nodes[key] = GraphNode(
            key=key,
            identifier=identifier,
            label=label,
            kind=kind,
            origin=resolved_origin.to_dict() if resolved_origin else None,
            profile=profile,
            lifecycle=lifecycle,
            editable=key in self._editable,
            draft_state=self._draft_states.get(key, "baseline"),
            missing=missing,
        )
        return key

    def _build_nodes(self) -> None:
        catalog = self._catalog
        registries = (
            ("clinical_object", catalog.clinical_objects),
            ("concept", catalog.concepts),
            ("semantic_relationship", catalog.semantic_relationships),
            ("temporal_semantic", catalog.temporal_semantics),
            ("aggregation", catalog.aggregations),
            ("guardrail", catalog.guardrails),
            ("coverage", catalog.coverage),
            ("vocabulary", catalog.vocabularies),
            ("source", catalog.sources),
            ("context", catalog.contexts),
        )
        for kind, registry in registries:
            for identifier, record in registry.items():
                label = (
                    getattr(record, "label", None)
                    or getattr(record, "title", None)
                    or identifier
                )
                self._add_node(kind, identifier, label)

        for binding in catalog.feature_bindings:
            identifier = binding.id or binding.qualified_identifier
            self._add_node(
                "feature_binding",
                identifier,
                binding.identifier,
                profile=binding.profile,
            )
        for binding in catalog.object_bindings:
            identifier = binding.id or f"{binding.profile}:{binding.object}:{binding.table}"
            self._add_node(
                "object_binding",
                identifier,
                f"{binding.object} in {binding.table}",
                profile=binding.profile,
            )
        for table in catalog.profile_tables:
            identifier = table.id or table.identifier
            table_origin = self._origin("table", identifier)
            self._add_node(
                "table", identifier, table.table, profile=table.profile
            )
            for column in table.columns:
                self._add_node(
                    "physical_column",
                    _physical_column_id(identifier, column.name),
                    f"{table.table}.{column.name}",
                    origin=table_origin,
                    profile=table.profile,
                )
        for binding in catalog.relationship_bindings:
            self._add_node(
                "relationship_binding",
                binding.id,
                binding.id,
                profile=binding.profile,
            )
        for path in catalog.relationship_binding_paths:
            self._add_node(
                "relationship_binding_path",
                path.id,
                path.id,
                profile=path.profile,
            )
        for qualification in catalog.qualifications.values():
            self._add_node(
                "qualification",
                qualification.id,
                qualification.summary,
                origin=qualification.origin,
            )
        for identifier, lineage in catalog.feature_lineage.items():
            origin = catalog.origins.get(f"feature_lineage:{identifier}")
            self._add_node(
                "feature_lineage",
                identifier,
                str(lineage.get("summary", identifier)),
                origin=origin,
                lifecycle=str(lineage.get("lifecycle_status"))
                if lineage.get("lifecycle_status") is not None
                else None,
            )
        for context in catalog.contexts.values():
            context_origin = self._origin("context", context.id)
            for claim in context.claims:
                identifier = f"{context.id}#{claim.id}"
                self._add_node(
                    "claim",
                    identifier,
                    claim.statement,
                    origin=context_origin,
                )

    def _pointer(self, kind: str, identifier: str, field: str) -> str:
        origin = self._origin(kind, identifier)
        token = _pointer_token(identifier)
        if kind == "claim":
            context_id, claim_id = identifier.rsplit("#", 1)
            return (
                f"/contexts/{_pointer_token(context_id)}/claims/"
                f"@id={_pointer_token(claim_id)}/{field}"
            )
        if kind in _BINDING_COLLECTIONS:
            collection = _BINDING_COLLECTIONS[kind]
            return f"/profile_binding/{collection}/@id={token}/{field}"
        if kind == "physical_column":
            table_id, column_name = identifier.split("::", 1)
            return (
                f"/profile_binding/tables/@id={_pointer_token(table_id)}"
                f"/columns/@name={_pointer_token(column_name)}/{field}"
            )
        if kind == "qualification":
            return f"/qualifications/{token}/{field}"
        if kind == "feature_lineage":
            return f"/feature_lineage/{token}/{field}"
        collection = _SEMANTIC_COLLECTIONS.get(kind, f"{kind}s")
        if origin and origin.document_kind in {"profile", "extension"} and kind in {
            "clinical_object", "concept", "semantic_relationship",
            "temporal_semantic", "aggregation", "guardrail", "coverage",
        }:
            return f"/contributions/{collection}/{token}/{field}"
        return f"/{collection}/{token}/{field}"

    def _edge(
        self,
        source_kind: str,
        source_id: str,
        target_kind: str,
        target_id: str,
        edge_type: str,
        field: str,
        index: int | None = None,
    ) -> None:
        source = node_key(source_kind, source_id)
        target = node_key(target_kind, target_id)
        if source not in self._nodes:
            return
        if target not in self._nodes:
            self._add_node(target_kind, target_id, target_id, missing=True)
        pointer = self._pointer(source_kind, source_id, field)
        if index is not None:
            pointer += f"/{index}"
        source_node = self._nodes[source]
        self._edges_build.append(
            GraphEdge(
                source=source,
                target=target,
                type=edge_type,
                direction="outgoing",
                source_pointer=pointer,
                source_contribution=source,
                origin=source_node.origin,
                draft_state=self._draft_states.get(source, "baseline"),
            )
        )

    @staticmethod
    def _graph_kind(kind: str) -> str:
        return "concept" if kind == "feature" else kind

    def _apply_authored_overlay(
        self,
        records: tuple[AuthoredGraphRecord, ...],
        diagnostics: tuple[Mapping[str, Any], ...],
    ) -> None:
        """Overlay current authored state without constructing an invalid Catalog."""

        owned = {
            node_key(self._graph_kind(item.kind), item.identifier)
            for item in records
        }
        for item in records:
            if item.kind != "context":
                continue
            baseline = self._catalog.contexts.get(item.identifier)
            if baseline is not None:
                owned.update(
                    node_key("claim", f"{item.identifier}#{claim.id}")
                    for claim in baseline.claims
                )
            if item.record is not None:
                owned.update(
                    node_key("claim", f"{item.identifier}#{claim.get('id')}")
                    for claim in item.record.get("claims", ())
                    if isinstance(claim, Mapping) and isinstance(claim.get("id"), str)
                )

        self._edges_build[:] = [
            edge for edge in self._edges_build if edge.source not in owned
        ]
        for key in owned:
            self._nodes.pop(key, None)

        table_ids = self._table_ids()
        for item in records:
            if item.kind == "table" and item.record is not None:
                table = item.record.get("table")
                if item.profile and isinstance(table, str):
                    table_ids[(item.profile, table)] = item.identifier
        for item in records:
            if item.record is not None:
                self._add_authored_node(item)
                self._build_authored_edges(item, table_ids)
            else:
                kind = self._graph_kind(item.kind)
                key = node_key(kind, item.identifier)
                self._nodes[key] = GraphNode(
                    key=key,
                    identifier=item.identifier,
                    label=item.identifier,
                    kind=kind,
                    origin=item.origin,
                    profile=item.profile,
                    lifecycle=item.lifecycle,
                    editable=False,
                    draft_state="deleted",
                    missing=True,
                )

        for edge in tuple(self._edges_build):
            if edge.target not in self._nodes:
                kind, identifier = edge.target.split(":", 1)
                self._add_node(kind, identifier, identifier, missing=True)
        self._edges_build[:] = [
            replace(edge, error=True, diagnostics=diagnostics)
            if self._nodes[edge.target].missing
            else edge
            for edge in self._edges_build
        ]

    def _add_authored_node(self, item: AuthoredGraphRecord) -> None:
        kind = self._graph_kind(item.kind)
        record = item.record or {}
        key = node_key(kind, item.identifier)
        self._nodes[key] = GraphNode(
            key=key,
            identifier=item.identifier,
            label=str(
                record.get("label")
                or record.get("title")
                or record.get("summary")
                or item.identifier
            ),
            kind=kind,
            origin=item.origin,
            profile=item.profile,
            lifecycle=item.lifecycle,
            editable=True,
            draft_state=item.draft_state,
        )

    def _authored_edge(
        self,
        item: AuthoredGraphRecord,
        target_kind: str,
        target_id: Any,
        edge_type: str,
        field: str,
        index: int | None = None,
        *,
        source_kind: str | None = None,
        source_id: str | None = None,
        source_pointer: str | None = None,
    ) -> None:
        if not isinstance(target_id, str):
            return
        source = node_key(
            source_kind or self._graph_kind(item.kind),
            source_id or item.identifier,
        )
        pointer = f"{source_pointer or item.source_pointer}/{field}"
        if index is not None:
            pointer += f"/{index}"
        self._edges_build.append(
            GraphEdge(
                source=source,
                target=node_key(target_kind, target_id),
                type=edge_type,
                direction="outgoing",
                source_pointer=pointer,
                source_contribution=source,
                origin=item.origin,
                draft_state=item.draft_state,
            )
        )

    def _authored_many(
        self, item: AuthoredGraphRecord, target_kind: str, values: Any,
        edge_type: str, field: str, **source: Any,
    ) -> None:
        if isinstance(values, (list, tuple)):
            for index, value in enumerate(values):
                self._authored_edge(
                    item, target_kind, value, edge_type, field, index, **source
                )

    def _build_authored_edges(
        self,
        item: AuthoredGraphRecord,
        table_ids: Mapping[tuple[str, str], str],
    ) -> None:
        record = item.record or {}
        for field, target_kind, edge_type, is_many in _AUTHORED_REFERENCE_FIELDS.get(item.kind, ()):
            if is_many:
                self._authored_many(item, target_kind, record.get(field), edge_type, field)
            else:
                self._authored_edge(item, target_kind, record.get(field), edge_type, field)
        if item.kind not in {"source", "vocabulary", "table", "physical_column", "context"}:
            self._authored_many(
                item, "claim", record.get("claim_refs"),
                "supported_by_claim", "claim_refs",
            )
        if item.kind == "coverage":
            target_kind = record.get("subject_kind")
            if target_kind == "feature":
                target_kind = "concept"
            if isinstance(target_kind, str):
                self._authored_edge(
                    item,
                    target_kind,
                    record.get("subject"),
                    "covers_subject",
                    "subject",
                )
        if item.kind == "qualification":
            subject = record.get("subject")
            if isinstance(subject, Mapping):
                target_kind = "concept" if subject.get("kind") == "feature" else subject.get("kind")
                if isinstance(target_kind, str):
                    self._authored_edge(
                        item, target_kind, subject.get("id"),
                        "qualifies_subject",
                        "subject/id",
                    )
        if item.kind in {"feature_binding", "object_binding"}:
            table = record.get("table")
            self._authored_edge(
                item, "table", table_ids.get((item.profile, table), table),
                "binds_table", "table",
            )
            if item.kind == "feature_binding" and isinstance(table, str):
                table_id = table_ids.get((item.profile, table))
                column = record.get("column")
                if isinstance(table_id, str) and isinstance(column, str):
                    self._authored_edge(
                        item, "physical_column",
                        _physical_column_id(table_id, column),
                        "maps_column", "column",
                    )
        if item.kind == "physical_column":
            table_id = item.identifier.split("::", 1)[0]
            self._authored_edge(
                item, "table", table_id, "declared_by_table", "name"
            )
        if item.kind == "relationship_binding":
            for field, edge_type in (("source", "source_table"), ("target", "target_table")):
                endpoint = record.get(field)
                table = endpoint.get("table") if isinstance(endpoint, Mapping) else None
                self._authored_edge(
                    item, "table", table_ids.get((item.profile, table), table),
                    edge_type, f"{field}/table",
                )
        if item.kind == "context":
            self._authored_many(item, "concept", record.get("related_concepts"), "related_concept", "related_concepts")
            self._authored_many(item, "semantic_relationship", record.get("related_relationships"), "related_relationship", "related_relationships")
            for index, table_ref in enumerate(record.get("related_tables", ())):
                if not isinstance(table_ref, Mapping):
                    continue
                profile = table_ref.get("profile")
                table = table_ref.get("table")
                target = table_ids.get((profile, table), table_ref.get("id") or table)
                self._authored_edge(
                    item, "table", target, "related_table", "related_tables", index
                )
            for index, claim in enumerate(record.get("claims", ())):
                if not isinstance(claim, Mapping) or not isinstance(claim.get("id"), str):
                    continue
                claim_id = f"{item.identifier}#{claim['id']}"
                claim_item = AuthoredGraphRecord(
                    kind="claim", identifier=claim_id, record=claim,
                    source_pointer=f"{item.source_pointer}/claims/{index}",
                    origin=item.origin, profile=item.profile,
                    lifecycle=item.lifecycle, draft_state=item.draft_state,
                )
                self._add_authored_node(claim_item)
                self._authored_edge(item, "claim", claim_id, "contains_claim", "claims", index)
                self._authored_many(
                    item, "source", claim.get("sources"), "supported_by_source", "sources",
                    source_kind="claim", source_id=claim_id,
                    source_pointer=claim_item.source_pointer,
                )

    def _many(
        self,
        source_kind: str,
        source_id: str,
        target_kind: str,
        values: Iterable[str],
        edge_type: str,
        field: str,
    ) -> None:
        for index, value in enumerate(values):
            self._edge(
                source_kind,
                source_id,
                target_kind,
                value,
                edge_type,
                field,
                index,
            )

    def _claim_edges(
        self, kind: str, identifier: str, claim_refs: Iterable[str]
    ) -> None:
        self._many(kind, identifier, "claim", claim_refs, "supported_by_claim", "claim_refs")

    def _table_ids(self) -> dict[tuple[str, str], str]:
        return {
            (table.profile, table.table): table.id or table.identifier
            for table in self._catalog.profile_tables
        }

    def _build_edges(self) -> None:
        catalog = self._catalog
        for concept in catalog.concepts.values():
            self._many("concept", concept.id, "clinical_object", concept.objects, "owned_by", "objects")
            self._many("concept", concept.id, "temporal_semantic", concept.temporal_semantics, "has_time_semantic", "temporal_semantics")
            self._many("concept", concept.id, "aggregation", concept.aggregations, "has_aggregation", "aggregations")
            if concept.vocabulary:
                self._edge("concept", concept.id, "vocabulary", concept.vocabulary, "uses_vocabulary", "vocabulary")
            self._claim_edges("concept", concept.id, concept.claim_refs)
        for obj in catalog.clinical_objects.values():
            self._claim_edges("clinical_object", obj.id, obj.claim_refs)
        for rel in catalog.semantic_relationships.values():
            self._edge("semantic_relationship", rel.id, "clinical_object", rel.source_object, "source_object", "source_object")
            self._edge("semantic_relationship", rel.id, "clinical_object", rel.target_object, "target_object", "target_object")
            self._many("semantic_relationship", rel.id, "temporal_semantic", rel.temporal_semantics, "has_time_semantic", "temporal_semantics")
            self._claim_edges("semantic_relationship", rel.id, rel.claim_refs)
        for temporal in catalog.temporal_semantics.values():
            self._many("temporal_semantic", temporal.id, "clinical_object", temporal.objects, "applies_to_object", "objects")
            self._many("temporal_semantic", temporal.id, "concept", temporal.feature_refs, "represented_by_concept", "feature_refs")
            self._many("temporal_semantic", temporal.id, "temporal_semantic", temporal.relative_to, "relative_to", "relative_to")
            self._claim_edges("temporal_semantic", temporal.id, temporal.claim_refs)
        for aggregation in catalog.aggregations.values():
            self._edge("aggregation", aggregation.id, "clinical_object", aggregation.source_object, "source_object", "source_object")
            self._edge("aggregation", aggregation.id, "clinical_object", aggregation.target_object, "target_object", "target_object")
            self._edge("aggregation", aggregation.id, "concept", aggregation.source_concept, "source_concept", "source_concept")
            if aggregation.result_concept:
                self._edge("aggregation", aggregation.id, "concept", aggregation.result_concept, "result_concept", "result_concept")
            self._many("aggregation", aggregation.id, "semantic_relationship", aggregation.semantic_relationships, "uses_relationship", "semantic_relationships")
            self._claim_edges("aggregation", aggregation.id, aggregation.claim_refs)
        guardrail_fields = (
            ("objects", "clinical_object", "guards_object"),
            ("concepts", "concept", "guards_concept"),
            ("semantic_relationships", "semantic_relationship", "guards_relationship"),
            ("temporal_semantics", "temporal_semantic", "guards_time_semantic"),
            ("aggregations", "aggregation", "guards_aggregation"),
            ("coverage", "coverage", "guards_coverage"),
        )
        for guardrail in catalog.guardrails.values():
            for field, target_kind, edge_type in guardrail_fields:
                self._many("guardrail", guardrail.id, target_kind, getattr(guardrail, field), edge_type, field)
            self._claim_edges("guardrail", guardrail.id, guardrail.claim_refs)
        subject_kind_aliases = {"feature": "concept"}
        for coverage in catalog.coverage.values():
            target_kind = subject_kind_aliases.get(coverage.subject_kind, coverage.subject_kind)
            self._edge("coverage", coverage.id, target_kind, coverage.subject, "covers_subject", "subject")
            self._claim_edges("coverage", coverage.id, coverage.claim_refs)
        table_ids = self._table_ids()
        for table in catalog.profile_tables:
            table_id = table.id or table.identifier
            for column in table.columns:
                column_id = _physical_column_id(table_id, column.name)
                self._edge(
                    "physical_column", column_id, "table", table_id,
                    "declared_by_table", "name",
                )
        for context in catalog.contexts.values():
            self._many("context", context.id, "concept", context.related_concepts, "related_concept", "related_concepts")
            self._many("context", context.id, "semantic_relationship", context.related_relationships, "related_relationship", "related_relationships")
            for index, table_ref in enumerate(context.related_tables):
                table_id = table_ids.get((table_ref.profile, table_ref.table), table_ref.identifier)
                self._edge("context", context.id, "table", table_id, "related_table", "related_tables", index)
            for index, claim in enumerate(context.claims):
                claim_id = f"{context.id}#{claim.id}"
                self._edge("context", context.id, "claim", claim_id, "contains_claim", "claims", index)
                for source_index, source_id in enumerate(claim.sources):
                    self._edge("claim", claim_id, "source", source_id, "supported_by_source", f"sources/{source_index}")
        for qualification in catalog.qualifications.values():
            target_kind = subject_kind_aliases.get(qualification.subject_kind, qualification.subject_kind)
            self._edge("qualification", qualification.id, target_kind, qualification.subject_id, "qualifies_subject", "subject/id")
            self._claim_edges("qualification", qualification.id, qualification.claim_refs)
        for binding in catalog.feature_bindings:
            identifier = binding.id or binding.qualified_identifier
            table_id = table_ids[(binding.profile, binding.table)]
            self._edge("feature_binding", identifier, "concept", binding.concept, "binds_concept", "concept")
            self._edge("feature_binding", identifier, "table", table_id, "binds_table", "table")
            self._edge(
                "feature_binding", identifier, "physical_column",
                _physical_column_id(table_id, binding.column),
                "maps_column", "column",
            )
            if binding.vocabulary:
                self._edge("feature_binding", identifier, "vocabulary", binding.vocabulary, "uses_vocabulary", "vocabulary")
        for binding in catalog.object_bindings:
            identifier = binding.id or f"{binding.profile}:{binding.object}:{binding.table}"
            self._edge("object_binding", identifier, "clinical_object", binding.object, "binds_object", "object")
            self._edge("object_binding", identifier, "table", table_ids[(binding.profile, binding.table)], "binds_table", "table")
            self._claim_edges("object_binding", identifier, binding.claim_refs)
        for binding in catalog.relationship_bindings:
            self._edge("relationship_binding", binding.id, "table", table_ids[(binding.profile, binding.source.table)], "source_table", "source/table")
            self._edge("relationship_binding", binding.id, "table", table_ids[(binding.profile, binding.target.table)], "target_table", "target/table")
            self._many("relationship_binding", binding.id, "semantic_relationship", binding.semantic_relationships, "implements_relationship", "semantic_relationships")
            self._claim_edges("relationship_binding", binding.id, binding.claim_refs)
        for path in catalog.relationship_binding_paths:
            self._edge("relationship_binding_path", path.id, "semantic_relationship", path.semantic_relationship, "implements_relationship", "semantic_relationship")
            self._many("relationship_binding_path", path.id, "relationship_binding", path.relationship_bindings, "path_step", "relationship_bindings")
            self._claim_edges("relationship_binding_path", path.id, path.claim_refs)
        for identifier, lineage in catalog.feature_lineage.items():
            output = lineage.get("output_concept")
            if isinstance(output, str):
                self._edge("feature_lineage", identifier, "concept", output, "output_concept", "output_concept")
            self._many("feature_lineage", identifier, "concept", lineage.get("input_concepts", ()), "input_concept", "input_concepts")
            self._many("feature_lineage", identifier, "feature_binding", lineage.get("input_bindings", ()), "input_binding", "input_bindings")
            self._claim_edges("feature_lineage", identifier, lineage.get("claim_refs", ()))


def build_graph(
    catalog: Catalog,
    *,
    editable_keys: Iterable[str] = (),
    draft_states: Mapping[str, str] | None = None,
    authored_overlay: Iterable[AuthoredGraphRecord] = (),
    diagnostics: Iterable[Mapping[str, Any]] = (),
) -> GraphIndex:
    """Convenience factory used by the curator session."""

    return GraphIndex(
        catalog,
        editable_keys=editable_keys,
        draft_states=draft_states,
        authored_overlay=authored_overlay,
        diagnostics=diagnostics,
    )
