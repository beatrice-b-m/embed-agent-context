"""Command-line access to the EMBED V2 feature catalog."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .catalog import (
    DOMAINS,
    FEATURE_KINDS,
    GRAINS,
    CatalogError,
    load_catalog,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        help="catalog JSON path; defaults to repository catalog/catalog.json",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate and summarize the catalog")

    get_parser = subparsers.add_parser(
        "get",
        help="get a concept ID, table.column, or profile:table.column feature",
    )
    get_parser.add_argument("identifier")
    get_parser.add_argument(
        "--include-codes",
        action="store_true",
        help="include the complete code map when a vocabulary is attached",
    )

    search_parser = subparsers.add_parser("search", help="search concepts")
    search_parser.add_argument("query", nargs="?", default="")
    search_parser.add_argument("--profile")
    search_parser.add_argument("--table")
    search_parser.add_argument("--grain", choices=GRAINS)
    search_parser.add_argument("--domain", choices=DOMAINS)
    search_parser.add_argument("--feature-kind", choices=FEATURE_KINDS)
    search_parser.add_argument("--limit", type=int, default=50)

    code_parser = subparsers.add_parser("code", help="look up an exact code")
    code_parser.add_argument("feature_or_vocabulary")
    code_parser.add_argument("code")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        if args.command == "validate":
            data = catalog.summary()
        elif args.command == "get":
            data = catalog.get_feature(
                args.identifier, include_codes=args.include_codes
            )
        elif args.command == "search":
            data = catalog.search_features(
                args.query,
                profile=args.profile,
                table=args.table,
                grain=args.grain,
                domain=args.domain,
                feature_kind=args.feature_kind,
                limit=args.limit,
            )
        elif args.command == "code":
            data = catalog.lookup_code(args.feature_or_vocabulary, args.code)
        else:  # pragma: no cover - argparse constrains this branch.
            raise AssertionError(f"unsupported command {args.command!r}")
    except (CatalogError, OSError, ValueError) as exc:
        _emit_error(args.format, args.command, exc)
        return 2

    if args.format == "json":
        _emit_json(
            {
                "ok": True,
                "command": args.command,
                "data": data,
            }
        )
    else:
        print(_format_text(args.command, data))
    return 0


def _emit_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _emit_error(output_format: str, command: str, exc: Exception) -> None:
    if output_format == "json":
        _emit_json(
            {
                "ok": False,
                "command": command,
                "error": {
                    "type": _error_type(exc),
                    "message": str(exc),
                },
            }
        )
    else:
        print(f"error: {exc}", file=sys.stderr)


def _error_type(exc: Exception) -> str:
    name = type(exc).__name__
    if name.startswith("Catalog"):
        name = name[len("Catalog") :]
    if name.endswith("Error"):
        name = name[: -len("Error")]
    words: list[str] = []
    current = ""
    for character in name:
        if character.isupper() and current:
            words.append(current)
            current = character.lower()
        else:
            current += character.lower()
    if current:
        words.append(current)
    return "_".join(words) or "error"


def _format_text(command: str, data: dict[str, Any]) -> str:
    if command == "validate":
        return (
            f"valid: schema v{data['schema_version']}; "
            f"{data['concepts']} concepts, {data['bindings']} bindings, "
            f"{data['vocabularies']} vocabularies"
        )
    if command == "get":
        concept = data["concept"]
        lines = [
            f"{data['identifier']} — {concept['label']}",
            concept["definition"],
        ]
        if data["kind"] == "binding":
            binding = data["binding"]
            lines.append(
                f"{binding['profile']} · {binding['grain']} · "
                f"{binding['physical_type']} · {binding['role']}"
            )
        else:
            lines.append(f"{len(data['bindings'])} physical binding(s)")
        vocabulary = data.get("vocabulary")
        if vocabulary is not None:
            lines.append(
                f"vocabulary: {vocabulary['id']} "
                f"({vocabulary['completeness']}, {vocabulary['parsing']})"
            )
            codes = vocabulary.get("codes")
            if codes is not None:
                lines.append("codes:")
                lines.extend(
                    f"  {code} — {meaning}"
                    for code, meaning in codes.items()
                )
        return "\n".join(lines)
    if command == "search":
        matches = data["matches"]
        if not matches:
            return "No matches."
        lines = [
            f"{item['score']:>4}  {item['identifier']} — {item['label']}"
            for item in matches
        ]
        if data["total"] > len(matches):
            lines.append(
                f"Showing {len(matches)} of {data['total']} matches."
            )
        return "\n".join(lines)
    if command == "code":
        return (
            f"{data['vocabulary']} {data['code']} — {data['meaning']}"
        )
    raise ValueError(f"unsupported command {command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
