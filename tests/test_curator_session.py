"""Curator draft, validation, conflict, diff, and save contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from embed_context.curator.session import CuratorError, CuratorSession


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC = ROOT / "catalog/semantic/catalog.json"
PROFILE = ROOT / "catalog/profiles/open-v2.json"
QUALIFICATION = "open-v2.qualification.clinical_object.breast_imaging_episode"


class CuratorSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        directory = Path(self.temporary.name)
        self.semantic = directory / "semantic.json"
        self.profile = directory / "profile.json"
        self.semantic.write_bytes(SEMANTIC.read_bytes())
        self.profile.write_bytes(PROFILE.read_bytes())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def session(self, *, editable: bool = True) -> CuratorSession:
        return CuratorSession(
            self.semantic,
            profile_paths=[self.profile],
            edit_module=self.profile if editable else None,
        )

    def test_read_only_inventory_and_real_discovery(self) -> None:
        session = self.session(editable=False)
        inventory = session.list_records(text="pathology", limit=20)
        self.assertGreater(inventory["total"], 0)
        self.assertTrue(all(not item["editable"] for item in inventory["records"]))
        result = session.discover({"query": "absent pathology", "profile": "open-v2", "limit": 3})
        self.assertEqual(result["baseline"]["count"], 3)
        self.assertFalse(result["comparison"]["available"])
        with self.assertRaises(CuratorError) as caught:
            session.create_record({})
        self.assertEqual(caught.exception.error_type, "read_only")

    def test_valid_replacement_diff_revision_conflict_and_atomic_save(self) -> None:
        session = self.session()
        record = session.get_record("qualification", QUALIFICATION)
        replacement = dict(record["authored"])
        replacement["summary"] = "Maintainer-reviewed synthetic profile qualification."
        result = session.replace_record(
            "qualification", QUALIFICATION,
            {"revision": 0, "record": replacement},
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["revision"], 1)
        self.assertIn("Maintainer-reviewed", session.diff()["diff"])
        with self.assertRaises(CuratorError) as caught:
            session.replace_record("qualification", QUALIFICATION, {"revision": 0, "record": replacement})
        self.assertEqual(caught.exception.error_type, "revision_conflict")
        saved = session.save(expected_revision=1)
        self.assertTrue(saved["saved"])
        self.assertFalse(saved["dirty"])
        self.assertTrue(saved["valid"])
        self.assertFalse(session.dirty)
        authored = json.loads(self.profile.read_text(encoding="utf-8"))
        self.assertEqual(authored["qualifications"][QUALIFICATION]["summary"], replacement["summary"])

    def test_invalid_draft_is_retained_but_cannot_save(self) -> None:
        session = self.session()
        record = session.get_record("qualification", QUALIFICATION)
        replacement = dict(record["authored"])
        replacement["claim_refs"] = ["missing.context#missing-claim"]
        result = session.replace_record("qualification", QUALIFICATION, {"revision": 0, "record": replacement})
        self.assertFalse(result["valid"])
        self.assertTrue(result["diagnostics"])
        self.assertTrue(session.dirty)
        with self.assertRaises(CuratorError) as caught:
            session.save(expected_revision=1)
        self.assertEqual(caught.exception.error_type, "validation_error")

    def test_immutable_feature_opens_and_one_edit_has_one_changed_record(self) -> None:
        session = self.session()
        feature = session.get_record("feature", "pathology.severity")
        self.assertEqual(feature["identifier"], "pathology.severity")
        self.assertIsInstance(
            feature["form_spec"]["record"]["aggregations"], list
        )
        self.assertIn(
            "aggregation.pathology-severity-to-side",
            feature["form_spec"]["record"]["aggregations"],
        )

        record = session.get_record("qualification", QUALIFICATION)["authored"]
        record["summary"] += " Reviewed."
        session.replace_record(
            "qualification",
            QUALIFICATION,
            {"revision": 0, "record": record},
        )
        self.assertEqual(
            session.diff()["changed_records"],
            [
                {
                    "kind": "qualification",
                    "identifier": QUALIFICATION,
                    "state": "modified",
                }
            ],
        )

    def test_incomplete_create_is_rejected_without_mutating_draft(self) -> None:
        session = self.session()
        spec = session.creation_form_spec("qualification")
        self.assertTrue(spec["enhanced"])
        self.assertTrue(
            next(field for field in spec["fields"] if field["name"] == "id")[
                "required"
            ]
        )

        before = session.session_info()
        with self.assertRaises(CuratorError) as caught:
            session.create_record(
                {
                    "revision": before["revision"],
                    "kind": "qualification",
                    "identifier": "project.incomplete",
                    "record": {},
                }
            )
        self.assertEqual(caught.exception.error_type, "local_validation_error")
        after = session.session_info()
        self.assertEqual(after["revision"], before["revision"])
        self.assertEqual(after["dirty"], before["dirty"])

    def test_invalid_draft_graph_uses_current_broken_reference(self) -> None:
        session = self.session()
        record = session.get_record("qualification", QUALIFICATION)
        replacement = dict(record["authored"])
        replacement["claim_refs"] = ["missing.context#missing-claim"]
        result = session.replace_record(
            "qualification", QUALIFICATION,
            {"revision": 0, "record": replacement},
        )
        self.assertFalse(result["valid"])

        graph = session.neighborhood("qualification", QUALIFICATION)
        edge = next(
            edge
            for edge in graph["outgoing"]
            if edge["target"] == "claim:missing.context#missing-claim"
        )
        missing = next(
            node
            for node in graph["nodes"]
            if node["key"] == "claim:missing.context#missing-claim"
        )
        self.assertEqual(edge["draft_state"], "modified")
        self.assertTrue(edge["error"])
        self.assertEqual(edge["diagnostics"], result["diagnostics"])
        self.assertTrue(missing["missing"])

    def test_deleted_table_is_missing_in_current_draft_graph(self) -> None:
        session = self.session()
        authored = json.loads(self.profile.read_text(encoding="utf-8"))
        table = authored["profile_binding"]["tables"][0]
        table_id = table["id"]
        before = session.neighborhood("table", table_id)
        incoming = next(
            edge
            for edge in before["incoming"]
            if edge["source"].startswith(("feature_binding:", "object_binding:"))
        )
        source_kind, source_id = incoming["source"].split(":", 1)

        result = session.delete_record(
            "table", table_id, {"revision": 0, "confirm": True}
        )
        self.assertFalse(result["valid"])
        deleted = session.list_records(status="deleted")
        self.assertTrue(
            any(
                item["kind"] == "table" and item["identifier"] == table_id
                for item in deleted["records"]
            )
        )
        deleted_record = session.get_record("table", table_id)
        self.assertEqual(deleted_record["draft_state"], "deleted")
        self.assertFalse(deleted_record["editable"])
        deleted_graph = session.neighborhood("table", table_id)
        deleted_focus = next(
            node for node in deleted_graph["nodes"] if node["key"] == f"table:{table_id}"
        )
        self.assertTrue(deleted_focus["missing"])
        self.assertEqual(deleted_focus["draft_state"], "deleted")
        graph = session.neighborhood(source_kind, source_id)
        edge = next(
            edge for edge in graph["outgoing"]
            if edge["target"] == f"table:{table_id}"
        )
        target = next(
            node for node in graph["nodes"]
            if node["key"] == f"table:{table_id}"
        )
        self.assertTrue(edge["error"])
        self.assertTrue(target["missing"])

    def test_context_source_change_prevents_save(self) -> None:
        session = self.session()
        record = session.get_record("qualification", QUALIFICATION)
        replacement = dict(record["authored"])
        replacement["summary"] += " Reviewed."
        session.replace_record("qualification", QUALIFICATION, {"revision": 0, "record": replacement})
        self.semantic.write_bytes(self.semantic.read_bytes() + b" ")
        with self.assertRaises(CuratorError) as caught:
            session.save(expected_revision=1)
        self.assertEqual(caught.exception.error_type, "composition_changed")


if __name__ == "__main__":
    unittest.main()
