"""Unit tests for strict loading and deterministic catalog queries."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from embed_context import (
    CatalogAmbiguousError,
    CatalogNotFoundError,
    CatalogValidationError,
    load_catalog,
)
from tests.catalog_fixture import synthetic_catalog, write_catalog


class CatalogLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def load(self, data: dict | None = None):
        return load_catalog(
            write_catalog(self.directory / "catalog.json", data)
        )

    @staticmethod
    def exam_relationship(
        *,
        source_completeness: str = "required",
        targets_per_source: str = "zero_or_one",
    ) -> dict:
        return {
            "id": "synthetic.exam_reference",
            "profile": "open-v2",
            "kind": "reference",
            "source": {
                "table": "exam_level_anon",
                "columns": ["acc_anon"],
                "completeness": source_completeness,
            },
            "target": {
                "table": "exam_level_anon",
                "columns": ["acc_anon"],
            },
            "cardinality": {
                "targets_per_source": targets_per_source,
                "sources_per_target": "zero_or_more",
            },
            "evidence": ["inference"],
            "caveats": [],
            "join_hazards": [],
        }

    def test_loads_and_freezes_synthetic_catalog(self) -> None:
        catalog = self.load()

        self.assertEqual(catalog.schema_version, 3)
        self.assertEqual(catalog.profiles, ("open-v2",))
        self.assertEqual(len(catalog.concepts), 2)
        self.assertEqual(len(catalog.bindings), 3)
        self.assertEqual(len(catalog.vocabularies), 1)
        self.assertEqual(len(catalog.sources), 1)
        self.assertEqual(len(catalog.contexts), 1)
        with self.assertRaises(TypeError):
            catalog.concepts["new"] = catalog.concepts["identity.accession"]
        with self.assertRaises(FrozenInstanceError):
            catalog.bindings[0].profile = "changed"
        with self.assertRaises(TypeError):
            catalog.contexts["new"] = catalog.contexts[
                "open-v2.density-interpretation"
            ]
        with self.assertRaises(FrozenInstanceError):
            catalog.contexts[
                "open-v2.density-interpretation"
            ].claims[0].status = "changed"
        with self.assertRaises(AttributeError):
            catalog._schema_version = 4

    def test_loads_and_freezes_table_relationship_metadata(self) -> None:
        data = synthetic_catalog()
        data["relationships"] = [
            {
                "id": "synthetic.wide_density_projection",
                "profile": "open-v2",
                "kind": "projection",
                "source": {
                    "table": "combined_anon",
                    "columns": ["tissueden"],
                    "completeness": "optional",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["tissueden"],
                },
                "cardinality": {
                    "targets_per_source": "unknown",
                    "sources_per_target": "unknown",
                },
                "evidence": ["inference"],
                "caveats": ["Synthetic relationship for contract tests."],
                "join_hazards": ["Values are not established as equal."],
            }
        ]

        catalog = self.load(data)

        self.assertEqual(len(catalog.tables), 2)
        self.assertEqual(len(catalog.relationships), 1)
        self.assertEqual(
            catalog.relationships[0].source.columns, ("tissueden",)
        )
        with self.assertRaises(FrozenInstanceError):
            catalog.tables[0].grain = "exam"
        with self.assertRaises(FrozenInstanceError):
            catalog.relationships[0].kind = "reference"

    def test_loads_strict_sourced_context_contract(self) -> None:
        catalog = self.load()

        source = catalog.sources["open-v2.release-schema"]
        context = catalog.contexts["open-v2.density-interpretation"]

        self.assertEqual(source.scope, "profile_specific")
        self.assertEqual(source.profiles, ("open-v2",))
        self.assertEqual(context.scope, "profile_specific")
        self.assertEqual(
            context.related_tables[0].identifier,
            "open-v2:exam_level_anon",
        )
        self.assertEqual(context.claims[0].id, "coded-feature")
        self.assertEqual(context.claims[0].status, "verified")
        self.assertEqual(context.workflow_steps, ())

    def test_rejects_unknown_context_references(self) -> None:
        mutations = (
            (
                "related_concepts",
                lambda data: data["contexts"][
                    "open-v2.density-interpretation"
                ]["related_concepts"].append("missing.concept"),
                "unknown concepts",
            ),
            (
                "related_tables",
                lambda data: data["contexts"][
                    "open-v2.density-interpretation"
                ]["related_tables"].append(
                    {"profile": "open-v2", "table": "missing_table"}
                ),
                "unknown table",
            ),
            (
                "related_relationships",
                lambda data: data["contexts"][
                    "open-v2.density-interpretation"
                ]["related_relationships"].append("missing.relationship"),
                "unknown relationship",
            ),
            (
                "claim_sources",
                lambda data: data["contexts"][
                    "open-v2.density-interpretation"
                ]["claims"][0]["sources"].append("missing.source"),
                "unknown sources",
            ),
        )
        for name, mutate, message in mutations:
            with self.subTest(name=name):
                data = synthetic_catalog()
                mutate(data)
                with self.assertRaisesRegex(
                    CatalogValidationError, message
                ):
                    self.load(data)

    def test_rejects_context_scope_and_source_authority_mismatches(self) -> None:
        data = synthetic_catalog()
        source = data["sources"]["open-v2.release-schema"]
        source["scope"] = "embed_general"
        with self.assertRaisesRegex(
            CatalogValidationError, "empty profile list"
        ):
            self.load(data)

        data = synthetic_catalog()
        context = data["contexts"]["open-v2.density-interpretation"]
        context["scope"] = "embed_general"
        with self.assertRaisesRegex(
            CatalogValidationError, "empty profile list"
        ):
            self.load(data)

        data = synthetic_catalog()
        source = data["sources"]["open-v2.release-schema"]
        source.update(
            {
                "kind": "public_documentation",
                "scope": "embed_general",
                "locator_kind": "url",
                "locator": "https://example.test/embed",
                "profiles": [],
            }
        )
        with self.assertRaisesRegex(
            CatalogValidationError, "verified.*no applicable"
        ):
            self.load(data)

    def test_rejects_unsafe_source_locators_and_empirical_context_fields(
        self,
    ) -> None:
        for locator in (
            "/Users/example/private.md",
            "../private.md",
        ):
            with self.subTest(locator=locator):
                data = synthetic_catalog()
                source = data["sources"]["open-v2.release-schema"]
                source["locator_kind"] = "repository_path"
                source["locator"] = locator
                with self.assertRaisesRegex(
                    CatalogValidationError, "repository-relative"
                ):
                    self.load(data)

        for target, field in (
            ("source", "row_count"),
            ("context", "prevalence"),
            ("claim", "positive_count"),
        ):
            with self.subTest(target=target):
                data = synthetic_catalog()
                if target == "source":
                    data["sources"]["open-v2.release-schema"][field] = 10
                elif target == "context":
                    data["contexts"][
                        "open-v2.density-interpretation"
                    ][field] = 10
                else:
                    data["contexts"][
                        "open-v2.density-interpretation"
                    ]["claims"][0][field] = 10
                with self.assertRaisesRegex(
                    CatalogValidationError, "unexpected fields"
                ):
                    self.load(data)

    def test_validates_ordered_workflow_steps_and_claim_ids(self) -> None:
        data = synthetic_catalog()
        context = data["contexts"]["open-v2.density-interpretation"]
        context["kind"] = "clinical_workflow"
        with self.assertRaisesRegex(
            CatalogValidationError, "at least two ordered stages"
        ):
            self.load(data)

        context["workflow_steps"] = [
            {
                "id": "interpret",
                "label": "Interpret density",
                "claims": ["coded-feature"],
            },
            {
                "id": "review",
                "label": "Review context",
                "claims": ["missing-claim"],
            },
        ]
        with self.assertRaisesRegex(
            CatalogValidationError, "unknown claims"
        ):
            self.load(data)

        duplicate = synthetic_catalog()
        claim = copy.deepcopy(
            duplicate["contexts"]["open-v2.density-interpretation"][
                "claims"
            ][0]
        )
        duplicate["contexts"]["open-v2.density-interpretation"][
            "claims"
        ].append(claim)
        with self.assertRaisesRegex(
            CatalogValidationError, "duplicate claim IDs"
        ):
            self.load(duplicate)

    def test_rejects_incomplete_table_and_relationship_contracts(self) -> None:
        missing_table = synthetic_catalog()
        missing_table["tables"].pop()
        with self.assertRaisesRegex(
            CatalogValidationError, "no table specification"
        ):
            self.load(missing_table)

        unknown_key_column = synthetic_catalog()
        unknown_key_column["tables"][1]["keys"][0]["columns"] = ["missing"]
        with self.assertRaisesRegex(
            CatalogValidationError, "references unknown columns"
        ):
            self.load(unknown_key_column)

        bad_relationship = synthetic_catalog()
        bad_relationship["relationships"] = [
            {
                "id": "synthetic.bad",
                "profile": "open-v2",
                "kind": "reference",
                "source": {
                    "table": "combined_anon",
                    "columns": ["tissueden"],
                    "completeness": "unknown",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["tissueden", "acc_anon"],
                },
                "cardinality": {
                    "targets_per_source": "unknown",
                    "sources_per_target": "unknown",
                },
                "evidence": ["unresolved"],
                "caveats": [],
                "join_hazards": [],
            }
        ]
        with self.assertRaisesRegex(
            CatalogValidationError, "equal length"
        ):
            self.load(bad_relationship)

    def test_rejects_empirical_fields_in_linkage_objects(self) -> None:
        for target in ("table", "key"):
            with self.subTest(target=target):
                data = synthetic_catalog()
                if target == "table":
                    data["tables"][0]["row_count"] = 10
                else:
                    data["tables"][1]["keys"][0]["duplicate_count"] = 10
                with self.assertRaisesRegex(
                    CatalogValidationError, "unexpected fields"
                ):
                    self.load(data)

    def test_cardinality_requires_unique_key_on_the_one_side(self) -> None:
        data = synthetic_catalog()
        data["relationships"] = [
            {
                "id": "synthetic.nonunique_source",
                "profile": "open-v2",
                "kind": "projection",
                "source": {
                    "table": "combined_anon",
                    "columns": ["tissueden"],
                    "completeness": "unknown",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["tissueden"],
                },
                "cardinality": {
                    "targets_per_source": "unknown",
                    "sources_per_target": "zero_or_one",
                },
                "evidence": ["inference"],
                "caveats": [],
                "join_hazards": [],
            }
        ]

        with self.assertRaisesRegex(
            CatalogValidationError, "source columns.*unique key"
        ):
            self.load(data)

    def test_rejects_conflicting_key_declarations_for_same_columns(self) -> None:
        for field, value in (
            ("kind", "technical"),
            ("uniqueness", "not_unique"),
            ("completeness", "incomplete"),
        ):
            with self.subTest(field=field):
                data = synthetic_catalog()
                conflicting = copy.deepcopy(data["tables"][1]["keys"][0])
                conflicting["id"] = f"exam.accession.conflicting_{field}"
                conflicting[field] = value
                data["tables"][1]["keys"].append(conflicting)

                with self.assertRaisesRegex(
                    CatalogValidationError,
                    "conflicting key declarations.*acc_anon",
                ):
                    self.load(data)

    def test_rejects_source_completeness_conflicting_with_key(self) -> None:
        for key_completeness, source_completeness in (
            ("complete", "optional"),
            ("incomplete", "required"),
        ):
            with self.subTest(
                key=key_completeness,
                source=source_completeness,
            ):
                data = synthetic_catalog()
                data["tables"][1]["keys"][0][
                    "completeness"
                ] = key_completeness
                data["relationships"] = [
                    self.exam_relationship(
                        source_completeness=source_completeness
                    )
                ]

                with self.assertRaisesRegex(
                    CatalogValidationError,
                    "source completeness.*contradicts.*key completeness",
                ):
                    self.load(data)

    def test_at_least_one_target_requires_complete_source_endpoint(self) -> None:
        for source_completeness in ("optional", "unknown"):
            for targets_per_source in ("exactly_one", "one_or_more"):
                with self.subTest(
                    source=source_completeness,
                    cardinality=targets_per_source,
                ):
                    data = synthetic_catalog()
                    data["tables"][1]["keys"][0]["completeness"] = "unknown"
                    data["relationships"] = [
                        self.exam_relationship(
                            source_completeness=source_completeness,
                            targets_per_source=targets_per_source,
                        )
                    ]

                    with self.assertRaisesRegex(
                        CatalogValidationError,
                        "at least one target.*source completeness.*required",
                    ):
                        self.load(data)

    def test_rejects_duplicate_json_object_keys(self) -> None:
        serialized = json.dumps(synthetic_catalog())
        serialized = serialized.replace(
            '"schema_version": 3',
            '"schema_version": 3, "schema_version": 3',
            1,
        )
        path = self.directory / "duplicate.json"
        path.write_text(serialized, encoding="utf-8")

        with self.assertRaisesRegex(
            CatalogValidationError, "duplicate JSON object key"
        ):
            load_catalog(path)

    def test_rejects_unsupported_version_before_version_specific_shape(self) -> None:
        version_one = synthetic_catalog()
        version_one["schema_version"] = 1
        version_one.pop("tables")
        version_one.pop("relationships")

        future = synthetic_catalog()
        future["schema_version"] = 4
        future["future_extension"] = {}

        for version, data in ((1, version_one), (4, future)):
            with self.subTest(version=version):
                with self.assertRaisesRegex(
                    CatalogValidationError,
                    rf"unsupported catalog schema_version {version}; "
                    "expected integer 3",
                ):
                    self.load(data)

    def test_rejects_nonstandard_json_numbers(self) -> None:
        data = synthetic_catalog()
        data["bindings"][0]["parameters"] = {"slot": float("nan")}
        serialized = json.dumps(data)
        path = self.directory / "nan.json"
        path.write_text(serialized, encoding="utf-8")

        with self.assertRaisesRegex(
            CatalogValidationError, "non-standard JSON number"
        ):
            load_catalog(path)

    def test_rejects_unknown_structural_fields(self) -> None:
        data = synthetic_catalog()
        data["concepts"]["identity.accession"]["extra"] = "not allowed"

        with self.assertRaisesRegex(
            CatalogValidationError, "unexpected fields: extra"
        ):
            self.load(data)

    def test_binding_parameters_are_closed_to_empirical_fields(self) -> None:
        for field in (
            "null-count",
            "null_rate",
            "prevalence",
            "row_total",
            "percentage",
            "min",
            "max",
            "category_frequency",
            "observed_categories",
            "n_rows",
            "release_rows",
            "null_pct",
        ):
            with self.subTest(field=field):
                data = synthetic_catalog()
                data["bindings"][0]["parameters"] = {field: 10}
                with self.assertRaisesRegex(
                    CatalogValidationError, "unsupported fields"
                ):
                    self.load(data)

    def test_binding_slot_parameter_must_be_a_positive_integer(self) -> None:
        for value in (0, -1, True, "1", 1.5):
            with self.subTest(value=value):
                data = synthetic_catalog()
                data["bindings"][0]["parameters"] = {"slot": value}
                with self.assertRaisesRegex(
                    CatalogValidationError, "positive integer"
                ):
                    self.load(data)

    def test_allows_semantic_vocabulary_codes_named_like_statistics(self) -> None:
        data = synthetic_catalog()
        data["vocabularies"]["exam.tissue_density"]["codes"]["mean"] = (
            "Synthetic semantic code"
        )

        catalog = self.load(data)

        self.assertEqual(
            catalog.lookup_code("exam.tissue_density", "mean")["meaning"],
            "Synthetic semantic code",
        )

    def test_rejects_unknown_concept_and_vocabulary_references(self) -> None:
        missing_concept = synthetic_catalog()
        missing_concept["bindings"][0]["concept"] = "missing.concept"
        with self.assertRaisesRegex(
            CatalogValidationError, "unknown concept"
        ):
            self.load(missing_concept)

        missing_vocabulary = synthetic_catalog()
        missing_vocabulary["concepts"]["exam.tissue_density"][
            "vocabulary"
        ] = "missing.vocabulary"
        with self.assertRaisesRegex(
            CatalogValidationError, "unknown vocabulary"
        ):
            self.load(missing_vocabulary)

    def test_rejects_duplicate_physical_bindings(self) -> None:
        data = synthetic_catalog()
        data["bindings"].append(copy.deepcopy(data["bindings"][0]))

        with self.assertRaisesRegex(
            CatalogValidationError, "duplicate physical binding"
        ):
            self.load(data)

    def test_rejects_unknown_controlled_values(self) -> None:
        data = synthetic_catalog()
        data["bindings"][0]["grain"] = "unknown"
        with self.assertRaisesRegex(CatalogValidationError, "unknown value"):
            self.load(data)

    def test_rejects_profiles_without_bindings(self) -> None:
        data = synthetic_catalog()
        data["profiles"].append("empty")

        with self.assertRaisesRegex(
            CatalogValidationError, "profiles have no physical bindings: empty"
        ):
            self.load(data)

    def test_rejects_vocabulary_ids_that_shadow_physical_features(self) -> None:
        data = synthetic_catalog()
        vocabulary = data["vocabularies"].pop("exam.tissue_density")
        physical_name = "exam_level_anon.acc_anon"
        data["vocabularies"][physical_name] = vocabulary
        data["concepts"]["exam.tissue_density"]["vocabulary"] = physical_name

        with self.assertRaisesRegex(
            CatalogValidationError,
            "vocabulary IDs collide with physical identifiers",
        ):
            self.load(data)

    def test_requires_shared_concept_and_vocabulary_ids_to_be_linked(self) -> None:
        data = synthetic_catalog()
        data["vocabularies"]["identity.accession"] = copy.deepcopy(
            data["vocabularies"]["exam.tissue_density"]
        )

        with self.assertRaisesRegex(
            CatalogValidationError,
            "concept/vocabulary IDs may overlap only",
        ):
            self.load(data)

    def test_rejects_ambiguous_physical_name_separators_and_whitespace(self) -> None:
        for field, value in (
            ("table", "bad:name"),
            ("column", "bad:name"),
            ("table", " padded"),
            ("column", "padded "),
        ):
            with self.subTest(field=field, value=value):
                data = synthetic_catalog()
                data["bindings"][0][field] = value
                with self.assertRaises(CatalogValidationError):
                    self.load(data)

    def test_allows_same_physical_name_in_different_profiles(self) -> None:
        data = synthetic_catalog()
        data["profiles"].append("future")
        future = copy.deepcopy(data["bindings"][0])
        future["profile"] = "future"
        data["bindings"].append(future)
        future_table = copy.deepcopy(data["tables"][1])
        future_table["profile"] = "future"
        future_table["keys"] = []
        data["tables"].append(future_table)

        catalog = self.load(data)

        unqualified = catalog.get_feature("exam_level_anon.tissueden")
        self.assertEqual(unqualified["kind"], "binding_set")
        self.assertEqual(
            [item["profile"] for item in unqualified["bindings"]],
            ["future", "open-v2"],
        )
        qualified = catalog.get_feature(
            "future:exam_level_anon.tissueden"
        )
        self.assertEqual(qualified["kind"], "binding")
        self.assertEqual(qualified["binding"]["profile"], "future")

    def test_requires_profile_for_ambiguous_physical_name(self) -> None:
        data = synthetic_catalog()
        data["profiles"].append("future")
        future = copy.deepcopy(data["bindings"][0])
        future["profile"] = "future"
        future["concept"] = "identity.accession"
        data["bindings"].append(future)
        future_table = copy.deepcopy(data["tables"][1])
        future_table["profile"] = "future"
        future_table["keys"] = []
        data["tables"].append(future_table)
        catalog = self.load(data)

        with self.assertRaisesRegex(
            CatalogAmbiguousError,
            "future:exam_level_anon.tissueden.*"
            "open-v2:exam_level_anon.tissueden",
        ):
            catalog.get_feature("exam_level_anon.tissueden")
        qualified = catalog.get_feature(
            "future:exam_level_anon.tissueden"
        )
        self.assertEqual(
            qualified["concept"]["id"], "identity.accession"
        )


class CatalogQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.catalog = load_catalog(
            write_catalog(
                Path(self.temporary.name) / "catalog.json",
                synthetic_catalog(),
            )
        )

    def test_gets_context_with_cited_source_details(self) -> None:
        result = self.catalog.get_context(
            "open-v2.density-interpretation"
        )

        self.assertEqual(result["kind"], "context")
        self.assertEqual(
            result["identifier"], "open-v2.density-interpretation"
        )
        self.assertEqual(
            result["context"]["claims"][0]["id"], "coded-feature"
        )
        self.assertEqual(
            set(result["sources"]), {"open-v2.release-schema"}
        )
        self.assertEqual(
            result["sources"]["open-v2.release-schema"]["kind"],
            "release_schema",
        )

    def test_context_results_are_mutation_isolated(self) -> None:
        first = self.catalog.get_context(
            "open-v2.density-interpretation"
        )
        first["context"]["claims"][0]["statement"] = "Changed"
        first["sources"]["open-v2.release-schema"]["title"] = "Changed"

        second = self.catalog.get_context(
            "open-v2.density-interpretation"
        )
        self.assertIn(
            "synthetic density field",
            second["context"]["claims"][0]["statement"],
        )
        self.assertEqual(
            second["sources"]["open-v2.release-schema"]["title"],
            "Synthetic open-v2 release schema",
        )

    def test_searches_context_text_and_returns_matching_claim_sources(
        self,
    ) -> None:
        result = self.catalog.search_contexts("coded exam feature")

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["matches"][0]["identifier"],
            "open-v2.density-interpretation",
        )
        self.assertEqual(
            [
                claim["id"]
                for claim in result["matches"][0]["matching_claims"]
            ],
            ["coded-feature"],
        )
        self.assertEqual(
            set(result["sources"]), {"open-v2.release-schema"}
        )

    def test_searches_contexts_with_every_filter(self) -> None:
        result = self.catalog.search_contexts(
            "",
            kind="interpretation_guardrail",
            scope="profile_specific",
            profile="open-v2",
            domain="mammography",
            concept="exam.tissue_density",
            table="exam_level_anon",
            status="verified",
            source="open-v2.release-schema",
            limit=1,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(
            result["matches"][0]["identifier"],
            "open-v2.density-interpretation",
        )
        self.assertEqual(
            result["filters"],
            {
                "kind": "interpretation_guardrail",
                "scope": "profile_specific",
                "profile": "open-v2",
                "domain": "mammography",
                "concept": "exam.tissue_density",
                "table": "exam_level_anon",
                "relationship": None,
                "status": "verified",
                "source": "open-v2.release-schema",
            },
        )

    def test_context_search_returns_only_matching_claims(self) -> None:
        data = synthetic_catalog()
        context = data["contexts"]["open-v2.density-interpretation"]
        context["claims"].append(
            {
                "id": "unresolved-units",
                "statement": "Synthetic unit semantics remain unresolved.",
                "status": "unresolved",
                "sources": ["open-v2.release-schema"],
                "caveats": ["No unit is asserted."],
            }
        )
        catalog = load_catalog(
            write_catalog(
                Path(self.temporary.name) / "claim-filter.json",
                data,
            )
        )

        by_text = catalog.search_contexts("unit semantics")
        self.assertEqual(
            [
                claim["id"]
                for claim in by_text["matches"][0]["matching_claims"]
            ],
            ["unresolved-units"],
        )

        context_and_claim_text = catalog.search_contexts("density")
        self.assertEqual(
            [
                claim["id"]
                for claim in context_and_claim_text["matches"][0][
                    "matching_claims"
                ]
            ],
            ["coded-feature"],
        )

        context_only_text = catalog.search_contexts("mammography")
        self.assertEqual(
            context_only_text["matches"][0]["matching_claims"],
            [],
        )
        self.assertEqual(context_only_text["sources"], {})

        by_status = catalog.search_contexts("", status="verified")
        self.assertEqual(
            [
                claim["id"]
                for claim in by_status["matches"][0]["matching_claims"]
            ],
            ["coded-feature"],
        )

    def test_context_queries_validate_inputs_and_report_missing(self) -> None:
        with self.assertRaises(CatalogNotFoundError):
            self.catalog.get_context("missing.context")
        with self.assertRaises(CatalogValidationError):
            self.catalog.get_context(" ")
        with self.assertRaises(CatalogValidationError):
            self.catalog.search_contexts("")
        with self.assertRaisesRegex(CatalogValidationError, "unknown kind"):
            self.catalog.search_contexts("", kind="workflow")
        with self.assertRaisesRegex(CatalogValidationError, "unknown concept"):
            self.catalog.search_contexts("", concept="missing.concept")
        with self.assertRaisesRegex(
            CatalogValidationError, "unknown relationship"
        ):
            self.catalog.search_contexts(
                "", relationship="missing.relationship"
            )
        with self.assertRaisesRegex(CatalogValidationError, "unknown source"):
            self.catalog.search_contexts("", source="missing.source")
        with self.assertRaisesRegex(
            CatalogValidationError, "must not contain ':'"
        ):
            self.catalog.search_contexts(
                "", table="open-v2:exam_level_anon"
            )
        with self.assertRaisesRegex(CatalogValidationError, "limit"):
            self.catalog.search_contexts("density", limit=0)
        filtered_punctuation = self.catalog.search_contexts(
            "...", domain="mammography"
        )
        self.assertEqual(filtered_punctuation["total"], 1)

    def relationship_catalog(self):
        data = synthetic_catalog()
        data["relationships"] = [
            {
                "id": "synthetic.wide_density_projection",
                "profile": "open-v2",
                "kind": "projection",
                "source": {
                    "table": "combined_anon",
                    "columns": ["tissueden"],
                    "completeness": "optional",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["tissueden"],
                },
                "cardinality": {
                    "targets_per_source": "unknown",
                    "sources_per_target": "unknown",
                },
                "evidence": ["inference"],
                "caveats": ["Synthetic relationship for query tests."],
                "join_hazards": ["Values are not established as equal."],
            },
            {
                "id": "synthetic.exam_identity_reference",
                "profile": "open-v2",
                "kind": "reference",
                "source": {
                    "table": "exam_level_anon",
                    "columns": ["acc_anon"],
                    "completeness": "required",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["acc_anon"],
                },
                "cardinality": {
                    "targets_per_source": "exactly_one",
                    "sources_per_target": "exactly_one",
                },
                "evidence": ["cross_table_check"],
                "caveats": [],
                "join_hazards": [],
            },
        ]
        return load_catalog(
            write_catalog(
                Path(self.temporary.name) / "relationships.json",
                data,
            )
        )

    def test_gets_table_with_sorted_incident_relationships(self) -> None:
        catalog = self.relationship_catalog()

        result = catalog.get_table("open-v2", "exam_level_anon")

        self.assertEqual(result["kind"], "table")
        self.assertEqual(result["identifier"], "open-v2:exam_level_anon")
        self.assertEqual(
            result["table"],
            {
                "identifier": "open-v2:exam_level_anon",
                "profile": "open-v2",
                "table": "exam_level_anon",
                "grain": "exam",
                "keys": [
                    {
                        "id": "exam.accession",
                        "columns": ["acc_anon"],
                        "kind": "natural",
                        "uniqueness": "unique",
                        "completeness": "complete",
                        "evidence": ["cross_table_check"],
                        "caveats": [],
                    }
                ],
                "caveats": [],
            },
        )
        self.assertEqual(
            [
                relationship["id"]
                for relationship in result["relationships"]["outgoing"]
            ],
            ["synthetic.exam_identity_reference"],
        )
        self.assertEqual(
            [
                relationship["id"]
                for relationship in result["relationships"]["incoming"]
            ],
            [
                "synthetic.exam_identity_reference",
                "synthetic.wide_density_projection",
            ],
        )

    def test_gets_exact_relationship_with_stable_shape(self) -> None:
        catalog = self.relationship_catalog()

        result = catalog.get_relationship(
            "synthetic.wide_density_projection"
        )

        self.assertEqual(result["kind"], "relationship")
        self.assertEqual(
            result["identifier"], "synthetic.wide_density_projection"
        )
        self.assertEqual(
            result["relationship"],
            {
                "id": "synthetic.wide_density_projection",
                "profile": "open-v2",
                "kind": "projection",
                "source": {
                    "table": "combined_anon",
                    "columns": ["tissueden"],
                    "completeness": "optional",
                },
                "target": {
                    "table": "exam_level_anon",
                    "columns": ["tissueden"],
                },
                "cardinality": {
                    "targets_per_source": "unknown",
                    "sources_per_target": "unknown",
                },
                "evidence": ["inference"],
                "caveats": ["Synthetic relationship for query tests."],
                "join_hazards": ["Values are not established as equal."],
            },
        )

    def test_relationship_queries_return_mutation_isolated_results(self) -> None:
        catalog = self.relationship_catalog()
        table = catalog.get_table("open-v2", "exam_level_anon")
        relationship = catalog.get_relationship(
            "synthetic.wide_density_projection"
        )
        search = catalog.search_relationships()

        table["table"]["keys"][0]["columns"][0] = "changed"
        table["relationships"]["incoming"][0]["source"]["columns"][0] = (
            "changed"
        )
        relationship["relationship"]["join_hazards"][0] = "Changed"
        search["matches"][0]["source"]["columns"][0] = "changed"

        fresh_table = catalog.get_table("open-v2", "exam_level_anon")
        fresh_relationship = catalog.get_relationship(
            "synthetic.wide_density_projection"
        )
        fresh_search = catalog.search_relationships()
        self.assertEqual(
            fresh_table["table"]["keys"][0]["columns"], ["acc_anon"]
        )
        self.assertEqual(
            fresh_table["relationships"]["incoming"][0]["source"]["columns"],
            ["acc_anon"],
        )
        self.assertEqual(
            fresh_relationship["relationship"]["join_hazards"],
            ["Values are not established as equal."],
        )
        self.assertEqual(
            fresh_search["matches"][0]["source"]["columns"], ["acc_anon"]
        )

    def test_searches_relationships_with_combined_filters_and_limit(self) -> None:
        catalog = self.relationship_catalog()

        all_relationships = catalog.search_relationships(limit=1)
        self.assertEqual(all_relationships["count"], 1)
        self.assertEqual(all_relationships["total"], 2)
        self.assertEqual(
            all_relationships["matches"][0]["id"],
            "synthetic.exam_identity_reference",
        )
        self.assertEqual(
            all_relationships["filters"],
            {
                "profile": None,
                "table": None,
                "source_table": None,
                "target_table": None,
                "kind": None,
            },
        )

        filtered = catalog.search_relationships(
            profile="open-v2",
            table="exam_level_anon",
            source_table="combined_anon",
            target_table="exam_level_anon",
            kind="projection",
        )
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(
            [match["id"] for match in filtered["matches"]],
            ["synthetic.wide_density_projection"],
        )

        empty = catalog.search_relationships(table="missing_table")
        self.assertEqual(empty["count"], 0)
        self.assertEqual(empty["total"], 0)

    def test_relationship_queries_validate_inputs_and_report_missing(self) -> None:
        catalog = self.relationship_catalog()

        for arguments in (("", "exam_level_anon"), ("open-v2", " ")):
            with self.subTest(arguments=arguments):
                with self.assertRaises(CatalogValidationError):
                    catalog.get_table(*arguments)
        with self.assertRaises(CatalogNotFoundError):
            catalog.get_table("open-v2", "missing_table")
        with self.assertRaises(CatalogValidationError):
            catalog.get_relationship(" ")
        with self.assertRaises(CatalogNotFoundError):
            catalog.get_relationship("missing.relationship")
        with self.assertRaisesRegex(
            CatalogValidationError, "unknown profile"
        ):
            catalog.search_relationships(profile="missing")
        with self.assertRaisesRegex(CatalogValidationError, "unknown kind"):
            catalog.search_relationships(kind="foreign_key")
        for limit in (0, 501, True):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(CatalogValidationError, "limit"):
                    catalog.search_relationships(limit=limit)
        with self.assertRaisesRegex(
            CatalogValidationError, "source_table filter"
        ):
            catalog.search_relationships(source_table=" ")

    def test_gets_exact_concept_and_physical_feature(self) -> None:
        concept = self.catalog.get_feature("exam.tissue_density")
        self.assertEqual(concept["kind"], "concept")
        self.assertEqual(concept["identifier"], "exam.tissue_density")
        self.assertEqual(
            [item["identifier"] for item in concept["bindings"]],
            ["combined_anon.tissueden", "exam_level_anon.tissueden"],
        )
        self.assertNotIn("codes", concept["vocabulary"])

        physical = self.catalog.get_feature(
            "exam_level_anon.tissueden", include_codes=True
        )
        self.assertEqual(physical["kind"], "binding")
        self.assertEqual(
            physical["binding"]["concept"], "exam.tissue_density"
        )
        self.assertEqual(
            physical["vocabulary"]["codes"]["2"],
            "Scattered fibroglandular densities",
        )

    def test_get_result_mutation_does_not_mutate_catalog(self) -> None:
        first = self.catalog.get_feature(
            "exam.tissue_density", include_codes=True
        )
        first["concept"]["label"] = "Changed"
        first["vocabulary"]["codes"]["1"] = "Changed"

        second = self.catalog.get_feature(
            "exam.tissue_density", include_codes=True
        )
        self.assertEqual(second["concept"]["label"], "Breast tissue density")
        self.assertEqual(
            second["vocabulary"]["codes"]["1"], "Almost entirely fat"
        )

    def test_get_rejects_unknown_or_blank_identifier(self) -> None:
        with self.assertRaises(CatalogNotFoundError):
            self.catalog.get_feature("missing.feature")
        with self.assertRaises(CatalogValidationError):
            self.catalog.get_feature(" ")

    def test_looks_up_exact_code_through_all_target_forms(self) -> None:
        for target in (
            "exam.tissue_density",
            "exam_level_anon.tissueden",
        ):
            with self.subTest(target=target):
                result = self.catalog.lookup_code(target, "2")
                self.assertEqual(
                    result["meaning"], "Scattered fibroglandular densities"
                )
                self.assertEqual(result["vocabulary"], "exam.tissue_density")

        direct = self.catalog.lookup_code("exam.tissue_density", "1")
        self.assertEqual(direct["meaning"], "Almost entirely fat")
        self.assertEqual(direct["concept"], "exam.tissue_density")

    def test_code_lookup_is_exact_and_requires_a_vocabulary(self) -> None:
        with self.assertRaises(CatalogNotFoundError):
            self.catalog.lookup_code("exam.tissue_density", "01")
        with self.assertRaisesRegex(CatalogNotFoundError, "no vocabulary"):
            self.catalog.lookup_code("identity.accession", "1")

    def test_search_is_casefolded_weighted_and_deterministic(self) -> None:
        exact = self.catalog.search_features(
            "EXAM_LEVEL_ANON.TISSUEDEN", limit=3
        )
        self.assertEqual(
            exact["matches"][0]["identifier"], "exam.tissue_density"
        )
        self.assertEqual(exact["total"], 1)
        self.assertEqual(
            [binding["identifier"] for binding in exact["matches"][0]["bindings"]],
            ["exam_level_anon.tissueden"],
        )

        vocabulary_text = self.catalog.search_features(
            "SCATTERED densities", limit=3
        )
        self.assertEqual(vocabulary_text["total"], 1)
        self.assertEqual(
            [item["identifier"] for item in vocabulary_text["matches"]],
            ["exam.tissue_density"],
        )

        compact_identifier = self.catalog.search_features("TissueDen")
        self.assertEqual(compact_identifier["total"], 1)
        self.assertEqual(
            compact_identifier["matches"][0]["identifier"],
            "exam.tissue_density",
        )

    def test_search_applies_every_filter(self) -> None:
        result = self.catalog.search_features(
            "",
            profile="open-v2",
            table="exam_level_anon",
            grain="exam",
            domain="mammography",
            feature_kind="coded",
            limit=10,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(
            result["matches"][0]["identifier"], "exam.tissue_density"
        )
        self.assertEqual(
            [item["identifier"] for item in result["matches"][0]["bindings"]],
            ["exam_level_anon.tissueden"],
        )
        self.assertEqual(
            result["filters"],
            {
                "profile": "open-v2",
                "table": "exam_level_anon",
                "grain": "exam",
                "domain": "mammography",
                "feature_kind": "coded",
            },
        )

    def test_search_validates_query_filters_and_limit(self) -> None:
        with self.assertRaises(CatalogValidationError):
            self.catalog.search_features("")
        with self.assertRaisesRegex(CatalogValidationError, "unknown grain"):
            self.catalog.search_features("density", grain="row")
        with self.assertRaisesRegex(CatalogValidationError, "limit"):
            self.catalog.search_features("density", limit=0)
        with self.assertRaisesRegex(
            CatalogValidationError, "meaningful token"
        ):
            self.catalog.search_features("... !!!")

    def test_search_uses_token_overlap_and_ignores_prompt_stopwords(self) -> None:
        result = self.catalog.search_features(
            "show everything relevant to density"
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(
            result["matches"][0]["identifier"], "exam.tissue_density"
        )

        filtered = self.catalog.search_features(
            "...", table="exam_level_anon"
        )
        self.assertEqual(filtered["total"], 2)

    def test_search_normalizes_plurals_and_falls_back_to_partial_overlap(self) -> None:
        plural = self.catalog.search_features("breast densities")
        self.assertEqual(plural["total"], 1)
        self.assertEqual(
            plural["matches"][0]["identifier"], "exam.tissue_density"
        )

        fallback = self.catalog.search_features("density accession")
        self.assertEqual(
            {
                match["identifier"] for match in fallback["matches"]
            },
            {"exam.tissue_density", "identity.accession"},
        )

    def test_search_deduplicates_concepts_across_profiles(self) -> None:
        data = synthetic_catalog()
        data["profiles"].append("future")
        future = copy.deepcopy(data["bindings"][0])
        future["profile"] = "future"
        data["bindings"].append(future)
        future_table = copy.deepcopy(data["tables"][1])
        future_table["profile"] = "future"
        future_table["keys"] = []
        data["tables"].append(future_table)
        catalog = load_catalog(
            write_catalog(
                Path(self.temporary.name) / "profiles.json",
                data,
            )
        )

        result = catalog.search_features("density")
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["matches"][0]["bindings"]), 3)

        filtered = catalog.search_features("density", profile="future")
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(
            [item["profile"] for item in filtered["matches"][0]["bindings"]],
            ["future"],
        )


if __name__ == "__main__":
    unittest.main()
