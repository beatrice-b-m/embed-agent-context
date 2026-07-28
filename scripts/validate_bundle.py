#!/usr/bin/env python3
"""Validate bundle navigation and physical-column coverage.

This verifier reads schemas from the footers of an explicit eight-file
manifest. It does not open Parquet data pages, inspect value statistics, or
read the release legend.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from pathlib import Path

import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_TABLES = (
    "combined_anon",
    "exam_level_anon",
    "imaging_findings_anon",
    "pathology_findings_anon",
    "patients_anon",
    "reports_anon",
    "risk_anon",
    "side_level_anon",
)
EXPECTED_OCCURRENCES = 243

CODE_SPAN = re.compile(r"`([^`\n]+)`")
INLINE_LINK = re.compile(r"\[[^\]]+\]\((<[^>]+>|[^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


def exact_release_paths(table_dir: Path) -> list[Path]:
    table_dir = table_dir.resolve(strict=True)
    if not table_dir.is_dir():
        raise ValueError(f"table path is not a directory: {table_dir}")

    actual = {path.name for path in table_dir.iterdir() if path.suffix == ".parquet"}
    required = {f"{table}.parquet" for table in RELEASE_TABLES}
    if actual != required:
        missing = sorted(required - actual)
        extra = sorted(actual - required)
        raise ValueError(f"release table manifest mismatch; missing={missing}, extra={extra}")

    paths: list[Path] = []
    for name in sorted(required):
        path = table_dir / name
        if path.is_symlink():
            raise ValueError(f"release table must not be a symlink: {path}")
        resolved = path.resolve(strict=True)
        if resolved.parent != table_dir or not resolved.is_file():
            raise ValueError(f"release table escapes its directory: {path}")
        paths.append(resolved)
    return paths


def expected_columns(table_dir: Path) -> set[str]:
    expected: set[str] = set()
    for path in exact_release_paths(table_dir):
        table = path.stem
        schema = pq.ParquetFile(path).schema_arrow
        expected.update(f"{table}.{field.name}" for field in schema)
    if len(expected) != EXPECTED_OCCURRENCES:
        raise ValueError(
            f"release schema drift: expected {EXPECTED_OCCURRENCES} occurrences, "
            f"found {len(expected)}"
        )
    return expected


def bundle_texts(bundle_dir: Path) -> dict[Path, str]:
    bundle_dir = bundle_dir.resolve(strict=True)
    if not bundle_dir.is_dir():
        raise ValueError(f"bundle path is not a directory: {bundle_dir}")

    paths = sorted(bundle_dir.rglob("*.md"))
    if any(path.parent != bundle_dir for path in paths):
        raise ValueError("nested Markdown documents are not supported in the bundle")
    for path in paths:
        if path.is_symlink() or path.resolve().parent != bundle_dir:
            raise ValueError(f"bundle document must not be a symlink: {path}")

    texts = {path.resolve(): path.read_text(encoding="utf-8") for path in paths}
    entry = (bundle_dir / "README.md").resolve()
    if entry not in texts:
        raise ValueError(f"missing bundle entry point: {entry}")
    return texts


def github_slug(heading: str) -> str:
    heading = re.sub(r"[`*_~]", "", heading).strip().lower()
    heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
    return re.sub(r"-+", "-", heading.replace(" ", "-"))


def heading_slugs(text: str) -> set[str]:
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    for heading in HEADING.findall(text):
        base = github_slug(heading)
        number = counts.get(base, 0)
        counts[base] = number + 1
        slugs.add(base if number == 0 else f"{base}-{number}")
    return slugs


def local_targets(source: Path, text: str) -> list[tuple[Path, str, str]]:
    targets: list[tuple[Path, str, str]] = []
    for raw in INLINE_LINK.findall(text):
        target_text = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target_text):
            continue
        path_text, separator, fragment = target_text.partition("#")
        target = source if not path_text else (source.parent / path_text).resolve()
        targets.append((target, fragment if separator else "", target_text))
    return targets


def validate_links(texts: dict[Path, str], bundle_dir: Path) -> list[str]:
    bundle_dir = bundle_dir.resolve()
    errors: list[str] = []
    graph: dict[Path, set[Path]] = {path: set() for path in texts}
    slugs = {path: heading_slugs(text) for path, text in texts.items()}

    for source, text in texts.items():
        for target, fragment, target_text in local_targets(source, text):
            try:
                target.relative_to(bundle_dir)
            except ValueError:
                errors.append(f"local link escapes bundle in {source}: {target_text}")
                continue
            if target not in texts:
                errors.append(f"broken local link in {source}: {target_text}")
                continue
            graph[source].add(target)
            if fragment and fragment not in slugs[target]:
                errors.append(f"broken heading fragment in {source}: {target_text}")

    entry = (bundle_dir / "README.md").resolve()
    reached = {entry}
    queue = deque([entry])
    while queue:
        for target in graph[queue.popleft()]:
            if target not in reached:
                reached.add(target)
                queue.append(target)
    for unreachable in sorted(set(texts) - reached):
        errors.append(f"bundle document is not reachable from README.md: {unreachable.name}")
    return errors


def table_code_spans(text: str) -> set[str]:
    found: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.lstrip().startswith("|"):
            found.update(CODE_SPAN.findall(line))
    return found


def validate_coverage(
    expected: set[str], texts: dict[Path, str]
) -> tuple[list[str], list[str]]:
    table_spans = {span for text in texts.values() for span in table_code_spans(text)}
    found = expected & table_spans
    known_prefixes = tuple(f"{table}." for table in RELEASE_TABLES)
    unexpected = sorted(
        span
        for span in table_spans - expected
        if span.startswith(known_prefixes)
    )
    return sorted(expected - found), unexpected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tables",
        type=Path,
        default=REPO_ROOT / "reference_files/clinical_tables",
        help="directory containing the exact eight-file release manifest",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=REPO_ROOT / "bundle",
        help="flat directory containing the Markdown bundle",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        expected = expected_columns(args.tables)
        texts = bundle_texts(args.bundle)
    except (OSError, ValueError) as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2

    errors = validate_links(texts, args.bundle)
    missing, unexpected = validate_coverage(expected, texts)
    if missing:
        errors.append(
            "physical occurrences missing from Markdown table cells:\n  "
            + "\n  ".join(missing)
        )
    if unexpected:
        errors.append(
            "qualified table-cell names not present in release schemas:\n  "
            + "\n  ".join(unexpected)
        )

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(
        f"validated {len(expected)} physical column occurrences "
        f"across {len(texts)} reachable bundle documents"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
