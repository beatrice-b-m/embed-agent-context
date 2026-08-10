import importlib.resources
import json
from pathlib import Path
import shutil
import subprocess
from types import MappingProxyType
import unittest

from embed_context_curator.forms import (
    build_form_spec,
    definition_schema,
    local_validate_record,
    merge_record_json,
)


ROOT = Path(__file__).resolve().parents[3]
STATIC_ROOT = ROOT / "packages/curator/src/embed_context_curator/static"


class CuratorFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extension_schema = json.loads(
            (ROOT / "catalog/extensions/extension.schema.json").read_text()
        )

    def test_every_field_has_a_control_and_lossless_fallback(self):
        for family in (
            "concept",
            "clinical_context",
            "context_claim",
            "qualification",
            "feature_binding",
            "physical_column",
            "coverage",
            "vocabulary",
        ):
            with self.subTest(family=family):
                record_schema = definition_schema(self.extension_schema, family)
                expected_fields = list(record_schema.get("properties", {}))
                for variant in record_schema.get("oneOf", []):
                    for name in variant.get("properties", {}):
                        if name not in expected_fields:
                            expected_fields.append(name)
                record = {"future_schema_valid_field": {"nested": [1, 2]}}
                spec = build_form_spec(
                    self.extension_schema, family, record=record
                )
                self.assertEqual(
                    [field["name"] for field in spec["fields"]],
                    expected_fields,
                )
                self.assertEqual(spec["record"], record)
                self.assertEqual(spec["fallback"]["control"], "record_json")

    def test_reference_choices_are_compatible_and_deterministic(self):
        spec = build_form_spec(
            self.extension_schema,
            "feature_binding",
            references={
                "concept": [
                    {"id": "project.z", "label": "Zulu"},
                    {"id": "project.a", "label": "Alpha"},
                ],
                "table": ["project_table"],
                "guardrail": ["guardrail.not-compatible"],
            },
        )
        fields = {field["name"]: field for field in spec["fields"]}
        self.assertEqual(fields["concept"]["control"], "reference")
        self.assertEqual(
            [choice["id"] for choice in fields["concept"]["choices"]],
            ["project.a", "project.z"],
        )
        self.assertEqual(
            [choice["id"] for choice in fields["table"]["choices"]],
            ["project_table"],
        )
        self.assertNotIn(
            "guardrail.not-compatible",
            [choice["id"] for choice in fields["concept"]["choices"]],
        )

    def test_existing_identifier_is_immutable_but_create_identifier_is_not(self):
        existing = build_form_spec(self.extension_schema, "feature_binding")
        creating = build_form_spec(
            self.extension_schema, "feature_binding", creating=True
        )
        existing_id = next(field for field in existing["fields"] if field["name"] == "id")
        creating_id = next(field for field in creating["fields"] if field["name"] == "id")
        self.assertTrue(existing_id["immutable"])
        self.assertFalse(creating_id["immutable"])

    def test_record_merge_preserves_uncontrolled_fields(self):
        original = {"id": "project.x", "nested": {"preserve": True}}
        replacement = {"summary": "Changed"}
        merged = merge_record_json(original, replacement)
        self.assertEqual(
            merged,
            {
                "id": "project.x",
                "nested": {"preserve": True},
                "summary": "Changed",
            },
        )
        merged["nested"]["preserve"] = False
        self.assertTrue(original["nested"]["preserve"])

    def test_form_spec_normalizes_nested_immutable_record_values(self):
        record = MappingProxyType(
            {
                "id": "project.x",
                "nested": MappingProxyType({"values": ("one", "two")}),
            }
        )
        spec = build_form_spec(
            self.extension_schema, "feature_binding", record=record
        )
        self.assertEqual(
            spec["record"]["nested"], {"values": ["one", "two"]}
        )

    def test_local_validation_returns_normalized_schema_diagnostics(self):
        diagnostics = local_validate_record(
            self.extension_schema, "qualification", {"id": "bad id"}
        )
        self.assertTrue(diagnostics)
        self.assertTrue(all(item["stage"] == "local" for item in diagnostics))
        self.assertTrue(all(item["pointer"].startswith("/") for item in diagnostics))
        self.assertTrue(any("required" in item["message"] for item in diagnostics))


