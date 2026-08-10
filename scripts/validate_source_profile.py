#!/usr/bin/env python3
"""Verify one profile's physical column inventory against Parquet footers.

The verifier derives its complete expected manifest from the selected profile's
table and column declarations. Semantic mappings, clinical objects, and
relationships remain independent of this storage check. The verifier opens
Parquet footers for Arrow schemas only; it does not read row groups, data pages,
statistics, or clinical values.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    # Keep direct ``python scripts/...`` execution working from a source
    # checkout even when the package has not been installed in this environment.
    sys.path.insert(0, str(REPO_ROOT))

from embed_context import Catalog, CatalogError, load_catalog


DEFAULT_CATALOG = REPO_ROOT / "catalog/catalog-set.json"
DEFAULT_TABLES = REPO_ROOT / "reference_files/clinical_tables"
SAFE_TABLE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


class ProfileValidationError(ValueError):
    """Raised when catalog bindings and source schemas do not agree."""


@dataclass(frozen=True)
class ExpectedColumn:
    physical_type: str
    nullable: bool


def _require_regular_file(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise ProfileValidationError(f"{label} must not be a symlink: {path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ProfileValidationError(f"{label} does not exist: {path}") from exc
    if not resolved.is_file():
        raise ProfileValidationError(f"{label} is not a regular file: {path}")
    return resolved


def _load_catalog(path: Path) -> Catalog:
    resolved = _require_regular_file(path, label="catalog")
    try:
        return load_catalog(resolved)
    except CatalogError as exc:
        raise ProfileValidationError(f"invalid catalog: {exc}") from exc


def expected_profile_schema(
    catalog_path: Path, profile: str
) -> dict[str, dict[str, ExpectedColumn]]:
    """Return the table/column schema declared by one catalog profile."""

    catalog = _load_catalog(catalog_path)
    if profile not in catalog.profiles:
        raise ProfileValidationError(f"unknown catalog profile: {profile}")

    expected: dict[str, dict[str, ExpectedColumn]] = {}
    profile_binding = catalog.profile_bindings[profile]
    if not profile_binding.tables:
        raise ProfileValidationError(
            f"selected profile {profile!r} has no physical tables to verify"
        )
    for table_spec in profile_binding.tables:
        table = table_spec.table
        if not SAFE_TABLE_NAME.fullmatch(table):
            raise ProfileValidationError(
                f"table declaration has an unsafe table name: {table!r}"
            )
        columns: dict[str, ExpectedColumn] = {}
        for column in table_spec.columns:
            columns[column.name] = ExpectedColumn(
                physical_type=column.physical_type,
                nullable=column.nullable,
            )
        expected[table] = columns

    return expected


def _secure_table_directory(path: Path) -> Path:
    if path.is_symlink():
        raise ProfileValidationError(
            f"table directory must not be a symlink: {path}"
        )
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ProfileValidationError(
            f"table directory does not exist: {path}"
        ) from exc
    if not resolved.is_dir():
        raise ProfileValidationError(
            f"table path is not a directory: {path}"
        )
    return resolved


def exact_table_paths(
    table_directory: Path, expected_tables: set[str]
) -> dict[str, Path]:
    """Resolve an exact, direct-child Parquet manifest without following links."""

    directory = _secure_table_directory(table_directory)
    parquet_entries: dict[str, Path] = {}
    for entry in directory.iterdir():
        if entry.suffix != ".parquet":
            continue
        if entry.is_symlink():
            raise ProfileValidationError(
                f"release table must not be a symlink: {entry}"
            )
        if not entry.is_file():
            raise ProfileValidationError(
                f"release table is not a regular file: {entry}"
            )
        parquet_entries[entry.name] = entry

    expected_names = {f"{table}.parquet" for table in expected_tables}
    actual_names = set(parquet_entries)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ProfileValidationError(
            f"Parquet manifest mismatch; missing={missing}, extra={extra}"
        )

    return {
        table: parquet_entries[f"{table}.parquet"].resolve()
        for table in sorted(expected_tables)
    }


def _table_schema_errors(
    table: str,
    path: Path,
    expected: dict[str, ExpectedColumn],
) -> list[str]:
    try:
        schema = pq.ParquetFile(path).schema_arrow
    except (OSError, ValueError) as exc:
        raise ProfileValidationError(
            f"cannot read Parquet footer for {table}: {exc}"
        ) from exc

    actual = {field.name: field for field in schema}
    expected_names = set(expected)
    actual_names = set(actual)
    errors: list[str] = []
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra:
        errors.append(
            f"{table} column manifest mismatch; missing={missing}, extra={extra}"
        )

    for column in sorted(expected_names & actual_names):
        declared = expected[column]
        field = actual[column]
        physical_type = str(field.type)
        if physical_type != declared.physical_type:
            errors.append(
                f"{table}.{column} physical type mismatch; "
                f"catalog={declared.physical_type!r}, source={physical_type!r}"
            )
        if field.nullable != declared.nullable:
            errors.append(
                f"{table}.{column} nullable mismatch; "
                f"catalog={declared.nullable}, source={field.nullable}"
            )
    return errors


def validate_source_profile(
    catalog_path: Path,
    table_directory: Path,
    profile: str,
) -> None:
    """Validate the selected catalog profile against source Parquet footers."""

    expected = expected_profile_schema(catalog_path, profile)
    paths = exact_table_paths(table_directory, set(expected))
    errors: list[str] = []
    for table in sorted(expected):
        errors.extend(_table_schema_errors(table, paths[table], expected[table]))
    if errors:
        raise ProfileValidationError("\n".join(errors))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=(
            "catalog-set manifest path (default: catalog/catalog-set.json)"
        ),
    )
    parser.add_argument(
        "--tables",
        type=Path,
        default=DEFAULT_TABLES,
        help="directory containing the selected profile's Parquet tables",
    )
    parser.add_argument(
        "--profile",
        default="open-v2",
        help="catalog profile to verify",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_source_profile(args.catalog, args.tables, args.profile)
    except ProfileValidationError as exc:
        print(f"source profile validation error: {exc}", file=sys.stderr)
        return 1
    print(f"source profile {args.profile!r} matches catalog bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
