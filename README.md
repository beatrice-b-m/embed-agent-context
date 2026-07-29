# EMBED clinical-semantic context

This repository provides a count-free, machine-queryable clinical-semantic
catalog for the Emory Breast Imaging Dataset (EMBED). It helps an unfamiliar
agent understand what clinical objects, events, features, timelines,
relationships, and uncertainty EMBED can represent before the agent chooses a
cohort or analysis design.

The portable model is independent of physical storage. Profile-specific tables,
columns, types, keys, and join tuples form a secondary implementation-binding
layer. The same clinical concepts can therefore describe EMBED loaded from
release tables, denormalized views, another database, or a future release.

The catalog is descriptive. It does not choose a diagnosis date, outcome
window, exclusion rule, cohort definition, or aggregation policy on an
analyst's behalf.

## Clinical-semantic model

Schema version 5 organizes breast-imaging context around this clinical
hierarchy:

```text
patient
  → breast-imaging episode / exam
  → breast side and imaging finding
  → assessment / recommendation
  → linked procedure
  → pathology observation / diagnosis
```

The hierarchy is not a claim that every object has one row or one table. Each
semantic relationship records clinical meaning, direction, cardinality,
optionality, attribution limitations, temporal qualifications, evidence,
scope, and unresolved questions. Physical relationship bindings separately
describe how one profile approximates those relationships.

The portable semantic layer contains:

- `clinical_objects` for independently meaningful entities and observations;
- `concepts` for semantic features owned by clinical objects;
- `semantic_relationships` for storage-independent clinical adjacency and
  attribution;
- `temporal_semantics` for event, documentation, and availability meanings;
- `aggregations` for supplied rollups and explicitly unresolved transitions;
- `guardrails` for reusable interpretation constraints;
- `coverage` for supported, unsupported, unresolved, and uncataloged scope;
- vocabularies, contexts, claims, and sources for meanings and provenance.

`profile_bindings` contains the secondary implementation layer: feature
bindings, object/table representations, table specifications, and physical
relationship bindings.

See [the v5 architecture](docs/architecture-v5.md) and
[catalog format](docs/catalog-format.md) for the complete contract.

## Breast-cancer outcome and time semantics

The initial outcome model distinguishes invasive breast cancer, in-situ breast
cancer, high-risk lesion, borderline lesion, benign finding, and non-breast
cancer. `unattached_pathology` is an attachment state, not a seventh diagnosis
code: it does not establish absence of disease, a benign diagnosis, complete
follow-up, or a negative outcome. The non-breast-cancer state is likewise not
benign, healthy, or absence of malignancy. Restricting to attached pathology
also conditions on a represented tissue-sampling procedure.

Supplied side- and exam-level pathology severity use the minimum numeric value
because the represented scale is inverse. The catalog does not invent a
finding-to-side, exam-to-patient, or patient-level outcome policy where one is
not supplied.

Candidate dates retain their distinct meanings:

- exam study date is an imaging-exam event time;
- procedure date is a procedure event time;
- specimen collection time is clinically meaningful but is not represented by
  a supported open-v2 feature;
- pathology report date is a documentation/report time.

None is designated a universal diagnosis date. Availability may lag event or
documentation time, and using downstream procedure or pathology information
for an earlier prediction target may cause temporal leakage.

## Discovery first

Start with a clinical question; table names and stable IDs are not required:

```bash
uv run --locked --no-dev python -m embed_context discover \
  "How is breast cancer represented and when is it known?"
uv run --locked --no-dev python -m embed_context discover \
  "What does absent pathology mean?" --profile open-v2
uv run --locked --no-dev python -m embed_context discover \
  "pathology attribution to imaging findings" \
  --kind semantic_relationship --kind guardrail --domain pathology
```

Discovery searches clinical objects, features, semantic relationships,
temporal semantics, aggregations, guardrails, coverage, and supporting context.
Each match reports its kind, identifier, score, label, matched fields, matched
terms, and unmatched query terms. Diagnostics distinguish:

- matches excluded by filters;
- unknown filter or vocabulary values;
- semantics explicitly unsupported in the selected profile;
- missing catalog coverage.

Missing catalog coverage means that the portable catalog has no indexed
assertion for the question. It does not prove that the clinical concept is
absent from EMBED or clinical reality.

Use exact getters to navigate a discovery result:

```bash
uv run --locked --no-dev python -m embed_context object imaging_finding
uv run --locked --no-dev python -m embed_context feature pathology.severity
uv run --locked --no-dev python -m embed_context feature \
  pathology.severity --include-codes
uv run --locked --no-dev python -m embed_context semantic-relationship \
  clinical.finding-pathology-observation
uv run --locked --no-dev python -m embed_context temporal \
  time.pathology-report-documentation
uv run --locked --no-dev python -m embed_context aggregation \
  aggregation.pathology-severity-to-exam
uv run --locked --no-dev python -m embed_context guardrail \
  guardrail.null-pathology-not-negative
uv run --locked --no-dev python -m embed_context coverage \
  coverage.open-v2.specimen-time
uv run --locked --no-dev python -m embed_context code \
  pathology.severity 0
```

After selecting semantic concepts, inspect a release implementation through the
explicitly secondary binding commands:

