"""Focused tests for the footer-only source-profile verifier."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from embed_context.catalog import (
    AGGREGATION_STATUSES,
    BINDING_GRAINS,
    CLAIM_STATUSES,
    CONTEXT_KINDS,
    CONTEXT_SCOPES,
    COVERAGE_STATUSES,
    DOMAINS,
    FEATURE_KINDS,
    SEMANTIC_RELATIONSHIP_KINDS,
    SOURCE_KINDS,
    SOURCE_LOCATOR_KINDS,
    TEMPORAL_KINDS,
)
from scripts.validate_source_profile import (
    DEFAULT_CATALOG,
    ProfileValidationError,
    main,
    parse_args,
    validate_source_profile,
)


class SourceProfileVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.catalog_path = self.root / "catalog.json"
        self.table_directory = self.root / "tables"
        self.table_directory.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def binding(
        table: str,
        column: str,
        physical_type: str,
        nullable: bool,
        *,
        profile: str = "sample",
    ) -> dict[str, Any]:
        return {
            "profile": profile,
            "table": table,
            "column": column,
            "concept": "synthetic.feature",
            "grain": "exam",
            "role": "canonical",
            "physical_type": physical_type,
            "nullable": nullable,
        }

    def write_catalog(
        self,
        bindings: list[dict[str, Any]],
        *,
        profiles: list[str] | None = None,
    ) -> None:
        selected_profiles = profiles or ["sample"]
        profile_bindings = {}
        for profile in selected_profiles:
            profile_features = [
                {
                    key: value
                    for key, value in binding.items()
                    if key != "profile"
                }
                for binding in bindings
                if binding["profile"] == profile
            ]
            profile_bindings[profile] = {
                "feature_bindings": profile_features,
                "object_bindings": [],
                "tables": [
                    {
                        "table": table,
                        "grain": "exam",
                        "keys": [],
                        "caveats": [],
                    }
                    for table in sorted(
                        {binding["table"] for binding in profile_features}
                    )
                ],
                "relationship_bindings": [],
                "relationship_binding_paths": [],
            }
        self.catalog_path.write_text(
            json.dumps(
                {
                    "$schema": "./catalog.schema.json",
                    "schema_version": 6,
                    "profiles": selected_profiles,
                    "binding_grains": list(BINDING_GRAINS),
                    "feature_kinds": list(FEATURE_KINDS),
                    "domains": list(DOMAINS),
                    "context_kinds": list(CONTEXT_KINDS),
                    "context_scopes": list(CONTEXT_SCOPES),
                    "source_kinds": list(SOURCE_KINDS),
                    "source_locator_kinds": list(SOURCE_LOCATOR_KINDS),
                    "claim_statuses": list(CLAIM_STATUSES),
                    "semantic_relationship_kinds": list(
                        SEMANTIC_RELATIONSHIP_KINDS
                    ),
                    "temporal_kinds": list(TEMPORAL_KINDS),
                    "aggregation_statuses": list(AGGREGATION_STATUSES),
                    "coverage_statuses": list(COVERAGE_STATUSES),
                    "clinical_objects": {
                        "exam": {
                            "label": "Exam",
                            "definition": "One represented examination.",
                            "grain": "One exam.",
                            "domains": ["exam"],
                            "search_terms": ["exam"],
                            "claim_refs": [],
                            "caveats": [],
                        }
                    },
                    "concepts": {
                        "synthetic.feature": {
                            "label": "Synthetic feature",
                            "definition": "Feature used only for verifier tests.",
                            "feature_kind": "numeric",
                            "domains": ["technical"],
                            "objects": ["exam"],
                            "search_terms": ["synthetic"],
                            "caveats": [],
                            "evidence": ["release_schema"],
                        }
                    },
                    "semantic_relationships": {},
                    "temporal_semantics": {},
                    "aggregations": {},
                    "guardrails": {},
                    "coverage": {},
                    "vocabularies": {},
                    "sources": {},
                    "contexts": {},
                    "profile_bindings": profile_bindings,
                }
            ),
            encoding="utf-8",
        )

    def write_schema(
        self,
        table: str,
        fields: list[tuple[str, pa.DataType, bool]],
        *,
        directory: Path | None = None,
    ) -> Path:
        target_directory = directory or self.table_directory
        path = target_directory / f"{table}.parquet"
        schema = pa.schema(
            [
                pa.field(name, physical_type, nullable=nullable)
                for name, physical_type, nullable in fields
            ]
        )
        pq.write_metadata(schema, path)
        return path

    def valid_bindings(self) -> list[dict[str, Any]]:
        return [
            self.binding("alpha", "identifier", "int64", False),
            self.binding("alpha", "label", "string", True),
            self.binding("beta", "event_time", "timestamp[ns]", True),
        ]

    def test_default_catalog_is_the_canonical_catalog_set_manifest(self) -> None:
        args = parse_args([])
        self.assertEqual(args.catalog, DEFAULT_CATALOG)
        self.assertEqual(
            DEFAULT_CATALOG,
            Path(__file__).resolve().parents[1] / "catalog/catalog-set.json",
        )

    def write_valid_tables(self) -> None:
        self.write_schema(
            "alpha",
            [
                ("identifier", pa.int64(), False),
                ("label", pa.string(), True),
            ],
        )
        self.write_schema(
            "beta",
            [("event_time", pa.timestamp("ns"), True)],
        )

    def test_success_uses_count_free_message(self) -> None:
        self.write_catalog(self.valid_bindings())
        self.write_valid_tables()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(
                [
                    "--catalog",
                    str(self.catalog_path),
                    "--tables",
                    str(self.table_directory),
                    "--profile",
                    "sample",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            stdout.getvalue(),
            "source profile 'sample' matches catalog bindings\n",
        )
        self.assertEqual(stderr.getvalue(), "")
        self.assertFalse(any(character.isdigit() for character in stdout.getvalue()))

    def test_missing_table_is_rejected(self) -> None:
        self.write_catalog(self.valid_bindings())
        self.write_schema(
            "alpha",
            [
                ("identifier", pa.int64(), False),
                ("label", pa.string(), True),
            ],
        )

        with self.assertRaisesRegex(
            ProfileValidationError, "Parquet manifest mismatch.*beta.parquet"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_extra_table_is_rejected(self) -> None:
        self.write_catalog(self.valid_bindings())
        self.write_valid_tables()
        self.write_schema("extra", [("value", pa.int8(), True)])

        with self.assertRaisesRegex(
            ProfileValidationError, "Parquet manifest mismatch.*extra.parquet"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_physical_type_mismatch_is_rejected(self) -> None:
        bindings = [self.binding("alpha", "value", "int64", True)]
        self.write_catalog(bindings)
        self.write_schema("alpha", [("value", pa.string(), True)])

        with self.assertRaisesRegex(
            ProfileValidationError, "physical type mismatch"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_column_manifest_mismatch_is_rejected(self) -> None:
        bindings = [self.binding("alpha", "expected", "string", True)]
        self.write_catalog(bindings)
        self.write_schema("alpha", [("unexpected", pa.string(), True)])

        with self.assertRaisesRegex(
            ProfileValidationError, "column manifest mismatch"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_nullable_mismatch_is_rejected(self) -> None:
        bindings = [self.binding("alpha", "value", "int64", False)]
        self.write_catalog(bindings)
        self.write_schema("alpha", [("value", pa.int64(), True)])

        with self.assertRaisesRegex(ProfileValidationError, "nullable mismatch"):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_duplicate_binding_is_rejected(self) -> None:
        duplicate = self.binding("alpha", "value", "int64", True)
        self.write_catalog([duplicate, dict(duplicate)])

        with self.assertRaisesRegex(
            ProfileValidationError, "duplicate physical binding"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_invalid_catalog_is_rejected_before_footer_comparison(self) -> None:
        self.write_catalog(self.valid_bindings())
        document = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        document["concepts"]["synthetic.feature"]["row_count"] = 1
        self.catalog_path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaisesRegex(
            ProfileValidationError,
            "invalid catalog.*Additional properties are not allowed",
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_unknown_profile_is_rejected(self) -> None:
        self.write_catalog(self.valid_bindings())

        with self.assertRaisesRegex(
            ProfileValidationError, "unknown catalog profile"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "other"
            )

    def test_profile_without_bindings_is_rejected(self) -> None:
        self.write_catalog(self.valid_bindings(), profiles=["sample", "empty"])

        with self.assertRaisesRegex(
            ProfileValidationError, "invalid catalog.*should be non-empty"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "empty"
            )

    def test_unsafe_catalog_table_name_is_rejected(self) -> None:
        bindings = [self.binding("../escape", "value", "int64", True)]
        self.write_catalog(bindings)

        with self.assertRaisesRegex(ProfileValidationError, "unsafe table name"):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_table_is_rejected(self) -> None:
        bindings = [self.binding("alpha", "value", "int64", True)]
        self.write_catalog(bindings)
        outside = self.write_schema(
            "outside",
            [("value", pa.int64(), True)],
            directory=self.root,
        )
        (self.table_directory / "alpha.parquet").symlink_to(outside)

        with self.assertRaisesRegex(ProfileValidationError, "must not be a symlink"):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_parquet_named_directory_is_rejected(self) -> None:
        bindings = [self.binding("alpha", "value", "int64", True)]
        self.write_catalog(bindings)
        (self.table_directory / "alpha.parquet").mkdir()

        with self.assertRaisesRegex(ProfileValidationError, "not a regular file"):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )


if __name__ == "__main__":
    unittest.main()
