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
        self.catalog_path = self.root / "catalog-set.json"
        self.semantic_path = self.root / "semantic.json"
        self.table_directory = self.root / "tables"
        self.table_directory.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def column(
        table: str,
        name: str,
        physical_type: str,
        nullable: bool,
        *,
        profile: str = "sample",
    ) -> dict[str, Any]:
        return {
            "profile": profile,
            "table": table,
            "name": name,
            "physical_type": physical_type,
            "nullable": nullable,
        }

    def write_catalog(
        self,
        columns: list[dict[str, Any]],
        *,
        profiles: list[str] | None = None,
        mappings: list[dict[str, Any]] | None = None,
    ) -> None:
        selected_profiles = profiles or ["sample"]
        profile_locators = []
        for profile in selected_profiles:
            profile_columns = [
                column for column in columns if column["profile"] == profile
            ]
            profile_mappings = mappings
            if profile_mappings is None:
                profile_mappings = [
                    {
                        "id": f"{profile}.binding.feature.{index}",
                        "table": column["table"],
                        "column": column["name"],
                        "concept": "synthetic.feature",
                        "status": "direct",
                    }
                    for index, column in enumerate(profile_columns)
                ]
            tables = []
            for table_index, table in enumerate(
                sorted({column["table"] for column in profile_columns})
            ):
                physical_columns = [
                    {
                        key: value
                        for key, value in column.items()
                        if key in {"name", "physical_type", "nullable"}
                    }
                    for column in profile_columns
                    if column["table"] == table
                ]
                tables.append(
                    {
                        "id": f"{profile}.binding.table.{table_index}",
                        "table": table,
                        "grain": "one synthetic exam row",
                        "columns": physical_columns,
                        "keys": [],
                        "caveats": [],
                    }
                )
            profile_path = self.root / f"{profile}.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "$schema": "./profile.schema.json",
                        "profile_schema_version": 2,
                        "profile": {"id": profile, "label": profile.title()},
                        "requires": {"semantic_schema_version": 8},
                        "contributions": {
                            "clinical_objects": {},
                            "concepts": {},
                            "semantic_relationships": {},
                            "temporal_semantics": {},
                            "aggregations": {},
                            "guardrails": {},
                            "coverage": {},
                        },
                        "sources": {},
                        "contexts": {},
                        "qualifications": {},
                        "vocabularies": {},
                        "profile_binding": {
                            "feature_bindings": profile_mappings,
                            "object_bindings": [],
                            "tables": tables,
                            "relationship_bindings": [],
                            "relationship_binding_paths": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile_locators.append({"kind": "file", "path": profile_path.name})

        self.semantic_path.write_text(
            json.dumps(
                {
                    "$schema": "./catalog.schema.json",
                    "semantic_schema_version": 8,
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
                }
            ),
            encoding="utf-8",
        )
        self.catalog_path.write_text(
            json.dumps(
                {
                    "$schema": "./catalog-set.schema.json",
                    "catalog_set_schema_version": 1,
                    "semantic_catalog": {
                        "kind": "file",
                        "path": self.semantic_path.name,
                    },
                    "profiles": profile_locators,
                    "extensions": [],
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

    def valid_columns(self) -> list[dict[str, Any]]:
        return [
            self.column("alpha", "identifier", "int64", False),
            self.column("alpha", "label", "string", True),
            self.column("beta", "event_time", "timestamp[ns]", True),
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
        self.write_catalog(self.valid_columns())
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
        self.write_catalog(self.valid_columns())
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
        self.write_catalog(self.valid_columns())
        self.write_valid_tables()
        self.write_schema("extra", [("value", pa.int8(), True)])

        with self.assertRaisesRegex(
            ProfileValidationError, "Parquet manifest mismatch.*extra.parquet"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_physical_type_mismatch_is_rejected(self) -> None:
        columns = [self.column("alpha", "value", "int64", True)]
        self.write_catalog(columns)
        self.write_schema("alpha", [("value", pa.string(), True)])

        with self.assertRaisesRegex(
            ProfileValidationError, "physical type mismatch"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_column_manifest_mismatch_is_rejected(self) -> None:
        columns = [self.column("alpha", "expected", "string", True)]
        self.write_catalog(columns)
        self.write_schema("alpha", [("unexpected", pa.string(), True)])

        with self.assertRaisesRegex(
            ProfileValidationError, "column manifest mismatch"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_nullable_mismatch_is_rejected(self) -> None:
        columns = [self.column("alpha", "value", "int64", False)]
        self.write_catalog(columns)
        self.write_schema("alpha", [("value", pa.int64(), True)])

        with self.assertRaisesRegex(ProfileValidationError, "nullable mismatch"):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_unmapped_and_multiply_mapped_columns_are_verified_once(self) -> None:
        columns = [
            self.column("alpha", "unmapped", "string", True),
            self.column("alpha", "shared", "int64", False),
        ]
        self.write_catalog(
            columns,
            mappings=[
                {
                    "id": "sample.binding.feature.shared.direct",
                    "table": "alpha",
                    "column": "shared",
                    "concept": "synthetic.feature",
                    "status": "direct",
                },
                {
                    "id": "sample.binding.feature.shared.conditional",
                    "table": "alpha",
                    "column": "shared",
                    "concept": "synthetic.feature",
                    "status": "conditional",
                },
            ],
        )
        self.write_schema(
            "alpha",
            [("unmapped", pa.string(), True), ("shared", pa.int64(), False)],
        )

        validate_source_profile(self.catalog_path, self.table_directory, "sample")

    def test_invalid_catalog_is_rejected_before_footer_comparison(self) -> None:
        self.write_catalog(self.valid_columns())
        document = json.loads(self.semantic_path.read_text(encoding="utf-8"))
        document["concepts"]["synthetic.feature"]["row_count"] = 1
        self.semantic_path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaisesRegex(
            ProfileValidationError,
            "invalid catalog.*Additional properties are not allowed",
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    def test_unknown_profile_is_rejected(self) -> None:
        self.write_catalog(self.valid_columns())

        with self.assertRaisesRegex(
            ProfileValidationError, "unknown catalog profile"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "other"
            )

    def test_profile_without_bindings_is_rejected(self) -> None:
        self.write_catalog(self.valid_columns(), profiles=["sample", "empty"])

        with self.assertRaisesRegex(
            ProfileValidationError, "has no physical tables to verify"
        ):
            validate_source_profile(
                self.catalog_path, self.table_directory, "empty"
            )

    def test_unsafe_catalog_table_name_is_rejected(self) -> None:
        columns = [self.column("../escape", "value", "int64", True)]
        self.write_catalog(columns)

        with self.assertRaisesRegex(ProfileValidationError, "unsafe table name"):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_table_is_rejected(self) -> None:
        columns = [self.column("alpha", "value", "int64", True)]
        self.write_catalog(columns)
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
        columns = [self.column("alpha", "value", "int64", True)]
        self.write_catalog(columns)
        (self.table_directory / "alpha.parquet").mkdir()

        with self.assertRaisesRegex(ProfileValidationError, "not a regular file"):
            validate_source_profile(
                self.catalog_path, self.table_directory, "sample"
            )


if __name__ == "__main__":
    unittest.main()