```bash
uv run --locked --no-dev python -m embed_context profile-table \
  open-v2 exam_level_anon
uv run --locked --no-dev python -m embed_context relationship-binding \
  open-v2.pathology_findings_anon.imaging_finding
uv run --locked --no-dev python -m embed_context relationship-bindings \
  --profile open-v2 --table pathology_findings_anon
```

Physical relationship bindings are descriptive metadata, not executable joins.
Callers must honor their optionality, cardinality, evidence, caveats, and join
hazards.

Place `--format json` before the subcommand for a stable machine-readable
envelope:

```bash
uv run --locked --no-dev python -m embed_context --format json discover \
  "Which timestamps could anchor pathology?"
```

Successful responses use:

```json
{"ok": true, "command": "discover", "data": {}}
```

Errors use the same envelope with `ok: false` and a structured error type and
message. `validate` summarizes schema-v5 semantic inventories, binding
inventories, and controlled facets.

## Stdio MCP server

MCP support is optional so the core catalog and CLI remain dependency-free.
Start the read-only server with the pinned SDK extra:

```bash
uv run --locked --no-dev --extra mcp python -m embed_context.mcp_server
```

An MCP client can invoke it from any working directory:

```json
{
  "command": "uv",
  "args": [
    "--directory",
    "/absolute/path/to/embedv2-agent-context",
    "run",
    "--locked",
    "--no-dev",
    "--extra",
    "mcp",
    "python",
    "-m",
    "embed_context.mcp_server"
  ]
}
```

The server exposes twelve read-only, closed-schema, structured-output tools:

1. `discover`
2. `get_clinical_object`
3. `get_feature`
4. `get_semantic_relationship`
5. `get_temporal_semantic`
6. `get_aggregation`
7. `get_guardrail`
8. `get_coverage`
9. `lookup_code`
10. `get_profile_table`
11. `get_relationship_binding`
12. `search_relationship_bindings`

Agents should begin with `discover`, follow exact semantic references, and use
the final three profile/binding operations only to implement chosen semantics
in a release. Tool schemas reject undeclared arguments. All tools are
read-only, idempotent, and closed-world with respect to catalog metadata.

The server writes MCP protocol messages only to stdout. Startup errors and
diagnostics go to stderr.

## Repository layout

- [catalog/catalog.json](catalog/catalog.json) — canonical portable semantics,
  provenance, and profile bindings.
- [catalog/catalog.schema.json](catalog/catalog.schema.json) — versioned JSON
  Schema.
- `embed_context/` — dependency-free query core and CLI plus the optional MCP
  adapter.
- `tests/` — synthetic contracts, validation, discovery, interface, and
  source-profile checks.
- [docs/architecture-v5.md](docs/architecture-v5.md) — semantic/binding layer
  decision and discovery contract.
- [docs/catalog-format.md](docs/catalog-format.md) — authoring and query
  contract.
- [docs/migration-v4-to-v5.md](docs/migration-v4-to-v5.md) — breaking-change
  guidance.
- [docs/project-scope.md](docs/project-scope.md) — boundaries and authoring
  requirements.
- `reference_files/` — ignored local EMBED V2 source artifacts used only to
  verify profile bindings.

## Breaking migration from schema v4

Schema v5 is intentionally breaking. There is no automatic v4-to-v5 in-memory
conversion because physical metadata cannot reliably invent clinical objects,
attribution, time roles, coverage, or guardrails.

The CLI commands `search`, `get`, `table`, `relationship`, `relationships`,
`context`, `contexts`, `pattern`, and `patterns` are removed. Replace them with
`discover`, an exact semantic getter, and—when needed—an explicitly named
profile-binding command.

The MCP tools `search_features`, `get_table`, `get_relationship`,
`search_relationships`, `get_context`, `search_contexts`,
`get_analysis_pattern`, and `search_analysis_patterns` are removed. Use the
twelve tools listed above.

Task-specific analysis patterns are not migrated as cohort recipes. Their
supported clinical facts move into outcome, temporal, aggregation, coverage,
and guardrail semantics; generic modeling advice is removed. See
[the full v4-to-v5 migration guide](docs/migration-v4-to-v5.md).

## Explicit non-goals

The portable catalog does not:

- encode SQL, dataframe operations, executable predicates, or pipelines;
- select preferred cohort definitions, anchors, follow-up windows, outcomes,
  exclusions, or aggregation policies;
- claim that a cohort or analysis is scientifically valid;
- treat physical tables as the clinical conceptual model;
- anticipate every research workflow;
- include empirical row counts, distributions, prevalences, or completeness
  measurements;
- interpret imaging assessment as pathology truth or absent pathology as a
  negative diagnosis.

Agents and users remain responsible for constructing and defending their
analysis design.

## Verification

Run the complete suite and the footer-only source-profile check:

```bash
uv run --locked python -m unittest discover -v
uv run --locked python scripts/validate_source_profile.py
```

Exercise the optional MCP adapter against the pinned SDK:

```bash
uv run --locked --no-dev --extra mcp python -m unittest \
  tests.test_mcp_server -v
```

The source-profile verifier derives the expected physical manifest from the
selected profile and compares table names, columns, physical types, and schema
nullability. It reads Parquet footers only and does not inspect clinical values
or statistics.
