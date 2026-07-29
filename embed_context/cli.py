"""Command-line access to the EMBED V2 feature catalog."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .catalog import (
    ANALYSIS_PATTERN_STATUSES,
    CLAIM_STATUSES,
    CONTEXT_KINDS,
    CONTEXT_SCOPES,
    DOMAINS,
    FEATURE_KINDS,
    GRAINS,
    RELATIONSHIP_KINDS,
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

    table_parser = subparsers.add_parser(
        "table",
        help="get one profile-specific table specification",
    )
    table_parser.add_argument("profile")
    table_parser.add_argument("table")

    relationship_parser = subparsers.add_parser(
        "relationship",
        help="get one exact table relationship",
    )
    relationship_parser.add_argument("identifier")

    relationships_parser = subparsers.add_parser(
        "relationships",
        help="list and filter table relationships",
    )
    relationships_parser.add_argument("--profile")
    relationships_parser.add_argument(
        "--table",
        help="match relationships where either endpoint uses this table",
    )
    relationships_parser.add_argument("--source-table")
    relationships_parser.add_argument("--target-table")
    relationships_parser.add_argument(
        "--kind",
        choices=sorted(RELATIONSHIP_KINDS),
    )
    relationships_parser.add_argument("--limit", type=int, default=50)

    context_parser = subparsers.add_parser(
        "context",
        help="get one exact clinical context",
    )
    context_parser.add_argument("identifier")

    contexts_parser = subparsers.add_parser(
        "contexts",
        help="search and filter clinical contexts",
    )
    contexts_parser.add_argument("query", nargs="?", default="")
    contexts_parser.add_argument("--kind", choices=CONTEXT_KINDS)
    contexts_parser.add_argument("--scope", choices=CONTEXT_SCOPES)
    contexts_parser.add_argument("--profile")
    contexts_parser.add_argument("--domain", choices=DOMAINS)
    contexts_parser.add_argument("--concept")
    contexts_parser.add_argument("--table")
    contexts_parser.add_argument("--relationship")
    contexts_parser.add_argument("--status", choices=CLAIM_STATUSES)
    contexts_parser.add_argument("--source")
    contexts_parser.add_argument("--limit", type=int, default=50)

    pattern_parser = subparsers.add_parser(
        "pattern",
        help="get one exact non-executable analysis pattern",
    )
    pattern_parser.add_argument("identifier")

    patterns_parser = subparsers.add_parser(
        "patterns",
        help="search and filter non-executable analysis patterns",
    )
    patterns_parser.add_argument("query", nargs="?", default="")
    patterns_parser.add_argument(
        "--status", choices=ANALYSIS_PATTERN_STATUSES
    )
    patterns_parser.add_argument("--scope", choices=CONTEXT_SCOPES)
    patterns_parser.add_argument("--profile")
    patterns_parser.add_argument("--domain", choices=DOMAINS)
    patterns_parser.add_argument("--grain", choices=GRAINS)
    patterns_parser.add_argument("--limit", type=int, default=50)
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
        elif args.command == "table":
            data = catalog.get_table(args.profile, args.table)
        elif args.command == "relationship":
            data = catalog.get_relationship(args.identifier)
        elif args.command == "relationships":
            data = catalog.search_relationships(
                profile=args.profile,
                table=args.table,
                source_table=args.source_table,
                target_table=args.target_table,
                kind=args.kind,
                limit=args.limit,
            )
        elif args.command == "context":
            data = catalog.get_context(args.identifier)
        elif args.command == "contexts":
            data = catalog.search_contexts(
                args.query,
                kind=args.kind,
                scope=args.scope,
                profile=args.profile,
                domain=args.domain,
                concept=args.concept,
                table=args.table,
                relationship=args.relationship,
                status=args.status,
                source=args.source,
                limit=args.limit,
            )
        elif args.command == "pattern":
            data = catalog.get_analysis_pattern(args.identifier)
        elif args.command == "patterns":
            data = catalog.search_analysis_patterns(
                args.query,
                status=args.status,
                scope=args.scope,
                profile=args.profile,
                domain=args.domain,
                grain=args.grain,
                limit=args.limit,
            )
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
            f"{data['vocabularies']} vocabularies, "
            f"{data['tables']} tables, "
            f"{data['relationships']} "
            f"{'relationship' if data['relationships'] == 1 else 'relationships'}, "
            f"{data['sources']} "
            f"{'source' if data['sources'] == 1 else 'sources'}, "
            f"{data['contexts']} "
            f"{'context' if data['contexts'] == 1 else 'contexts'}, "
            f"{data['analysis_patterns']} analysis "
            f"{'pattern' if data['analysis_patterns'] == 1 else 'patterns'}"
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
    if command == "table":
        table = data["table"]
        lines = [
            f"{data['identifier']} — {table['grain']} table",
        ]
        keys = table["keys"]
        if keys:
            lines.append("keys:")
            lines.extend(
                f"  {key['id']} — {', '.join(key['columns'])} "
                f"({key['kind']}; {key['uniqueness']}; "
                f"{key['completeness']})"
                for key in keys
            )
        else:
            lines.append("keys: none documented")
        relationships = data["relationships"]
        lines.append(
            f"relationships: {len(relationships['outgoing'])} outgoing, "
            f"{len(relationships['incoming'])} incoming"
        )
        return "\n".join(lines)
    if command == "relationship":
        return _format_relationship(data["relationship"])
    if command == "relationships":
        matches = data["matches"]
        if not matches:
            return "No relationships."
        lines = [_format_relationship(item) for item in matches]
        if data["total"] > len(matches):
            lines.append(
                f"Showing {len(matches)} of {data['total']} relationships."
            )
        return "\n".join(lines)
    if command == "context":
        context = data["context"]
        lines = [
            f"{data['identifier']} — {context['title']}",
            context["summary"],
            _format_context_metadata(context),
        ]
        lines.extend(_format_context_claims(context["claims"]))
        workflow_steps = context["workflow_steps"]
        if workflow_steps:
            lines.append("workflow:")
            lines.extend(
                f"  {step['id']} — {step['label']} "
                f"({', '.join(step['claims'])})"
                for step in workflow_steps
            )
        sources = data["sources"]
        if sources:
            lines.append("sources:")
            lines.extend(
                f"  {identifier} — {source['title']}"
                for identifier, source in sources.items()
            )
        return "\n".join(lines)
    if command == "contexts":
        matches = data["matches"]
        if not matches:
            return "No contexts."
        lines: list[str] = []
        for match in matches:
            lines.append(
                f"{match['score']:>4}  {match['identifier']} — "
                f"{match['title']}"
            )
            lines.append(f"      {_format_context_metadata(match)}")
            lines.extend(
                f"      {line}"
                for line in _format_context_claims(
                    match["matching_claims"],
                    heading=False,
                )
            )
        if data["total"] > len(matches):
            lines.append(
                f"Showing {len(matches)} of {data['total']} contexts."
            )
        return "\n".join(lines)
    if command == "pattern":
        pattern = data["pattern"]
        lines = [
            f"{data['identifier']} — {pattern['title']}",
            pattern["summary"],
            f"{pattern['status']} · {pattern['scope']} · "
            f"{', '.join(pattern['applicable_grains'])}",
            "alternatives:",
        ]
        lines.extend(
            f"  {item['id']} — {item['label']}"
            for item in pattern["alternatives"]
        )
        lines.append("required decisions:")
        lines.extend(
            f"  {item['id']} — {item['question']}"
            for item in pattern["required_decisions"]
        )
        lines.append("prohibited shortcuts:")
        lines.extend(
            f"  {item['id']} — {item['statement']}"
            for item in pattern["prohibited_shortcuts"]
        )
        return "\n".join(lines)
    if command == "patterns":
        matches = data["matches"]
        if not matches:
            return "No analysis patterns."
        lines = [
            f"{item['score']:>4}  {item['id']} — {item['title']} "
            f"[{item['status']}]"
            for item in matches
        ]
        if data["total"] > len(matches):
            lines.append(
                f"Showing {len(matches)} of {data['total']} analysis patterns."
            )
        return "\n".join(lines)
    raise ValueError(f"unsupported command {command!r}")


def _format_relationship(relationship: dict[str, Any]) -> str:
    source = relationship["source"]
    target = relationship["target"]
    cardinality = relationship["cardinality"]
    source_columns = ", ".join(source["columns"])
    target_columns = ", ".join(target["columns"])
    line = (
        f"{relationship['id']} — {relationship['kind']} · "
        f"{relationship['profile']}:{source['table']}({source_columns}) → "
        f"{target['table']}({target_columns}) · "
        f"{cardinality['targets_per_source']} target(s) per source; "
        f"{cardinality['sources_per_target']} source(s) per target"
    )
    hazards = relationship["join_hazards"]
    if hazards:
        line += "\n  hazards: " + "; ".join(hazards)
    return line


def _format_context_metadata(context: dict[str, Any]) -> str:
    metadata = f"{context['scope']} · {context['kind']}"
    profiles = context["profiles"]
    if profiles:
        metadata += f" · {', '.join(profiles)}"
    return metadata


def _format_context_claims(
    claims: list[dict[str, Any]],
    *,
    heading: bool = True,
) -> list[str]:
    lines = ["claims:"] if heading else []
    lines.extend(
        f"  [{claim['status']}] {claim['id']} — {claim['statement']}"
        for claim in claims
    )
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
