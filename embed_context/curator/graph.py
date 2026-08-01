"""Deterministic typed connection graph for the local curator.

The graph is derived from an already validated effective :class:`Catalog`.
It never reads source files and never mutates catalog records.  Authored-source
metadata which is not retained by ``Catalog`` (editability and draft state) is
accepted as a small overlay keyed by canonical ``kind:id`` node keys.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GraphIndex:
    """An immutable, deterministically ordered graph derived from a catalog."""

    def __init__(
        self,
        catalog: Catalog,
        *,
        editable_keys: Iterable[str] = (),
        draft_states: Mapping[str, str] | None = None,
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
            self._add_node(
                "table", identifier, table.table, profile=table.profile
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
        for revision in catalog.revisions.values():
            self._add_node(
                "revision", revision.id, revision.reason, origin=revision.origin
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
            root = (
                "binding_additions"
                if origin and origin.document_kind == "extension"
                else "profile_binding"
            )
            return f"/{root}/{collection}/@id={token}/{field}"
        if kind == "qualification":
            return f"/qualifications/{token}/{field}"
        if kind == "feature_lineage":
            return f"/feature_lineage/{token}/{field}"
        if kind == "revision":
            return f"/revisions/@id={token}/{field}"
        collection = _SEMANTIC_COLLECTIONS.get(kind, f"{kind}s")
        if kind == "concept" and origin and origin.document_kind == "extension":
            return f"/semantic_additions/concepts/{token}/{field}"
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
            self._edge("feature_binding", identifier, "concept", binding.concept, "binds_concept", "concept")
            self._edge("feature_binding", identifier, "table", table_ids[(binding.profile, binding.table)], "binds_table", "table")
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
        for revision in catalog.revisions.values():
            target_kind = "concept" if revision.kind == "reinterprets_concept" else "feature_binding"
            original_field = (
                "original_concept"
                if revision.kind == "reinterprets_concept"
                else "original_binding"
            )
            replacement_field = (
                "replacement_concept"
                if revision.kind == "reinterprets_concept"
                else "replacement_binding"
            )
            self._edge("revision", revision.id, target_kind, revision.original_id, "revises_original", original_field)
            self._edge("revision", revision.id, target_kind, revision.replacement_id, "selects_replacement", replacement_field)
            self._claim_edges("revision", revision.id, revision.claim_refs)


def build_graph(
    catalog: Catalog,
    *,
    editable_keys: Iterable[str] = (),
    draft_states: Mapping[str, str] | None = None,
) -> GraphIndex:
    """Convenience factory used by the curator session."""

    return GraphIndex(
        catalog, editable_keys=editable_keys, draft_states=draft_states
    )
