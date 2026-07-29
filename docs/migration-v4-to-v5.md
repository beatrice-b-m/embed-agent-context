# Migration from schema version 4 to version 5

Schema version 5 is intentionally breaking. Version 4 readers must reject a
version 5 catalog, and the version 5 reader reports an explicit migration
error for version 4 input rather than silently reinterpreting it.

## Collection changes

- `analysis_pattern_statuses` and `analysis_patterns` are removed.
- `bindings`, `tables`, and physical `relationships` move under
  `profile_bindings`.
- `clinical_objects`, `semantic_relationships`, `temporal_semantics`,
  `aggregations`, `guardrails`, and `coverage` are added as portable semantic
  collections.
- Existing concepts gain clinical-object ownership and may reference structured
  temporal, missing-state, or aggregation semantics.
- Existing `sources` and claim-level context provenance remain authoritative
  evidence machinery.

Stable concept, vocabulary, source, profile, table, column, and physical
relationship identifiers are preserved where their meanings are unchanged.
Physical relationship identifiers are not reinterpreted as semantic
relationship identifiers.

## Analysis-pattern disposition

The version 4 `open-v2.pathology-cancer-vs-noncancer` pattern is not migrated as
a cohort recipe.

| Disposition | Version 4 material | Version 5 destination |
|---|---|---|
| Retain | Reviewed severity code meanings, inverse ordering, verified side/exam minimum rollups, and sourced representation facts | Concepts, vocabulary, aggregations, contexts, and claim provenance |
| Generalize | Null-is-negative, assessment-is-pathology, downstream leakage, one-to-one attribution, implicit grain change, attached-pathology selection, and non-breast-cancer-as-healthy shortcuts | Reusable guardrails independent of a named research workflow |
| Move into clinical semantics | Outcome states, unattached pathology, procedure/pathology attribution, candidate dates, aggregation alternatives, and capture limitations | Clinical objects, semantic relationships, temporal semantics, structured missing states, aggregations, and coverage |
| Remove | The three case/control alternatives, the named cancer-versus-noncancer workflow, draft-pattern maturity, generic partition advice, and any implication of a preferred case, control, anchor, window, or exclusion policy | No replacement; agents must construct and defend these analysis choices |

- Cancer, benign, high-risk, borderline, non-breast-cancer, and unattached
  states move to outcome and missing-state semantics.
- Unit-of-analysis and multiple-record questions become grain and aggregation
  guardrails.
- Exam, procedure, specimen, and report-date choices move to temporal
  semantics without a preferred anchor.
- Follow-up and ascertainment limitations become capture guardrails.
- Null-is-negative, assessment-is-pathology, temporal leakage,
  many-to-many attribution, and co-location/co-availability statements become
  reusable guardrails.
- Numeric inverse-severity behavior becomes aggregation metadata.
- Generic train/test partition advice is removed.
- The three case/control alternatives are removed.

## Query and interface changes

Clinical discovery begins with `discover`, followed by exact semantic getters.
Table and physical relationship operations are renamed or documented as profile
binding queries.

### CLI command mapping

| Version 4 command | Version 5 replacement | Important change |
|---|---|---|
| `search QUERY` | `discover QUERY --kind feature` or unfiltered `discover QUERY` | Unified discovery can return every semantic kind and includes match reasons, unmatched terms, filter effects, support diagnostics, and coverage gaps. |
| `get ID` | `feature ID` | The response uses `feature`, returns all profile feature bindings, and can include resolved navigation and provenance. |
| `table PROFILE TABLE` | `profile-table PROFILE TABLE` | The name makes the secondary implementation role explicit. |
| `relationship ID` | `relationship-binding ID` | This gets a physical join binding, not a clinical relationship. Use `semantic-relationship ID` for portable meaning. |
| `relationships [filters]` | `relationship-bindings [filters]` | Physical filters are retained and clearly separated from clinical discovery. |
| `context ID` / `contexts QUERY` | `discover QUERY --kind context`, then a relevant semantic getter | Context claims remain evidence, but there is no context-first exact command. Semantic getter provenance resolves supporting claim, scope, and source records. |
| `pattern ID` / `patterns QUERY` | `discover QUERY --kind guardrail --kind temporal_semantic --kind aggregation --kind coverage` | There is deliberately no one-to-one pattern replacement and no cohort recipe. |

The new exact semantic commands are `object`, `feature`,
`semantic-relationship`, `temporal`, `aggregation`, `guardrail`, and
`coverage`. `validate` and `code` remain, although their summaries and linked
entity envelopes reflect schema version 5.

### MCP tool mapping

| Version 4 tool | Version 5 replacement |
|---|---|
| `search_features` | `discover` with `kinds: ["feature"]`, or unfiltered `discover` |
| `get_table` | `get_profile_table` |
| `get_relationship` | `get_relationship_binding` |
| `search_relationships` | `search_relationship_bindings` |
| `get_context` / `search_contexts` | `discover` plus an exact semantic getter with resolved provenance |
| `get_analysis_pattern` / `search_analysis_patterns` | `discover` across guardrails, temporal semantics, aggregations, and coverage |

The v5 MCP server additionally exposes `get_clinical_object`,
`get_semantic_relationship`, `get_temporal_semantic`, `get_aggregation`,
`get_guardrail`, and `get_coverage`.

### Parameters and responses

- `discover.kinds` is a list and may combine entity kinds. CLI callers repeat
  `--kind`.
- `profile` adds profile support context; it does not turn tables into the
  search ontology.
- Discovery matches contain `kind`, `identifier`, `score`, `label`, `entity`,
  `match_reasons`, `matched_terms`, and `unmatched_terms`.
- Discovery responses include normalized filters, pre- and post-filter counts,
  and diagnostics that distinguish excluded matches, invalid controlled
  vocabulary, unsupported profile coverage, and absent catalog coverage.
- Exact semantic getters use a kind-specific entity key and may add computed
  `related` and `provenance` sections. Those sections are derived navigation,
  not duplicated catalog assertions.
- `get_feature` returns every applicable binding rather than implying one
  canonical physical occurrence. Code maps remain opt-in.
- Physical table and relationship responses are explicitly profile-scoped and
  must not be interpreted as the clinical conceptual model.

Version 4 context claims are retained as provenance, but the discovery API
returns them through the semantic entities they support rather than requiring a
caller to choose a context-specific search surface first.

### Direct catalog consumers

Version 4 top-level physical arrays move beneath the selected profile:

| Version 4 path | Version 5 path |
|---|---|
| `bindings` filtered by `profile` | `profile_bindings[profile].feature_bindings` |
| `tables` filtered by `profile` | `profile_bindings[profile].tables` |
| `relationships` filtered by `profile` | `profile_bindings[profile].relationship_bindings` |

Object-to-table representation is new at
`profile_bindings[profile].object_bindings`. Nested records omit the redundant
`profile` field; the reader adds profile identity to query results.

The Python core removes the ambiguous v4 compatibility properties and methods
`catalog.bindings`, `catalog.tables`, `catalog.relationships`, `get_table`,
`get_relationship`, and `search_relationships`. Use `profile_bindings` for the
authoritative nested layer. Explicit flattened secondary views are available
as `feature_bindings`, `object_bindings`, `profile_tables`, and
`relationship_bindings`; exact queries use the v5 method names documented
above.

## Compatibility boundary

There is no automatic v4-to-v5 in-memory conversion. A converter could preserve
physical metadata, but it could not reliably invent clinical objects,
attribution, time roles, coverage, or guardrails. Catalog authors must migrate
those assertions explicitly and retain unresolved status when evidence is
insufficient.
