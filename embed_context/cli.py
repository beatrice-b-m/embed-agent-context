"""Command-line access to the EMBED clinical-semantic catalog."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .catalog import (
    DISCOVERY_KINDS,
    DOMAINS,
    RELATIONSHIP_BINDING_KINDS,
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

    discover_parser = subparsers.add_parser(
        "discover",
        help=(
            "discover clinical objects, features, relationships, time "
            "semantics, aggregations, guardrails, and coverage"
        ),
    )
    discover_parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="clinical question or phrase; may be omitted when filtering",
    )
    discover_parser.add_argument(
        "--profile",
        help="include support and implementation context for one profile",
    )
    discover_parser.add_argument(
        "--kind",
        dest="kinds",
        choices=DISCOVERY_KINDS,
        action="append",
        help="limit to an entity kind; repeat to select multiple kinds",
    )
    discover_parser.add_argument("--domain", choices=DOMAINS)
    discover_parser.add_argument("--limit", type=int, default=50)

    _add_identifier_command(
        subparsers,
        "object",
        "get one clinical object by stable identifier",
    )
    feature_parser = _add_identifier_command(
        subparsers,
        "feature",
        "get one semantic feature by stable identifier or physical alias",
    )
    feature_parser.add_argument(
        "--include-codes",
        action="store_true",
        help="include the complete code map when a vocabulary is attached",
    )
    _add_identifier_command(
        subparsers,
        "semantic-relationship",
        "get one storage-independent clinical relationship",
    )
    _add_identifier_command(
        subparsers,
        "temporal",
        "get one event, documentation, or availability-time meaning",
    )
    _add_identifier_command(
        subparsers,
        "aggregation",
        "get one supplied or explicitly unresolved aggregation meaning",
    )
    _add_identifier_command(
        subparsers,
        "guardrail",
        "get one reusable clinical interpretation guardrail",
    )
    _add_identifier_command(
        subparsers,
        "coverage",
        "get one supported, unsupported, or unresolved coverage statement",
    )

    code_parser = subparsers.add_parser("code", help="look up an exact code")
    code_parser.add_argument("feature_or_vocabulary")
    code_parser.add_argument("code")

    table_parser = subparsers.add_parser(
        "profile-table",
        help="get one secondary profile-specific table binding",
    )
    table_parser.add_argument("profile")
    table_parser.add_argument("table")

    _add_identifier_command(
        subparsers,
        "relationship-binding",
        "get one secondary physical relationship binding",
    )
    relationships_parser = subparsers.add_parser(
        "relationship-bindings",
        help="filter secondary physical relationship bindings",
    )
    relationships_parser.add_argument("--profile")
    relationships_parser.add_argument(
        "--table",
        help="match bindings where either endpoint uses this table",
    )
    relationships_parser.add_argument("--source-table")
    relationships_parser.add_argument("--target-table")
    relationships_parser.add_argument(
        "--kind",
        choices=sorted(RELATIONSHIP_BINDING_KINDS),
    )
    relationships_parser.add_argument(
        "--semantic-relationship",
        help="match bindings linked to this portable semantic relationship ID",
    )
    relationships_parser.add_argument("--limit", type=int, default=50)
    return parser


def _add_identifier_command(
    subparsers: Any,
    name: str,
    help_text: str,
) -> argparse.ArgumentParser:
    command = subparsers.add_parser(name, help=help_text)
    command.add_argument("identifier")
    return command


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        data = _run_command(catalog, args)
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


def _run_command(catalog: Any, args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "validate":
        return catalog.summary()
    if args.command == "discover":
        return catalog.discover(
            args.query,
            profile=args.profile,
            kinds=tuple(args.kinds) if args.kinds else None,
            domain=args.domain,
            limit=args.limit,
        )
    if args.command == "object":
        return catalog.get_clinical_object(args.identifier)
    if args.command == "feature":
        return catalog.get_feature(
            args.identifier,
            include_codes=args.include_codes,
        )
    if args.command == "semantic-relationship":
        return catalog.get_semantic_relationship(args.identifier)
    if args.command == "temporal":
        return catalog.get_temporal_semantic(args.identifier)
    if args.command == "aggregation":
        return catalog.get_aggregation(args.identifier)
    if args.command == "guardrail":
        return catalog.get_guardrail(args.identifier)
    if args.command == "coverage":
        return catalog.get_coverage(args.identifier)
    if args.command == "code":
        return catalog.lookup_code(args.feature_or_vocabulary, args.code)
    if args.command == "profile-table":
        return catalog.get_profile_table(args.profile, args.table)
    if args.command == "relationship-binding":
        return catalog.get_relationship_binding(args.identifier)
    if args.command == "relationship-bindings":
        return catalog.search_relationship_bindings(
            profile=args.profile,
            table=args.table,
            source_table=args.source_table,
            target_table=args.target_table,
            kind=args.kind,
            semantic_relationship=args.semantic_relationship,
            limit=args.limit,
        )
    raise AssertionError(f"unsupported command {args.command!r}")


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
        return _format_summary(data)
    if command == "discover":
        return _format_discovery(data)
    if command == "object":
        return _format_entity_result(data, "clinical_object")
    if command == "feature":
        return _format_feature(data)
    if command == "semantic-relationship":
        return _format_semantic_relationship(data)
    if command == "temporal":
        return _format_temporal(data)
    if command == "aggregation":
        return _format_aggregation(data)
    if command == "guardrail":
        return _format_guardrail(data)
    if command == "coverage":
        return _format_entity_result(data, "coverage")
    if command == "code":
        vocabulary = data.get("vocabulary", data.get("feature_or_vocabulary", ""))
        return f"{vocabulary} {data['code']} — {data['meaning']}"
    if command == "profile-table":
        return _format_profile_table(data)
    if command == "relationship-binding":
        return _format_relationship_binding(
            _entity_from_result(data, "relationship_binding")
        )
    if command == "relationship-bindings":
        matches = data.get("matches", ())
        if not matches:
            return "No relationship bindings."
        lines = [_format_relationship_binding(item) for item in matches]
        _append_result_count(lines, data, "relationship bindings")
        return "\n".join(lines)
    raise ValueError(f"unsupported command {command!r}")


def _format_summary(data: Mapping[str, Any]) -> str:
    labels = (
        ("clinical_objects", "clinical objects"),
        ("concepts", "features"),
        ("semantic_relationships", "semantic relationships"),
        ("temporal_semantics", "temporal semantics"),
        ("aggregations", "aggregations"),
        ("guardrails", "guardrails"),
        ("coverage", "coverage records"),
        ("vocabularies", "vocabularies"),
        ("sources", "sources"),
        ("contexts", "contexts"),
        ("profile_bindings", "profile bindings"),
        ("feature_bindings", "feature bindings"),
        ("bindings", "feature bindings"),
        ("tables", "profile tables"),
        ("relationship_bindings", "relationship bindings"),
    )
    counts = [
        f"{data[key]} {label}"
        for key, label in labels
        if isinstance(data.get(key), int)
    ]
    prefix = f"valid: schema v{data['schema_version']}"
    if counts:
        prefix += "; " + ", ".join(counts)
    facets = _format_facets(data)
    return "\n".join((prefix, *facets))


def _format_facets(data: Mapping[str, Any]) -> list[str]:
    facet_keys = (
        "profiles",
        "binding_grains",
        "feature_kinds",
        "domains",
        "context_kinds",
        "context_scopes",
        "source_kinds",
        "source_locator_kinds",
        "claim_statuses",
        "semantic_relationship_kinds",
        "temporal_kinds",
        "aggregation_statuses",
        "coverage_statuses",
        "relationship_binding_kinds",
    )
    lines: list[str] = []
    for key in facet_keys:
        values = data.get(key)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            lines.append(f"{key.replace('_', ' ')}: {', '.join(map(str, values))}")
    return lines


def _format_discovery(data: Mapping[str, Any]) -> str:
    matches = data.get("matches", ())
    lines: list[str] = []
    if not matches:
        lines.append("No catalog matches.")
    for match in matches:
        label = match.get("label") or match.get("identifier", "unknown")
        lines.append(
            f"{match.get('score', 0):>4}  {match.get('identifier', 'unknown')} "
            f"[{match.get('kind', 'unknown')}] — {label}"
        )
        reasons = match.get("match_reasons", ())
        if reasons:
            rendered = []
            for reason in reasons:
                field = reason.get("field", "unknown")
                terms = reason.get("terms", ())
                rendered.append(f"{field}: {', '.join(map(str, terms))}")
            lines.append("      matched by " + "; ".join(rendered))
        matched_terms = match.get("matched_terms", ())
        unmatched_terms = match.get("unmatched_terms", ())
        if matched_terms:
            lines.append("      matched terms: " + ", ".join(map(str, matched_terms)))
        if unmatched_terms:
            lines.append(
                "      unmatched terms: " + ", ".join(map(str, unmatched_terms))
            )
    _append_result_count(lines, data, "matches")
    lines.extend(_format_diagnostics(data.get("diagnostics")))
    return "\n".join(lines)


def _format_diagnostics(diagnostics: Any) -> list[str]:
    if not diagnostics:
        return ["diagnostics: none"]
    lines = ["diagnostics:"]
    if isinstance(diagnostics, Mapping):
        for name, value in diagnostics.items():
            if value in (None, False, "", [], {}, ()):
                continue
            lines.append(
                f"  {name.replace('_', ' ')}: {_render_diagnostic_value(value)}"
            )
    elif isinstance(diagnostics, Sequence) and not isinstance(
        diagnostics, (str, bytes)
    ):
        lines.extend(f"  {_render_diagnostic_value(item)}" for item in diagnostics)
    else:
        lines.append(f"  {_render_diagnostic_value(diagnostics)}")
    if len(lines) == 1:
        lines.append("  none")
    return lines


def _render_diagnostic_value(value: Any) -> str:
    if value is True:
        return "yes"
    if isinstance(value, Mapping):
        category = value.get("category")
        if category:
            message = value.get("message")
            details = [
                f"{key}={item}"
                for key, item in value.items()
                if key not in {"category", "message"}
            ]
            rendered = str(category).replace("_", " ")
            if message:
                rendered += f": {message}"
            if details:
                rendered += f" ({'; '.join(details)})"
            return rendered
        return "; ".join(f"{key}={item}" for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return ", ".join(map(str, value))
    return str(value)


def _format_feature(data: Mapping[str, Any]) -> str:
    feature = _entity_from_result(data, "feature")
    lines = _entity_lines(data, feature)
    bindings = data.get("profile_bindings", data.get("bindings", ()))
    if bindings:
        lines.append(f"{len(bindings)} profile binding(s)")
    vocabulary = data.get("vocabulary")
    if isinstance(vocabulary, Mapping):
        metadata = [
            str(vocabulary["id"])
            if "id" in vocabulary
            else str(vocabulary.get("identifier", "vocabulary"))
        ]
        for field in ("completeness", "parsing"):
            if vocabulary.get(field):
                metadata.append(str(vocabulary[field]))
        lines.append("vocabulary: " + " · ".join(metadata))
        codes = vocabulary.get("codes")
        if isinstance(codes, Mapping):
            lines.append("codes:")
            lines.extend(f"  {code} — {meaning}" for code, meaning in codes.items())
    _append_navigation_and_provenance(lines, data)
    return "\n".join(lines)


def _format_semantic_relationship(data: Mapping[str, Any]) -> str:
    relationship = _entity_from_result(data, "semantic_relationship")
    lines = _entity_lines(data, relationship)
    source = _reference_identifier(
        relationship.get("source_object", relationship.get("source"))
    )
    target = _reference_identifier(
        relationship.get("target_object", relationship.get("target"))
    )
    if source or target:
        lines.append(f"{source or '?'} → {target or '?'}")
    cardinality = relationship.get("cardinality")
    if isinstance(cardinality, Mapping):
        lines.append(
            "cardinality: "
            + "; ".join(f"{key}={value}" for key, value in cardinality.items())
        )
    optionality = relationship.get("optionality")
    if isinstance(optionality, Mapping):
        lines.append(
            "optionality: "
            + "; ".join(f"{key}={value}" for key, value in optionality.items())
        )
    if relationship.get("attribution"):
        lines.append(f"attribution: {relationship['attribution']}")
    if relationship.get("temporal_qualification"):
        lines.append(
            f"temporal qualification: {relationship['temporal_qualification']}"
        )
    limitations = relationship.get(
        "attribution_limitations",
        relationship.get("limitations", ()),
    )
    if limitations:
        lines.append("limitations: " + "; ".join(map(str, limitations)))
    _append_navigation_and_provenance(lines, data)
    return "\n".join(lines)


def _format_temporal(data: Mapping[str, Any]) -> str:
    temporal = _entity_from_result(data, "temporal_semantic")
    lines = _entity_lines(data, temporal)
    for field, label in (
        ("objects", "objects"),
        ("feature_refs", "features"),
        ("relative_to", "relative to"),
    ):
        values = temporal.get(field, ())
        if values:
            lines.append(f"{label}: {', '.join(map(str, values))}")
    _append_navigation_and_provenance(lines, data)
    return "\n".join(lines)


def _format_aggregation(data: Mapping[str, Any]) -> str:
    aggregation = _entity_from_result(data, "aggregation")
    lines = _entity_lines(data, aggregation)
    source_object = aggregation.get("source_object")
    target_object = aggregation.get("target_object")
    if source_object or target_object:
        lines.append(
            f"grain transition: {source_object or '?'} → "
            f"{target_object or '?'}"
        )
    source_concept = aggregation.get("source_concept")
    result_concept = aggregation.get("result_concept")
    if source_concept or result_concept:
        lines.append(
            f"feature transition: {source_concept or '?'} → "
            f"{result_concept or 'analyst-defined'}"
        )
    if aggregation.get("method"):
        lines.append(f"method: {aggregation['method']}")
    if aggregation.get("ordering"):
        lines.append(f"ordering: {aggregation['ordering']}")
    _append_navigation_and_provenance(lines, data)
    return "\n".join(lines)


def _format_guardrail(data: Mapping[str, Any]) -> str:
    guardrail = _entity_from_result(data, "guardrail")
    lines = _entity_lines(data, guardrail)
    if guardrail.get("rationale"):
        lines.append(f"rationale: {guardrail['rationale']}")
    _append_navigation_and_provenance(lines, data)
    return "\n".join(lines)


def _format_entity_result(
    data: Mapping[str, Any],
    entity_key: str,
) -> str:
    entity = _entity_from_result(data, entity_key)
    lines = _entity_lines(data, entity)
    _append_navigation_and_provenance(lines, data)
    return "\n".join(lines)


def _entity_from_result(
    data: Mapping[str, Any],
    entity_key: str,
) -> Mapping[str, Any]:
    entity = data.get(entity_key)
    return entity if isinstance(entity, Mapping) else data


def _entity_lines(
    result: Mapping[str, Any],
    entity: Mapping[str, Any],
) -> list[str]:
    identifier = result.get("identifier") or entity.get("id") or entity.get(
        "identifier", "unknown"
    )
    label = (
        entity.get("label")
        or entity.get("title")
        or entity.get("name")
        or identifier
    )
    lines = [f"{identifier} — {label}"]
    description = (
        entity.get("definition")
        or entity.get("meaning")
        or entity.get("description")
        or entity.get("statement")
        or entity.get("summary")
    )
    if description:
        lines.append(str(description))
    metadata = [
        str(entity[field])
        for field in ("kind", "status", "grain")
        if entity.get(field)
    ]
    if metadata:
        lines.append(" · ".join(metadata))
    caveats = entity.get("caveats", ())
    if caveats:
        lines.append("caveats: " + "; ".join(map(str, caveats)))
    return lines


def _format_profile_table(data: Mapping[str, Any]) -> str:
    table = _entity_from_result(data, "table")
    lines = _entity_lines(data, table)
    keys = table.get("keys", ())
    if keys:
        lines.append("keys:")
        for key in keys:
            if not isinstance(key, Mapping):
                lines.append(f"  {key}")
                continue
            columns = ", ".join(map(str, key.get("columns", ())))
            details = [
                str(key[field])
                for field in ("kind", "uniqueness", "completeness")
                if key.get(field)
            ]
            suffix = f" ({'; '.join(details)})" if details else ""
            lines.append(f"  {key.get('id', 'unnamed')} — {columns}{suffix}")
    else:
        lines.append("keys: none documented")
    relationships = data.get(
        "relationship_bindings",
        data.get("relationships", {}),
    )
    if isinstance(relationships, Mapping):
        outgoing = relationships.get("outgoing", ())
        incoming = relationships.get("incoming", ())
        lines.append(
            f"relationship bindings: {len(outgoing)} outgoing, "
            f"{len(incoming)} incoming"
        )
    return "\n".join(lines)


def _format_relationship_binding(relationship: Mapping[str, Any]) -> str:
    source = relationship.get("source", {})
    target = relationship.get("target", {})
    source_table = _endpoint_table(source)
    target_table = _endpoint_table(target)
    source_columns = ", ".join(map(str, source.get("columns", ())))
    target_columns = ", ".join(map(str, target.get("columns", ())))
    identifier = relationship.get("id", relationship.get("identifier", "unknown"))
    line = (
        f"{identifier} — {relationship.get('kind', 'unknown')} · "
        f"{relationship.get('profile', '?')}:{source_table}({source_columns}) → "
        f"{target_table}({target_columns})"
    )
    cardinality = relationship.get("cardinality")
    if isinstance(cardinality, Mapping):
        line += "\n  cardinality: " + "; ".join(
            f"{key}={value}" for key, value in cardinality.items()
        )
    hazards = relationship.get("join_hazards", ())
    if hazards:
        line += "\n  hazards: " + "; ".join(map(str, hazards))
    return line


def _reference_identifier(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return str(value.get("id", value.get("identifier", "")))
    return ""


def _append_navigation_and_provenance(
    lines: list[str],
    result: Mapping[str, Any],
) -> None:
    for field in ("related", "provenance"):
        value = result.get(field)
        if not value:
            continue
        lines.append(f"{field}:")
        if isinstance(value, Mapping):
            for category, references in value.items():
                rendered = _render_references(references)
                if rendered:
                    lines.append(f"  {category}: {rendered}")
        else:
            rendered = _render_references(value)
            if rendered:
                lines.append(f"  {rendered}")


def _render_references(value: Any) -> str:
    if isinstance(value, Mapping):
        direct = _reference_identifier(value)
        if direct:
            return direct
        return ", ".join(map(str, value))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        identifiers = [
            _reference_identifier(item) or str(item)
            for item in value
        ]
        return ", ".join(identifiers)
    return str(value) if value is not None else ""


def _endpoint_table(endpoint: Any) -> str:
    if isinstance(endpoint, Mapping):
        return str(endpoint.get("table", "?"))
    return "?"


def _append_result_count(
    lines: list[str],
    data: Mapping[str, Any],
    noun: str,
) -> None:
    total = data.get("total")
    count = data.get("count")
    if isinstance(total, int) and isinstance(count, int) and total > count:
        lines.append(f"Showing {count} of {total} {noun}.")


if __name__ == "__main__":
    raise SystemExit(main())
