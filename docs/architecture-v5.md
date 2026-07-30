# Clinical-semantic architecture

> Historical record: this page documents schema version 5 and software 0.6.0.
> See [architecture v6](architecture-v6.md) for the current design.

## Decision

Schema version 5 makes portable clinical semantics the primary catalog model.
Profile-specific tables, columns, types, keys, projections, and join tuples are
implementation bindings beneath that model.

The catalog remains descriptive and count-free. It does not contain SQL,
dataframe operations, executable cohort predicates, preferred research
policies, or claims that an analysis is scientifically valid.

## Layers

The portable semantic layer contains:

- `clinical_objects` for independently meaningful clinical entities and
  observations;
- `concepts` for features attached to one or more clinical objects;
- `semantic_relationships` for clinical adjacency, attribution, cardinality,
  optionality, and limitations independent of storage layout;
- `temporal_semantics` for event, documentation, and availability meanings;
- `aggregations` for supplied rollups and explicitly unsupported transitions;
- `guardrails` for reusable interpretation constraints;
- `coverage` for supported, unsupported, unresolved, and `not_cataloged`
  catalog coverage;
- `vocabularies`, `sources`, and `contexts` for values and sourced claim
  provenance.

The implementation layer is `profile_bindings`, keyed by profile. Each profile
contains feature bindings, object-to-table representations, table
specifications, and physical relationship bindings. A clinical object is not
required to have its own table, and one physical row may represent parts of
several clinical objects.

## Initial object graph

The initial breast-imaging graph contains patient, breast-imaging episode,
imaging exam, breast side, imaging finding, imaging interpretation,
procedure, pathology observation, pathology diagnosis, radiology report, and
risk assessment objects.

The graph does not assert a deterministic workflow. Each semantic relationship
records direction, cardinality in both directions, endpoint optionality,
attribution limitations, temporal qualifications, structured time links,
claim references, and caveats. Aggregations link the semantic relationships
that establish grouping or attribution. Profile bindings separately explain
how a release approximates or fails to represent those relationships.

## Breast-cancer outcome semantics

The pathology-severity vocabulary retains the six represented diagnosis
groups: invasive breast cancer, in-situ breast cancer, high-risk lesion,
borderline lesion, benign finding, and non-breast cancer.

`unattached_pathology` is an absence/attachment state, not a seventh diagnosis
code. It means that no pathology is attached through the represented field or
relationship. It does not establish absence of disease, a benign diagnosis,
complete follow-up, or a negative outcome.

Provided side- and exam-level severity fields use the minimum value because the
scale is inverse. No universal finding-to-side, exam-to-patient, or
patient-level outcome aggregation policy is selected.

## Temporal semantics

Candidate times are modeled by what they represent:

- exam study date: imaging-exam event time;
- procedure date: linked procedure event time;
- specimen collection time: clinically meaningful but not represented by a
  supported open-v2 feature;
- pathology report date: pathology documentation/report time.

The catalog does not designate any of them as a universal diagnosis date.
Availability may lag event or documentation time, and downstream procedure or
pathology information may create temporal leakage when used for an earlier
prediction target.

## Discovery contract

`discover` is the clinical-first entry point. It searches objects, concepts,
semantic relationships, temporal semantics, aggregations, guardrails,
coverage, and context claims without requiring table names or stable IDs.

Each match returns its entity kind, stable identifier, score, matched fields,
matched terms, and unmatched query terms. The result also reports whether
filters excluded otherwise matching entities, a controlled filter or
vocabulary value is unknown, a concept is explicitly unsupported in the
selected profile, or the catalog has no indexed coverage.

Exact semantic getters compute `related` navigation from the graph and
`provenance` from `context#claim` references, including claim status, context
scope/profiles, and source records. They also expose relevant profile bindings
without duplicating those links in portable records. Profile binding queries
remain explicitly secondary and are never presented as the conceptual model.
Context matches have their own exact `context` / `get_context` lookup, which
returns every reviewed claim and resolves its source records.

## Delivery surfaces and versions

The source tree keeps the canonical JSON and JSON Schema under `catalog/`.
Built wheels bundle both resources beside the Python package so
`load_catalog()`, `embed-context`, and `embed-context-mcp` work outside a
checkout. The dependency-free core powers the Python API and CLI. The optional
stdio MCP adapter delegates to that same core and exposes only read-only tools.

Four version axes must not be conflated:

- software `0.6.0` versions the package, CLI, and MCP server;
- catalog schema version `5` versions serialized catalog shape and semantics;
- `open-v2` identifies one physical dataset profile, not a schema version; and
- MCP SDK `2.0.0` is the pinned optional protocol dependency.
