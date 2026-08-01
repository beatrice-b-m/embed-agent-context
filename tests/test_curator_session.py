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
