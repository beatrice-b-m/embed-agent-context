"""Integration contracts for the checked-in structured catalog."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from embed_context import load_catalog
from embed_context.catalog import (
    ANALYSIS_PATTERN_STATUSES,
    BINDING_PARAMETER_KEYS,
    CARDINALITY_VALUES,
    CLAIM_STATUSES,
    CONTEXT_KINDS,
    CONTEXT_SCOPES,
    DOMAINS,
    ENDPOINT_COMPLETENESS,
    EVIDENCE_VALUES,
    FEATURE_KINDS,
    GRAINS,
    KEY_COMPLETENESS,
    KEY_KINDS,
    KEY_UNIQUENESS,
    RELATIONSHIP_KINDS,
    ROLES,
    SOURCE_KINDS,
    SOURCE_LOCATOR_KINDS,
    VOCABULARY_COMPLETENESS,
    VOCABULARY_PARSING,
    _BINDING_KEYS,
    _BINDING_REQUIRED_KEYS,
    _ANALYSIS_ALTERNATIVE_KEYS,
    _ANALYSIS_DECISION_KEYS,
    _ANALYSIS_PATTERN_KEYS,
    _CONCEPT_KEYS,
    _CONCEPT_REQUIRED_KEYS,
    _CLINICAL_CONTEXT_KEYS,
    _CONTEXT_CLAIM_KEYS,
    _CONTEXT_SOURCE_KEYS,
    _CONTEXT_TABLE_REFERENCE_KEYS,
    _PROHIBITED_SHORTCUT_KEYS,
    _VOCABULARY_KEYS,
    _VOCABULARY_REQUIRED_KEYS,
    _WORKFLOW_STEP_KEYS,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CheckedInCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog()

    def test_every_concept_and_binding_resolves_exactly(self) -> None:
        for concept_id in self.catalog.concepts:
            with self.subTest(concept=concept_id):
                result = self.catalog.get_feature(concept_id)
                self.assertEqual(result["concept"]["id"], concept_id)

        for binding in self.catalog.bindings:
            with self.subTest(binding=binding.qualified_identifier):
                result = self.catalog.get_feature(binding.qualified_identifier)
                self.assertEqual(result["binding"]["concept"], binding.concept)

    def test_every_table_and_relationship_resolves_exactly(self) -> None:
        for table in self.catalog.tables:
            with self.subTest(table=table.identifier):
                result = self.catalog.get_table(table.profile, table.table)
                self.assertEqual(result["identifier"], table.identifier)

        for relationship in self.catalog.relationships:
            with self.subTest(relationship=relationship.id):
                result = self.catalog.get_relationship(relationship.id)
                self.assertEqual(result["identifier"], relationship.id)

    def test_phase_three_context_inventory_resolves_with_sources(self) -> None:
        expected_contexts = {
            "clinical.screening-diagnostic-pathway",
            "embed.finding-procedure-recording",
            "open-v2.assessment-recommendation-context",
            "open-v2.demographic-administrative-context",
            "open-v2.linked-exam-context",
            "open-v2.multimodal-finding-context",
            "open-v2.pathology-procedure-context",
            "open-v2.report-context",
            "open-v2.risk-context",
            "open-v2.temporal-availability-context",
        }
        self.assertEqual(set(self.catalog.contexts), expected_contexts)

        cited_sources = set()
        for context_id, context in self.catalog.contexts.items():
            with self.subTest(context=context_id):
                result = self.catalog.get_context(context_id)
                self.assertEqual(result["identifier"], context_id)
                claim_sources = {
                    source_id
                    for claim in context.claims
                    for source_id in claim.sources
                }
                self.assertEqual(set(result["sources"]), claim_sources)
                cited_sources.update(claim_sources)

        self.assertEqual(cited_sources, set(self.catalog.sources))

    def test_initial_analysis_pattern_exposes_policy_boundaries(self) -> None:
        self.assertEqual(
            set(self.catalog.analysis_patterns),
            {"open-v2.pathology-cancer-vs-noncancer"},
        )
        result = self.catalog.get_analysis_pattern(
            "open-v2.pathology-cancer-vs-noncancer"
        )
        pattern = result["pattern"]
        self.assertEqual(pattern["status"], "draft")
        self.assertEqual(len(pattern["alternatives"]), 3)
        self.assertIn(
            "null-is-negative",
            {
                item["id"] for item in pattern["prohibited_shortcuts"]
            },
        )
        self.assertIn(
            "control-definition",
            {item["id"] for item in pattern["required_decisions"]},
        )
        search = self.catalog.search_analysis_patterns(
            "cancer versus no cancer",
            profile="open-v2",
            domain="pathology",
        )
        self.assertEqual(search["total"], 1)

    def test_phase_three_context_keeps_scope_and_maintainer_boundaries(self) -> None:
        self.assertEqual(
            {context.scope for context in self.catalog.contexts.values()},
            {"general_clinical", "embed_general", "profile_specific"},
        )
        statuses = {
            claim.status
            for context in self.catalog.contexts.values()
            for claim in context.claims
        }
        self.assertTrue({"verified", "reconciled", "unresolved"} <= statuses)

        for context in self.catalog.contexts.values():
            if context.scope == "profile_specific":
                continue
            with self.subTest(context=context.id):
                self.assertFalse(context.related_tables)
                self.assertFalse(context.related_relationships)

        temporal = self.catalog.get_context(
            "open-v2.temporal-availability-context"
        )["context"]
        claims = {claim["id"]: claim for claim in temporal["claims"]}
        anonymization = claims["anonymization-properties"]
        self.assertEqual(anonymization["status"], "verified")
        self.assertIn("consistent random date shift", anonymization["statement"])
        self.assertNotIn("policy-boundaries", claims)
        self.assertNotIn("downstream-availability", claims)

        linked = self.catalog.get_context(
            "open-v2.linked-exam-context"
        )["context"]
        linked_claims = {
            claim["id"]: claim for claim in linked["claims"]
        }
        self.assertEqual(linked_claims["link-meaning"]["status"], "verified")
        self.assertIn(
            "same-episode exam",
            linked_claims["link-meaning"]["statement"],
        )

        multimodal = self.catalog.get_context(
            "open-v2.multimodal-finding-context"
        )["context"]
        multimodal_claims = {
            claim["id"]: claim for claim in multimodal["claims"]
        }
        self.assertEqual(
            multimodal_claims["descriptor-null-semantics"]["status"],
            "verified",
        )
        self.assertNotIn("modality-followup-policy", multimodal_claims)

        pathology = self.catalog.get_context(
            "open-v2.pathology-procedure-context"
        )["context"]
        pathology_claims = {
            claim["id"]: claim for claim in pathology["claims"]
        }
        self.assertEqual(
            pathology_claims["severity-meaning"]["status"],
            "verified",
        )
        self.assertEqual(
            pathology_claims["severity-aggregation"]["status"],
            "verified",
        )
        self.assertEqual(
            pathology_claims["pathology-code-mappings"]["status"],
            "unresolved",
        )
        self.assertIn(
            "no single authoritative owner",
            pathology_claims["pathology-code-mappings"]["statement"],
        )

        report = self.catalog.get_context("open-v2.report-context")["context"]
        report_claims = {claim["id"]: claim for claim in report["claims"]}
        self.assertEqual(
            report_claims["sequence-meaning"]["status"],
            "reconciled",
        )
        self.assertIn(
            "minimum represented sequence",
            report_claims["sequence-meaning"]["statement"],
        )
        self.assertEqual(report_claims["addendum-link"]["status"], "unresolved")
        self.assertIn(
            "real-world exceptions",
            report_claims["addendum-link"]["statement"],
        )

        risk = self.catalog.get_context("open-v2.risk-context")["context"]
        risk_claims = {claim["id"]: claim for claim in risk["claims"]}
        self.assertEqual(risk_claims["risk-availability"]["status"], "verified")
        self.assertEqual(risk_claims["risk-semantics"]["status"], "unresolved")
        self.assertIn(
            "tentatively believed to use percentage points",
            risk_claims["risk-semantics"]["statement"],
        )

        demographics = self.catalog.get_context(
            "open-v2.demographic-administrative-context"
        )["context"]
        demographic_claims = {
            claim["id"]: claim for claim in demographics["claims"]
        }
        self.assertEqual(
            {
                claim_id: claim["status"]
                for claim_id, claim in demographic_claims.items()
            },
            {
                "age-years-and-quality": "verified",
                "age-at-exam-deidentification": "verified",
                "ashkenazi-heritage": "verified",
                "legal-sex": "verified",
                "release-version-meaning": "verified",
            },
        )

    def test_maintainer_review_semantics_are_registered(self) -> None:
        multimodal = self.catalog.get_context(
            "open-v2.multimodal-finding-context"
        )["context"]
        claims = {claim["id"]: claim for claim in multimodal["claims"]}
        self.assertEqual(
            claims["mammography-aggregate-semantics"]["status"],
            "verified",
        )
        self.assertIn(
            "finding number -9",
            claims["synthetic-contralateral-finding"]["statement"],
        )
        self.assertIn(
            "null side attached to a clinical finding",
            claims["finding-side-null"]["statement"],
        )
        self.assertIn(
            "do not share one guaranteed delimiter",
            claims["field-specific-parsing"]["statement"],
        )

        assessment = self.catalog.get_context(
            "open-v2.assessment-recommendation-context"
        )["context"]
        assessment_claims = {
            claim["id"]: claim for claim in assessment["claims"]
        }
        self.assertIn(
            "no single authoritative owner",
            assessment_claims["recommendation-code-mappings"]["statement"],
        )

        finding_number = self.catalog.get_feature(
            "imaging.finding_number"
        )["concept"]
        self.assertIn("Ordinal finding number", finding_number["definition"])
        self.assertTrue(
            any(
                "synthetic contralateral negative" in caveat
                for caveat in finding_number["caveats"]
            )
        )

        age = self.catalog.get_feature("demographics.age_at_exam")["concept"]
        self.assertIn("Age in years", age["definition"])
        self.assertTrue(
            any("top-coded to 89" in caveat for caveat in age["caveats"])
        )

        gender = self.catalog.get_feature(
            "demographics.gender_description"
        )["concept"]
        self.assertIn("legal sex", gender["definition"])

        release = self.catalog.get_feature("exam.release_version")["concept"]
        self.assertIn("first EMBED release", release["definition"])

        for concept_id in (
            "breast_side.pathology_severity_aggregate",
            "exam.pathology_severity_aggregate",
        ):
            with self.subTest(concept=concept_id):
                concept = self.catalog.get_feature(concept_id)["concept"]
                self.assertIn("Minimum", concept["definition"])
                self.assertNotIn("unresolved", concept["evidence"])

    def test_phase_three_requirement_level_context_queries(self) -> None:
        temporal = self.catalog.search_contexts("temporal leakage")
        self.assertIn(
            "open-v2.temporal-availability-context",
            {
                match["identifier"]
                for match in temporal["matches"]
            },
        )

        pathology_text = self.catalog.search_contexts("pathology")
        pathology_context = next(
            match
            for match in pathology_text["matches"]
            if match["identifier"] == "open-v2.pathology-procedure-context"
        )
        self.assertNotIn(
            "finding-versus-biopsy-side",
            {
                claim["id"]
                for claim in pathology_context["matching_claims"]
            },
        )

        pathology = self.catalog.search_contexts(
            "",
            profile="open-v2",
            domain="pathology",
            status="unresolved",
        )
        self.assertGreater(pathology["total"], 0)
        self.assertTrue(
            all(
                match["profiles"] == ["open-v2"]
                for match in pathology["matches"]
            )
        )
        self.assertTrue(
            all(
                claim["status"] == "unresolved"
                for match in pathology["matches"]
                for claim in match["matching_claims"]
            )
        )

    def test_open_v2_relationship_inventory_is_complete(self) -> None:
        expected = {
            "open-v2.combined_anon.exam_projection",
            "open-v2.combined_anon.imaging_index_projection",
            "open-v2.combined_anon.linked_exam",
            "open-v2.combined_anon.pathology_index_projection",
            "open-v2.combined_anon.patient_projection",
            "open-v2.combined_anon.side_projection",
            "open-v2.exam_level_anon.patient",
            "open-v2.imaging_findings_anon.exam",
            "open-v2.imaging_findings_anon.linked_exam",
            "open-v2.imaging_findings_anon.side",
            "open-v2.pathology_findings_anon.exam",
            "open-v2.pathology_findings_anon.imaging_finding",
            "open-v2.pathology_findings_anon.side",
            "open-v2.reports_anon.exam",
            "open-v2.reports_anon.patient",
            "open-v2.risk_anon.exam",
            "open-v2.risk_anon.patient",
            "open-v2.side_level_anon.exam",
        }
        actual = {
            relationship.id
            for relationship in self.catalog.relationships
            if relationship.profile == "open-v2"
        }
        self.assertEqual(actual, expected)

    def test_unreliable_natural_keys_and_wide_hazards_remain_explicit(self) -> None:
        by_table = {table.table: table for table in self.catalog.tables}
        for table_name in (
            "imaging_findings_anon",
            "pathology_findings_anon",
            "reports_anon",
        ):
            with self.subTest(table=table_name):
                natural_keys = [
                    key
                    for key in by_table[table_name].keys
                    if key.kind == "natural"
                ]
                self.assertTrue(natural_keys)
                self.assertTrue(
                    all(
                        key.uniqueness != "unique"
                        for key in natural_keys
                    )
                )

        wide_relationships = self.catalog.search_relationships(
            table="combined_anon"
        )["matches"]
        self.assertTrue(wide_relationships)
        self.assertTrue(
            all(item["join_hazards"] for item in wide_relationships)
        )

        for relationship_id in (
            "open-v2.combined_anon.linked_exam",
            "open-v2.imaging_findings_anon.linked_exam",
        ):
            with self.subTest(relationship=relationship_id):
                linked = self.catalog.get_relationship(relationship_id)[
                    "relationship"
                ]
                self.assertEqual(
                    linked["source"]["completeness"], "optional"
                )
                self.assertEqual(
                    linked["cardinality"]["targets_per_source"], "zero_or_one"
                )
                self.assertTrue(linked["join_hazards"])


    def test_domain_only_search_returns_each_matching_concept_once(self) -> None:
        for domain in (
            "pathology",
            "demographics",
            "social_determinants_of_health",
        ):
            with self.subTest(domain=domain):
                expected = {
                    concept_id
                    for concept_id, concept in self.catalog.concepts.items()
                    if domain in concept.domains
                }
                result = self.catalog.search_features("", domain=domain)
                identifiers = [
                    match["identifier"] for match in result["matches"]
                ]
                self.assertEqual(set(identifiers), expected)
                self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_shared_accession_and_pathology_slots_are_normalized(self) -> None:
        accession = self.catalog.get_feature("exam.accession_identifier")
        self.assertTrue(accession["bindings"])
        self.assertEqual(
            {binding["column"] for binding in accession["bindings"]},
            {"acc_anon"},
        )

        pathology_slots = [
            binding
            for binding in self.catalog.bindings
            if binding.column.startswith("path")
            and binding.column.removeprefix("path").isdigit()
        ]
        self.assertTrue(pathology_slots)
        self.assertEqual(
            {binding.concept for binding in pathology_slots},
            {"pathology.diagnosis_code_slot"},
        )
        for binding in pathology_slots:
            self.assertEqual(
                dict(binding.parameters)["slot"],
                int(binding.column.removeprefix("path")),
            )

    def test_code_lookup_returns_plain_structured_meaning(self) -> None:
        result = self.catalog.lookup_code("imaging.assessment", "N")
        self.assertEqual(result["meaning"], "Negative")
        self.assertEqual(result["concept"], "imaging.assessment")

        severity = self.catalog.lookup_code("pathology.severity", "0")
        self.assertEqual(severity["meaning"], "Invasive breast cancer")
        self.assertEqual(severity["concept"], "pathology.severity")

        for vocabulary in self.catalog.vocabularies.values():
            for _, meaning in vocabulary.codes:
                self.assertNotIn("**", meaning)
                self.assertNotIn("`", meaning)

    def test_requirement_level_text_queries(self) -> None:
        accession = self.catalog.search_features("ACCAnon")
        self.assertEqual(accession["total"], 1)
        self.assertEqual(
            accession["matches"][0]["identifier"],
            "exam.accession_identifier",
        )

        demographic = self.catalog.search_features("demographic features")
        self.assertGreater(demographic["total"], 0)
        self.assertTrue(
            all(
                "demographics" in match["domains"]
                for match in demographic["matches"]
            )
        )

        masses = self.catalog.search_features("breast masses")
        mass_identifiers = {
            match["identifier"] for match in masses["matches"]
        }
        self.assertTrue(mass_identifiers)
        self.assertNotIn("breast.side", mass_identifiers)
        self.assertTrue(
            any("mass" in identifier for identifier in mass_identifiers)
        )

    def test_pathology_severity_aggregates_share_codes_and_derivation(self) -> None:
        for concept_id in (
            "breast_side.pathology_severity_aggregate",
            "exam.pathology_severity_aggregate",
        ):
            with self.subTest(concept=concept_id):
                concept = self.catalog.concepts[concept_id]
                caveats = concept.caveats
                self.assertEqual(concept.vocabulary, "pathology.severity")
                self.assertIn("Minimum", concept.definition)
                self.assertTrue(
                    any(
                        "minimum value is the most severe" in item
                        for item in caveats
                    )
                )
                self.assertTrue(
                    all(
                        "finding-level presence flag" not in item
                        for item in caveats
                    )
                )

    def test_schema_facets_match_the_dependency_free_core(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "catalog/catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        properties = schema["properties"]
        self.assertEqual(properties["grains"]["const"], list(GRAINS))
        self.assertEqual(
            properties["feature_kinds"]["const"], list(FEATURE_KINDS)
        )
        self.assertEqual(properties["domains"]["const"], list(DOMAINS))
        self.assertEqual(
            properties["context_kinds"]["const"], list(CONTEXT_KINDS)
        )
        self.assertEqual(
            properties["context_scopes"]["const"], list(CONTEXT_SCOPES)
        )
        self.assertEqual(
            properties["source_kinds"]["const"], list(SOURCE_KINDS)
        )
        self.assertEqual(
            properties["source_locator_kinds"]["const"],
            list(SOURCE_LOCATOR_KINDS),
        )
        self.assertEqual(
            properties["claim_statuses"]["const"], list(CLAIM_STATUSES)
        )
        self.assertEqual(
            properties["analysis_pattern_statuses"]["const"],
            list(ANALYSIS_PATTERN_STATUSES),
        )
        definitions = schema["$defs"]
        self.assertEqual(
            set(definitions["evidence"]["enum"]), EVIDENCE_VALUES
        )
        self.assertEqual(
            set(definitions["binding"]["properties"]["role"]["enum"]),
            ROLES,
        )
        self.assertEqual(
            set(
                definitions["binding"]["properties"]["parameters"][
                    "properties"
                ]
            ),
            BINDING_PARAMETER_KEYS,
        )
        self.assertEqual(
            set(
                definitions["vocabulary"]["properties"]["completeness"][
                    "enum"
                ]
            ),
            VOCABULARY_COMPLETENESS,
        )
        self.assertEqual(
            set(
                definitions["vocabulary"]["properties"]["parsing"]["enum"]
            ),
            VOCABULARY_PARSING,
        )
        self.assertEqual(
            set(definitions["key"]["properties"]["kind"]["enum"]),
            KEY_KINDS,
        )
        self.assertEqual(
            set(definitions["key"]["properties"]["uniqueness"]["enum"]),
            KEY_UNIQUENESS,
        )
        self.assertEqual(
            set(definitions["key"]["properties"]["completeness"]["enum"]),
            KEY_COMPLETENESS,
        )
        self.assertEqual(
            set(definitions["relationship"]["properties"]["kind"]["enum"]),
            RELATIONSHIP_KINDS,
        )
        self.assertEqual(
            set(
                definitions["source_endpoint"]["properties"][
                    "completeness"
                ]["enum"]
            ),
            ENDPOINT_COMPLETENESS,
        )
        self.assertEqual(
            set(definitions["cardinality_value"]["enum"]),
            CARDINALITY_VALUES,
        )
        self.assertEqual(
            set(definitions["context_source"]["properties"]),
            _CONTEXT_SOURCE_KEYS,
        )
        self.assertEqual(
            set(definitions["clinical_context"]["properties"]),
            _CLINICAL_CONTEXT_KEYS,
        )
        self.assertEqual(
            set(definitions["context_claim"]["properties"]),
            _CONTEXT_CLAIM_KEYS,
        )
        self.assertEqual(
            set(definitions["context_table_reference"]["properties"]),
            _CONTEXT_TABLE_REFERENCE_KEYS,
        )
        self.assertEqual(
            set(definitions["workflow_step"]["properties"]),
            _WORKFLOW_STEP_KEYS,
        )
        self.assertEqual(
            set(definitions["analysis_pattern"]["properties"]),
            _ANALYSIS_PATTERN_KEYS,
        )
        self.assertEqual(
            set(definitions["analysis_alternative"]["properties"]),
            _ANALYSIS_ALTERNATIVE_KEYS,
        )
        self.assertEqual(
            set(definitions["analysis_decision"]["properties"]),
            _ANALYSIS_DECISION_KEYS,
        )
        self.assertEqual(
            set(definitions["prohibited_shortcut"]["properties"]),
            _PROHIBITED_SHORTCUT_KEYS,
        )
        for definition in (
            "context_source",
            "clinical_context",
            "context_claim",
            "context_table_reference",
            "workflow_step",
            "analysis_pattern",
            "analysis_alternative",
            "analysis_decision",
            "prohibited_shortcut",
        ):
            with self.subTest(definition=definition):
                self.assertEqual(
                    set(definitions[definition]["required"]),
                    set(definitions[definition]["properties"]),
                )
        for definition, allowed, required in (
            ("concept", _CONCEPT_KEYS, _CONCEPT_REQUIRED_KEYS),
            ("binding", _BINDING_KEYS, _BINDING_REQUIRED_KEYS),
            (
                "vocabulary",
                _VOCABULARY_KEYS,
                _VOCABULARY_REQUIRED_KEYS,
            ),
        ):
            with self.subTest(definition=definition):
                self.assertEqual(
                    set(definitions[definition]["properties"]), allowed
                )
                self.assertEqual(
                    set(definitions[definition]["required"]), required
                )

    def test_phase_two_schema_strings_match_core_validation(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "catalog/catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        definitions = schema["$defs"]
        identifier_schemas = (
            definitions["key"]["properties"]["id"],
            definitions["table"]["properties"]["profile"],
            definitions["relationship"]["properties"]["id"],
            definitions["relationship"]["properties"]["profile"],
        )
        for identifier_schema in identifier_schemas:
            pattern = identifier_schema["pattern"]
            with self.subTest(pattern=pattern):
                self.assertIsNotNone(re.search(pattern, "open-v2.valid_id"))
                for invalid in ("open-v2.valid_id\n", "Open-v2", " "):
                    self.assertIsNone(re.search(pattern, invalid))

        nonblank_schemas = (
            definitions["key"]["properties"]["caveats"]["items"],
            definitions["table"]["properties"]["caveats"]["items"],
            definitions["relationship"]["properties"]["caveats"]["items"],
            definitions["relationship"]["properties"]["join_hazards"]["items"],
        )
        for string_schema in nonblank_schemas:
            pattern = string_schema["pattern"]
            with self.subTest(pattern=pattern):
                self.assertIsNotNone(re.search(pattern, "Documented caveat."))
                self.assertIsNone(re.search(pattern, " \t\n"))


if __name__ == "__main__":
    unittest.main()
