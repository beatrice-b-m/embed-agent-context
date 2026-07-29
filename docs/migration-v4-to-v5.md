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

The CLI `pattern` and `patterns` commands and MCP
`get_analysis_pattern` and `search_analysis_patterns` tools are removed.
Callers should search for the clinical question with `discover` and follow
links to outcome semantics, temporal semantics, aggregations, and guardrails.

Version 4 context claims are retained as provenance, but the discovery API
returns them through the semantic entities they support rather than requiring a
caller to choose a context-specific search surface first.

## Compatibility boundary

There is no automatic v4-to-v5 in-memory conversion. A converter could preserve
physical metadata, but it could not reliably invent clinical objects,
attribution, time roles, coverage, or guardrails. Catalog authors must migrate
those assertions explicitly and retain unresolved status when evidence is
insufficient.
