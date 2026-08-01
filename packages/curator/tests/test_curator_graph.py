"""Focused tests for the curator's derived connection graph."""

from __future__ import annotations

import unittest

from embed_context import load_catalog
from embed_context_curator.graph import AuthoredGraphRecord, GraphIndex, node_key


class CuratorGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()
        cls.graph = GraphIndex(cls.catalog)

    def test_concept_edges_are_typed_and_retain_authored_location(self) -> None:
        outgoing = self.graph.outgoing("concept", "pathology.severity")
        keys = {(edge.type, edge.target) for edge in outgoing}

        self.assertIn(("owned_by", "clinical_object:pathology_diagnosis"), keys)
        self.assertIn(
            (
                "has_time_semantic",
                "temporal_semantic:time.pathology-report-documentation",
            ),
            keys,
        )
        aggregation_edge = next(
            edge
            for edge in outgoing
            if edge.target
            == "aggregation:aggregation.pathology-observation-severity"
        )
        self.assertEqual(
            aggregation_edge.source_pointer,
            "/concepts/pathology.severity/aggregations/0",
        )
        self.assertEqual(
            aggregation_edge.origin["contribution_class"], "portable"
        )

    def test_physical_binding_edges_use_authored_stable_ids(self) -> None:
        binding = next(
            item
            for item in self.catalog.feature_bindings
            if item.concept == "pathology.severity" and item.role == "canonical"
        )
        outgoing = self.graph.outgoing("feature_binding", binding.id)

        self.assertIn(
            "concept:pathology.severity", {edge.target for edge in outgoing}
        )
        table_edge = next(edge for edge in outgoing if edge.type == "binds_table")
        self.assertTrue(table_edge.target.startswith("table:open-v2.binding.table."))
        self.assertIn(
            f"/@id={binding.id}/table", table_edge.source_pointer
        )
        self.assertEqual(table_edge.origin["target_profile"], "open-v2")

    def test_claim_provenance_connects_context_claim_and_source(self) -> None:
        context = self.catalog.contexts["clinical.screening-diagnostic-pathway"]
        claim = context.claims[0]
        claim_id = f"{context.id}#{claim.id}"

        incoming = self.graph.incoming("claim", claim_id)
        outgoing = self.graph.outgoing("claim", claim_id)

        self.assertIn("contains_claim", {edge.type for edge in incoming})
        self.assertEqual(
            {edge.target for edge in outgoing},
            {f"source:{source}" for source in claim.sources},
        )
        self.assertTrue(
            all(
                edge.source_pointer.startswith(
                    f"/contexts/{context.id}/claims/@id={claim.id}/sources/"
                )
                for edge in outgoing
            )
        )

    def test_neighborhood_is_bounded_deterministic_and_bidirectional(self) -> None:
        first = self.graph.neighborhood("concept", "pathology.severity", depth=2)
        second = self.graph.neighborhood("concept", "pathology.severity", depth=2)

        self.assertEqual(first, second)
        self.assertEqual(first["focus"], "concept:pathology.severity")
        self.assertTrue(first["incoming"])
        self.assertTrue(first["outgoing"])
        self.assertEqual(
            [node["key"] for node in first["nodes"]],
            sorted(node["key"] for node in first["nodes"]),
        )
        with self.assertRaisesRegex(ValueError, "depth"):
            self.graph.neighborhood("concept", "pathology.severity", depth=3)
        with self.assertRaises(KeyError):
            self.graph.neighborhood("concept", "missing")

    def test_editability_and_draft_state_overlay_only_node_metadata(self) -> None:
        key = node_key("concept", "pathology.severity")
        graph = GraphIndex(
            self.catalog,
            editable_keys=[key],
            draft_states={key: "modified"},
        )
        node = graph.get_node("concept", "pathology.severity")

        self.assertIsNotNone(node)
        self.assertTrue(node.editable)
        self.assertEqual(node.draft_state, "modified")
        self.assertTrue(
            all(edge.draft_state == "modified" for edge in graph.outgoing("concept", "pathology.severity"))
        )

    def test_authored_overlay_marks_broken_reference_with_diagnostics(self) -> None:
        identifier = "open-v2.qualification.clinical_object.breast_imaging_episode"
        diagnostic = {"stage": "composition", "message": "missing draft claim"}
        graph = GraphIndex(
            self.catalog,
            authored_overlay=[
                AuthoredGraphRecord(
                    kind="qualification",
                    identifier=identifier,
                    record={
                        "summary": "Draft qualification",
                        "subject": {
                            "kind": "clinical_object",
                            "id": "breast_imaging_episode",
                        },
                        "claim_refs": ["missing.context#missing-claim"],
                    },
                    source_pointer=f"/qualifications/{identifier}",
                    origin=None,
                    profile="open-v2",
                    lifecycle="released",
                    draft_state="modified",
                )
            ],
            diagnostics=[diagnostic],
        )

        edge = next(
            edge
            for edge in graph.outgoing("qualification", identifier)
            if edge.target == "claim:missing.context#missing-claim"
        )
        self.assertTrue(edge.error)
        self.assertEqual(edge.diagnostics, (diagnostic,))
        self.assertEqual(
            edge.source_pointer,
            f"/qualifications/{identifier}/claim_refs/0",
        )
        self.assertTrue(
            graph.get_node("claim", "missing.context#missing-claim").missing
        )

    def test_authored_coverage_overlay_preserves_subject_edge(self) -> None:
        identifier = next(iter(self.catalog.coverage))
        coverage = self.catalog.coverage[identifier]
        graph = GraphIndex(
            self.catalog,
            authored_overlay=[
                AuthoredGraphRecord(
                    kind="coverage",
                    identifier=identifier,
                    record={
                        "summary": "Edited coverage",
                        "subject_kind": coverage.subject_kind,
                        "subject": coverage.subject,
                        "claim_refs": list(coverage.claim_refs),
                    },
                    source_pointer=f"/coverage/{identifier}",
                    origin=None,
                    profile=None,
                    lifecycle=None,
                    draft_state="modified",
                )
            ],
        )

        self.assertTrue(
            any(
                edge.type == "covers_subject"
                and edge.target
                == f"{coverage.subject_kind}:{coverage.subject}"
                for edge in graph.outgoing("coverage", identifier)
            )
        )


if __name__ == "__main__":
    unittest.main()
