"""Baseline-versus-draft deterministic discovery comparison."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from embed_context.catalog import Catalog


_MATCH_DETAIL_FIELDS = (
    "match_reasons",
    "profile_coverage",
    "qualifications",
    "active_revisions",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _binding_inventory(match: Mapping[str, Any]) -> dict[str, Any]:
    implementation = match.get("implementation_bindings")
    if not isinstance(implementation, Mapping):
        return {}
    result: dict[str, Any] = {}
    if "profile" in implementation:
        result["profile"] = implementation["profile"]
    for family in (
        "feature_bindings",
        "object_bindings",
        "relationship_bindings",
        "relationship_binding_paths",
    ):
        values = implementation.get(family, ())
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            continue
        identifiers: list[str] = []
        for value in values:
            if not isinstance(value, Mapping):
                identifiers.append(_canonical(value))
                continue
            identifier = (
                value.get("id")
                or value.get("qualified_identifier")
                or value.get("identifier")
            )
            identifiers.append(str(identifier) if identifier is not None else _canonical(value))
        result[family] = sorted(identifiers)
    return result


def _matches_by_key(
    result: Mapping[str, Any],
) -> tuple[dict[tuple[str, str], Mapping[str, Any]], dict[tuple[str, str], int]]:
    matches: dict[tuple[str, str], Mapping[str, Any]] = {}
    ranks: dict[tuple[str, str], int] = {}
    for rank, raw in enumerate(result.get("matches", ()), start=1):
        if not isinstance(raw, Mapping):
            raise ValueError("discovery matches must be mappings")
        key = (str(raw["kind"]), str(raw["identifier"]))
        if key in matches:
            raise ValueError(f"duplicate discovery match {key!r}")
        matches[key] = raw
        ranks[key] = rank
    return matches, ranks


def compare_discovery_results(
    baseline: Mapping[str, Any], draft: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare two results from the same ``Catalog.discover`` request.

    The comparison is keyed by ``(kind, identifier)`` rather than list
    position.  It reports only changed matches; unchanged counts remain in the
    summary.  All ordering is independent of input mapping insertion order.
    """

    baseline_matches, baseline_ranks = _matches_by_key(baseline)
    draft_matches, draft_ranks = _matches_by_key(draft)
    changes: list[dict[str, Any]] = []
    unchanged = 0
    for kind, identifier in sorted(set(baseline_matches) | set(draft_matches)):
        key = (kind, identifier)
        before = baseline_matches.get(key)
        after = draft_matches.get(key)
        if before is None:
            changes.append(
                {
                    "kind": kind,
                    "identifier": identifier,
                    "status": "added",
                    "rank": {"baseline": None, "draft": draft_ranks[key]},
                    "score": {"baseline": None, "draft": after.get("score")},
                }
            )
            continue
        if after is None:
            changes.append(
                {
                    "kind": kind,
                    "identifier": identifier,
                    "status": "removed",
                    "rank": {"baseline": baseline_ranks[key], "draft": None},
                    "score": {"baseline": before.get("score"), "draft": None},
                }
            )
            continue

        details: dict[str, Any] = {}
        before_rank = baseline_ranks[key]
        after_rank = draft_ranks[key]
        if before_rank != after_rank:
            details["rank"] = {
                "baseline": before_rank,
                "draft": after_rank,
                "delta": after_rank - before_rank,
            }
        before_score = before.get("score")
        after_score = after.get("score")
        if before_score != after_score:
            delta = (
                after_score - before_score
                if isinstance(before_score, (int, float))
                and not isinstance(before_score, bool)
                and isinstance(after_score, (int, float))
                and not isinstance(after_score, bool)
                else None
            )
            details["score"] = {
                "baseline": before_score,
                "draft": after_score,
                **({"delta": delta} if delta is not None else {}),
            }
        for field in _MATCH_DETAIL_FIELDS:
            before_value = before.get(field, [])
            after_value = after.get(field, [])
            if _canonical(before_value) != _canonical(after_value):
                details[field] = {
                    "baseline": before_value,
                    "draft": after_value,
                }
        before_inventory = _binding_inventory(before)
        after_inventory = _binding_inventory(after)
        if before_inventory != after_inventory:
            details["implementation_binding_inventory"] = {
                "baseline": before_inventory,
                "draft": after_inventory,
            }
        if details:
            changes.append(
                {
                    "kind": kind,
                    "identifier": identifier,
                    "status": "changed",
                    **details,
                }
            )
        else:
            unchanged += 1

    before_diagnostics = baseline.get("diagnostics", [])
    after_diagnostics = draft.get("diagnostics", [])
    diagnostics_changed = _canonical(before_diagnostics) != _canonical(after_diagnostics)
    return {
        "available": True,
        "baseline_count": baseline.get("count", len(baseline_matches)),
        "draft_count": draft.get("count", len(draft_matches)),
        "unchanged_count": unchanged,
        "changed_count": len(changes),
        "diagnostics_changed": diagnostics_changed,
        "diagnostics": {
            "baseline": before_diagnostics,
            "draft": after_diagnostics,
        }
        if diagnostics_changed
        else None,
        "changes": changes,
    }


def run_discovery_comparison(
    baseline: Catalog,
    draft: Catalog | None = None,
    *,
    query: str,
    profile: str | None = None,
    kinds: Sequence[str] | None = None,
    domain: str | None = None,
    limit: int = 10,
    draft_revision: int | None = None,
) -> dict[str, Any]:
    """Run the same discovery request against baseline and optional draft."""

    request = {
        "query": query,
        "profile": profile,
        "kinds": list(kinds) if kinds is not None else None,
        "domain": domain,
        "limit": limit,
    }
    baseline_result = baseline.discover(
        query, profile=profile, kinds=kinds, domain=domain, limit=limit
    )
    if draft is None:
        return {
            "request": request,
            "baseline": baseline_result,
            "draft": None,
            "draft_revision": draft_revision,
            "comparison": {
                "available": False,
                "reason": "no_valid_draft",
            },
        }
    draft_result = draft.discover(
        query, profile=profile, kinds=kinds, domain=domain, limit=limit
    )
    return {
        "request": request,
        "baseline": baseline_result,
        "draft": draft_result,
        "draft_revision": draft_revision,
        "comparison": compare_discovery_results(baseline_result, draft_result),
    }


# Short alias for session code and API handlers.
compare_query = run_discovery_comparison
