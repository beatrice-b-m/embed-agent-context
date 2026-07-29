#!/usr/bin/env python3
"""Verify a catalog profile against Parquet footer schemas.

The verifier derives its complete expected manifest from the selected profile's
catalog bindings. It opens Parquet footers for Arrow schemas only; it does not
read row groups, data pages, statistics, or clinical values.
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
    # Keep direct ``python scripts/...`` execution working in an uninstalled
    # repository; the project intentionally has no packaged runtime.
    sys.path.insert(0, str(REPO_ROOT))

from embed_context import Catalog, CatalogError, load_catalog


DEFAULT_CATALOG = REPO_ROOT / "catalog/catalog.json"
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
    seen: set[tuple[str, str]] = set()
    selected = False
    for binding in catalog.bindings:
        if binding.profile != profile:
            continue
        selected = True

        table = binding.table
        column = binding.column
        if not SAFE_TABLE_NAME.fullmatch(table):
            raise ProfileValidationError(
                f"binding has an unsafe table name: {table!r}"
            )

        key = (table, column)
        if key in seen:
            raise ProfileValidationError(
                f"duplicate binding for profile {profile}: {table}.{column}"
            )
        seen.add(key)
        expected.setdefault(table, {})[column] = ExpectedColumn(
            physical_type=binding.physical_type,
            nullable=binding.nullable,
        )

    if not selected:
        raise ProfileValidationError(
            f"catalog profile has no physical bindings: {profile}"
        )
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
    parquet_entries = [
        entry for entry in directory.iterdir() if entry.suffix == ".parquet"
    ]
    for entry in parquet_entries:
        if entry.is_symlink():
            raise ProfileValidationError(
                f"release table must not be a symlink: {entry}"
            )
        if not entry.is_file():
            raise ProfileValidationError(
                f"release table is not a regular file: {entry}"
            )

    expected_names = {f"{table}.parquet" for table in expected_tables}
    actual_names = {entry.name for entry in parquet_entries}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ProfileValidationError(
            f"Parquet manifest mismatch; missing={missing}, extra={extra}"
        )

    paths: dict[str, Path] = {}
    for table in sorted(expected_tables):
        candidate = directory / f"{table}.parquet"
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ProfileValidationError(
                f"cannot resolve release table: {candidate}"
            ) from exc
        if resolved.parent != directory:
            raise ProfileValidationError(
                f"release table escapes its directory: {candidate}"
            )
        if not resolved.is_file():
            raise ProfileValidationError(
                f"release table is not a regular file: {candidate}"
            )
        paths[table] = resolved
    return paths


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
        help="feature catalog JSON path",
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