class CuratorStaticContractTests(unittest.TestCase):
    def test_static_assets_are_package_resources(self):
        static = importlib.resources.files("embed_context_curator").joinpath("static")
        for name in ("index.html", "app.js", "styles.css"):
            self.assertTrue(static.joinpath(name).is_file(), name)

    def test_shell_uses_external_assets_and_safe_dom_rendering(self):
        html = (STATIC_ROOT / "index.html").read_text()
        javascript = (STATIC_ROOT / "app.js").read_text()
        self.assertIn('src="/app.js"', html)
        self.assertIn('href="/styles.css"', html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("innerHTML", javascript)
        self.assertIn("textContent", javascript)

    def test_shell_exposes_complete_navigation_query_and_graph_controls(self):
        html = (STATIC_ROOT / "index.html").read_text()
        for control in (
            "filter-text",
            "filter-kind",
            "filter-origin",
            "filter-profile",
            "filter-lifecycle",
            "filter-domain",
            "filter-status",
            "query-kinds",
            "query-domain",
            "query-comparison",
            "graph-depth",
        ):
            with self.subTest(control=control):
                self.assertIn(f'id="{control}"', html)

    def test_javascript_uses_layered_metadata_and_complete_comparisons(self):
        javascript = (STATIC_ROOT / "app.js").read_text()
        for contract in (
            "data?.source",
            "origin.contribution_class",
            "comparison.changes",
            "implementation_bindings",
            'history: "none"',
            "graphDepth",
            "?depth=${depth}",
            "load-more-records",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, javascript)

    def test_javascript_buffers_unapplied_editor_text_per_record(self):
        javascript = (STATIC_ROOT / "app.js").read_text()
        self.assertIn("const buffered = bufferedRecordValue(", javascript)
        self.assertIn("recordBufferKey(identity)", javascript)
        self.assertIn(
            'byId("record-editor").addEventListener("input", () => {\n'
            "    bufferCurrentEditor();",
            javascript,
        )
        self.assertIn(
            "state.buffer = discardBufferedRecord(state.buffer, "
            "recordBufferKey(state.selection));",
            javascript,
        )

    def test_save_and_shutdown_paths_track_unapplied_editor_buffers(self):
        javascript = (STATIC_ROOT / "app.js").read_text()
        self.assertIn(
            "rebaseDraftBuffer(state.buffer, data.revision || 0)",
            javascript,
        )
        self.assertIn(
            "const discardUnsaved = hasUnsavedWork(state.session, state.buffer);",
            javascript,
        )
        self.assertIn("discard_unsaved: discardUnsaved", javascript)
        self.assertIn(
            'draftAction("/api/draft/reset", "Draft reset", '
            "{ discardLocal: true })",
            javascript,
        )
        self.assertNotIn("if (data.saved || data.dirty === false)", javascript)

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable")
    def test_create_form_dom_events_track_cancelled_work_until_reset(self):
        app_uri = (STATIC_ROOT / "app.js").as_uri()
        script = f"""
          import {{createDraftBuffer, hasUnsavedWork,
                   trackCreateFormChanges, updateCreateFormBuffer}}
            from {json.dumps(app_uri)};

          class Input extends EventTarget {{
            constructor(value) {{ super(); this.value = value; }}
            enter(value) {{
              this.value = value;
              this.dispatchEvent(new Event('input'));
            }}
          }}

          const controls = {{
            kind: new Input(''),
            identifier: new Input(''),
            recordJson: new Input('{{}}'),
          }};
          const session = {{revision: 0, dirty: false}};
          let buffer = createDraftBuffer(session.revision);
          trackCreateFormChanges(controls, (values) => {{
            buffer = updateCreateFormBuffer(buffer, values);
          }});

          controls.kind.enter('qualification');
          controls.identifier.enter('project.incomplete');
          controls.recordJson.enter('{{"id":');
          // Closing the dialog emits no input event, so the draft must remain dirty.
          if (!hasUnsavedWork(session, buffer)) process.exit(1);

          controls.kind.enter('');
          controls.identifier.enter('');
          controls.recordJson.enter('{{}}');
          if (hasUnsavedWork(session, buffer)) process.exit(2);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable")
    def test_apply_edit_save_shutdown_buffer_interaction(self):
        app_uri = (STATIC_ROOT / "app.js").as_uri()
        script = f"""
          import {{createDraftBuffer, bufferRecord, discardBufferedRecord,
                   bufferedRecordValue, rebaseDraftBuffer,
                   hasUnsavedWork}} from {json.dumps(app_uri)};
          let session = {{revision: 0, dirty: false}};
          let buffer = createDraftBuffer(session.revision);

          buffer = bufferRecord(buffer, 'qualification:record-a', 'applied A');
          session = {{revision: 1, dirty: true}};
          buffer = discardBufferedRecord(buffer, 'qualification:record-a');
          buffer = bufferRecord(buffer, 'qualification:record-b', '{{"id":');

          session = {{revision: 2, dirty: false, saved: true}};
          buffer = rebaseDraftBuffer(buffer, session.revision);
          if (bufferedRecordValue(buffer, 'qualification:record-b', '') !== '{{"id":') process.exit(1);
          if (buffer.revision !== 2 || !buffer.dirty || !hasUnsavedWork(session, buffer)) process.exit(2);

          const discardUnsaved = hasUnsavedWork(session, buffer);
          if (!discardUnsaved) process.exit(3);
          const shutdownBody = {{discard_unsaved: discardUnsaved}};
          if (shutdownBody.discard_unsaved !== true) process.exit(4);

          buffer = createDraftBuffer(session.revision);
          if (hasUnsavedWork(session, buffer)) process.exit(5);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable")
    def test_dom_independent_javascript_draft_helpers(self):
        app_uri = (STATIC_ROOT / "app.js").as_uri()
        script = f"""
          import {{createDraftBuffer, bufferRecord, discardBufferedRecord,
                   bufferedRecordValue, recordBufferKey,
                   localShapeChecks, mergeRecordValues, parseKinds,
                   encodeEnhancedValue, decodeEnhancedValue,
                   recordOwnershipFacts, applyEnhancedValues,
                   nextRenderBatch}} from {json.dumps(app_uri)};
          let state = createDraftBuffer(4);
          const conceptKey = recordBufferKey({{kind: 'concept', id: 'project.x'}});
          state = bufferRecord(state, conceptKey, '{{"id":');
          if (!state.dirty || state.revision !== 4) process.exit(1);
          state = bufferRecord(state, 'concept:project.y', '{{"id":"project.y"}}');
          if (bufferedRecordValue(state, conceptKey, 'fallback') !== '{{"id":') process.exit(13);
          if (bufferedRecordValue(state, 'concept:missing', 'fallback') !== 'fallback') process.exit(14);
          const merged = mergeRecordValues({{nested: {{keep: true}}}}, {{label: 'X'}});
          if (!merged.nested.keep || merged.label !== 'X') process.exit(2);
          const errors = localShapeChecks({{fields: [
            {{name: 'id', required: true, type: 'string'}},
            {{name: 'domains', type: 'array', list_behavior: 'set'}}
          ]}}, {{domains: ['x', 'x']}});
          if (errors.length !== 2) process.exit(3);
          state = discardBufferedRecord(state, conceptKey);
          if (!state.dirty || bufferedRecordValue(state, 'concept:project.y', '') !== '{{"id":"project.y"}}') process.exit(4);
          state = discardBufferedRecord(state, 'concept:project.y');
          if (state.dirty) process.exit(15);
          const kinds = parseKinds('feature, guardrail, feature');
          if (JSON.stringify(kinds) !== JSON.stringify(['feature', 'guardrail'])) process.exit(5);
          const arrayField = {{name: 'claim_refs', type: 'array', control: 'reference'}};
          const refs = ['context.example#claim'];
          if (JSON.stringify(decodeEnhancedValue(arrayField, encodeEnhancedValue(arrayField, refs))) !== JSON.stringify(refs)) process.exit(6);
          try {{ decodeEnhancedValue(arrayField, '"scalar"'); process.exit(7); }} catch {{}}
          const objectField = {{name: 'subject', type: 'object', control: 'reference'}};
          const subject = {{kind: 'concept', id: 'project.x'}};
          const decodedSubject = decodeEnhancedValue(objectField, encodeEnhancedValue(objectField, subject));
          if (Array.isArray(decodedSubject) || decodedSubject.id !== 'project.x') process.exit(8);
          const facts = Object.fromEntries(recordOwnershipFacts({{
            editable: true, draft_state: 'modified',
            source: {{document: '/tmp/catalog.json', document_kind: 'extension', module_id: 'project', target_profile: 'open-v2'}},
            origin: {{contribution_class: 'project', lifecycle_status: 'draft'}}
          }}, {{kind: 'feature', id: 'project.x'}}));
          if (facts['Owning document'] !== '/tmp/catalog.json' || facts.Module !== 'project' || facts.Lifecycle !== 'draft') process.exit(9);
          if (Object.values(facts).includes('[object Object]')) process.exit(10);
          const enhanced = applyEnhancedValues({{summary: 'Before', untouched: true}}, [{{
            field: {{name: 'summary', type: 'string', control: 'textarea'}},
            raw: 'After', checked: false
          }}]);
          if (enhanced.summary !== 'After' || !enhanced.untouched) process.exit(11);
          const records = Array.from({{length: 120}}, (_, index) => index);
          const batch = nextRenderBatch(records, 50);
          if (batch.length !== 50 || batch[0] !== 50 || batch[49] !== 99) process.exit(12);
        """
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
