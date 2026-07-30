# Catalog format

## Design

Schema version 5 separates a portable clinical-semantic model from the
profile-specific structures that implement it:

```text
portable clinical semantics
│
├── clinical object ──< concept / feature
│        │
│        ├── semantic relationship ── clinical object
│        ├── temporal semantic
│        └── aggregation
│
├── reusable guardrail
├── coverage statement
└── context claim ── source

profile binding
│
├── object ── table / columns / representation
├── concept ── table / column / physical type / binding grain
├── table ── key candidate
└── semantic relationship ── physical relationship / join tuple
```

The portable layer describes clinical meaning, adjacency, time, aggregation,
uncertainty, and evidence without assuming a table layout. The binding layer
describes how one release or storage format represents those semantics. A
clinical object need not have its own table, and one row may co-locate parts of
several objects.

The catalog is a closed, count-free registry rather than a general ontology or
an execution engine. It does not contain SQL, dataframe expressions, executable
cohort predicates, preferred analysis policies, or empirical distributions.
See [`architecture-v5.md`](architecture-v5.md) for the design decision.

## Top-level contract

`schema_version`
: Integer format version. Version 5 readers reject every other version before
  interpreting version-specific fields.

`profiles`
: Stable identifiers for physical dataset variants. The keys of
  `profile_bindings` must equal the declared profile set.

`binding_grains`
: Controlled physical row grains used only by feature and table bindings:
  patient, exam, breast side, imaging finding, pathology finding, report, risk
  assessment, and wide row. A clinical object's `grain` is instead a
  descriptive clinical statement and is not constrained to a physical row
  enum.

`feature_kinds`, `domains`, `context_kinds`, `context_scopes`, `source_kinds`,
`source_locator_kinds`, and `claim_statuses`
: Controlled facets for feature classification, discovery, context scope,
  provenance, and review state.

`semantic_relationship_kinds`
: Controlled portable relationship classes: `hierarchy`, `association`,
  `attribution`, `documentation`, and `derivation`.

`temporal_kinds`
: Controlled distinctions among `event_time`, `documentation_time`, and
  `availability_time`.

`aggregation_statuses`
: Controlled states for an aggregation: `provided`, `analyst_defined`,
  `unsupported`, or `unresolved`.

`coverage_statuses`
: Controlled statements of `supported`, `unsupported`, `unresolved`, or
  `not_cataloged` coverage.

`clinical_objects`, `concepts`, `semantic_relationships`,
`temporal_semantics`, `aggregations`, `guardrails`, and `coverage`
: ID-keyed portable semantic collections.

`vocabularies`, `sources`, and `contexts`
: ID-keyed value dictionaries and claim-level provenance collections.

`profile_bindings`
: ID-keyed implementation layer. Each profile contains feature bindings, object
  bindings, table specifications, and physical relationship bindings.

The authoritative field constraints are in
[`catalog/catalog.schema.json`](../catalog/catalog.schema.json). Every object
shape is closed with `additionalProperties: false`; extensions require an
explicit schema decision rather than an ad hoc field.

Every listed top-level collection is required. `clinical_objects`, `concepts`,
and `profile_bindings` must be nonempty, and every profile must contain at
least one feature binding. A focused catalog may validly use empty
`semantic_relationships`, `temporal_semantics`, `aggregations`, `guardrails`,
or `coverage` collections. `vocabularies`, `sources`, and `contexts` may also
be empty when no retained record references them.

All nonblank strings are trimmed by contract: leading or trailing whitespace,
including a final newline, is invalid. Vocabulary code keys follow the same
rule, and each vocabulary contains at least one code.

### Two validation layers

Draft 2020-12 JSON Schema validates closed record shapes, types, required
fields, controlled constants, and local conditions. The dependency-free core
validator then resolves IDs and enforces graph, provenance-scope,
clinical-ownership, aggregation, temporal, and profile-binding invariants.
Neither layer substitutes for the other:

```bash
uv run --locked python -m unittest tests.test_catalog_schema -v
embed-context validate
```

The first command is a contributor check against both validators. The second
is the installed user's strict core validation and inventory summary.

### Compact record examples

A portable object and feature keep clinical meaning independent of storage:

```json
{
  "patient": {
    "label": "Patient",
    "definition": "A person represented in EMBED clinical data.",
    "grain": "One represented person.",
    "domains": ["identity"],
    "search_terms": ["person", "patient"],
    "claim_refs": ["embed.semantic#patient-meaning"],
    "caveats": ["Representation does not establish complete care."]
  }
}
```

```json
{
  "identity.patient_identifier": {
    "label": "Patient identifier",
    "definition": "Opaque patient identifier.",
    "feature_kind": "identifier",
    "domains": ["identity"],
    "objects": ["patient"],
    "search_terms": ["patient id"],
    "caveats": ["Do not interpret the identifier clinically."],
    "evidence": ["release_schema"],
    "claim_refs": ["embed.semantic#patient-meaning"],
    "missing_states": [],
    "temporal_semantics": [],
    "aggregations": []
  }
}
```

A context claim points to a source; portable entities point to the exact claim
with `context-id#claim-id`:

```json
{
  "embed.semantic": {
    "title": "Reviewed EMBED semantics",
    "kind": "data_representation",
    "scope": "embed_general",
    "profiles": [],
    "summary": "Reviewed portable meanings.",
    "domains": ["identity"],
    "search_terms": ["clinical semantics"],
    "related_concepts": ["identity.patient_identifier"],
    "related_tables": [],
    "related_relationships": [],
    "claims": [
      {
        "id": "patient-meaning",
        "statement": "A patient object represents one person.",
        "status": "verified",
        "sources": ["embed.semantic-source"],
        "caveats": []
      }
    ],
    "workflow_steps": [],
    "caveats": []
  }
}
```

The secondary profile layer binds that feature to a physical column:

```json
{
  "table": "clinical_data_anon",
  "column": "empi_anon",
  "concept": "identity.patient_identifier",
  "grain": "wide_row",
  "role": "wide_projection",
  "physical_type": "int64",
  "nullable": false
}
```

These are individual map entries or nested records, not a complete top-level
catalog. Use the checked-in catalog and JSON Schema for complete surrounding
shapes.

## Portable clinical-semantic entities

### Clinical objects

`clinical_objects` contains one entry per independently meaningful clinical
entity or observation. Each entry requires:

- `label` and `definition`;
- `grain`, a nonblank description of what one instance represents;
- controlled `domains` and discovery-oriented `search_terms`;
- zero or more `claim_refs`; and
- explicit `caveats`.

The initial model can therefore distinguish a patient, imaging episode, exam,
breast side, imaging finding, imaging interpretation, procedure, pathology
observation, pathology diagnosis, report, and risk assessment without claiming
that each object occupies a separate table.

### Concepts and missing states

Each record in `concepts` includes a stable feature identity, label, definition,
feature kind, domains, search terms, caveats, evidence labels, and optional
vocabulary reference, together with:

- required `objects`, identifying the clinical objects that own the feature;
- optional `claim_refs`;
- optional structured `missing_states`;
- optional `temporal_semantics` references; and
- optional `aggregations` references.

Non-technical concepts must own at least one clinical object. A technical
concept may use an empty `objects` array because a storage index or processing
field need not have independent clinical meaning.

Each missing-state entry has a local `id`, a source `representation`, its
clinical `meaning`, claim references, and caveats. Missingness is field-specific:
an unattached-pathology state is not a diagnosis code, and a null value must not
be silently converted to a negative clinical state.

### Semantic relationships

`semantic_relationships` connect clinical-object IDs independently of storage.
Each relationship records:

- `kind`, `source_object`, and `target_object`;
- directional `cardinality` as targets per source and sources per target;
- endpoint `optionality` for both source and target;
- an `attribution` statement and explicit `attribution_limitations`;
- a human-readable `temporal_qualification` and structured
  `temporal_semantics` references;
- domains, search terms, claim references, and caveats.

Cardinality uses `exactly_one`, `zero_or_one`, `one_or_more`, `zero_or_more`,
or `unknown`. Optionality uses `required`, `optional`, or `unknown`.
Cardinality, optionality, and attribution are distinct claims. For example, an
optional many-to-many pathology-to-finding attribution cannot be simplified to
a one-to-one join merely because one profile supplies matching columns.

### Temporal semantics

`temporal_semantics` names what a candidate time means rather than selecting a
universal anchor. Each entry contains:

- `kind`: event, documentation, or availability time;
- a clinical `meaning`;
- related `objects` and `feature_refs`;
- `relative_to` references to other temporal semantics;
- domains, search terms, claim references, and caveats.

`relative_to` points from a time to candidate reference times that are
generally upstream of it in the represented clinical context. It supports
timeline navigation but does not assert universal ordering, causality,
certainty, or a required interval. Exceptions and strength of the timing claim
belong in the meaning, caveats, and linked semantic relationship's temporal
qualification. Cycles are invalid.

Exam study time, procedure time, specimen collection time, pathology report
time, and data availability answer different questions. A profile can mark a
clinically meaningful time as unsupported through `coverage`; absence of a
binding must not cause the catalog to invent a date. The catalog does not
designate any candidate as a universal diagnosis date. A temporal semantic
without `feature_refs` must have `unsupported` or `unresolved` coverage for
every declared profile, either through profile-specific records or one
applicable general record.

### Aggregations

`aggregations` describes movement between clinical objects and features. Each
entry identifies:

- a controlled `status`;
- `source_object`, `target_object`, and `source_concept`;
- a nullable `result_concept`;
- the semantic relationships that establish grouping or attribution;
- the `method` and relevant `ordering`; and
- domains, search terms, claim references, and caveats.

`provided` documents a supplied rollup. `analyst_defined` means the transition
requires an analysis-specific policy. `unsupported` records that the catalog or
selected representation does not supply the transition. `unresolved` preserves
insufficient evidence. A null `result_concept` is explicit: it means there is
no registered result feature for that transition, not that a default should be
calculated. The source concept must belong to the source object, and any result
concept must belong to the target object; validation rejects cross-grain
transitions whose feature ownership contradicts their declared endpoints.

Aggregation status describes the registered semantic transition, not support
in every profile. A selected profile supports a supplied transition only when
profile-scoped `coverage` says so and the result concept has a feature binding.
Future profiles may bind the same portable aggregation or explicitly record it
as unsupported.

### Reusable guardrails

`guardrails` contains interpretation constraints that apply across research
questions. A guardrail has a title, statement, rationale, scope, profile list,
domains, search terms, claim references, caveats, and links to relevant
objects, concepts, semantic relationships, temporal semantics, aggregations,
and coverage entries.

Guardrails can state, for example, that absent pathology is not a negative
diagnosis, imaging assessment is not pathology truth, downstream data may leak
future information, many-to-many attribution requires reconciliation, or grain
changes require an explicit aggregation policy. They do not define cases,
controls, windows, exclusions, or preferred pipelines.

General-clinical and EMBED-general guardrails have an empty `profiles` list.
Profile-specific guardrails declare at least one profile.

### Coverage

`coverage` makes supported, unsupported, unresolved, and uncataloged areas
discoverable. Each entry identifies a `subject_kind`, a stable `subject`,
status, scope, profiles, summary, domains, search terms, claim references, and
caveats.

The subject kind is one of `clinical_object`, `concept`,
`semantic_relationship`, `temporal_semantic`, `aggregation`, `guardrail`, or
`topic`. References resolve to the corresponding collection except `topic`,
which is a stable navigation identifier. Profile scope follows the same rule as
guardrails: only profile-specific coverage declares profiles.

`unsupported` is an affirmative representation statement, while
`not_cataloged` says the portable catalog has no registered semantic coverage.
Neither state means that the clinical event did not occur.

## Evidence and provenance

Substantive portable assertions link to context claims with
`context-id#claim-id`. The fragment form distinguishes a single reviewed claim
from an entire context and must resolve exactly.

Contexts retain the version-4 claim model:

- each claim has a stable local ID, review status, one or more source IDs, and
  caveats;
- a context is homogeneous in scope;
- general-clinical and EMBED-general contexts cannot point at profile tables or
  physical relationships;
- profile-specific verified claims require evidence applicable to that
  profile; and
- contradicted claims retain enough provenance to expose the conflict.

Review statuses remain:

- `verified` — directly supported at the declared scope;
- `reconciled` — reviewed evidence has been combined into a qualified claim;
- `unverified` — useful material has not passed applicable review;
- `unresolved` — available evidence does not establish the meaning; and
- `contradicted` — retained evidence conflicts with current interpretation.

Clinical-workflow contexts may preserve ordered source claims, but workflow
steps are provenance, not the conceptual object graph. Semantic relationships
carry the portable adjacency and limitations.

Source locators remain typed as stable HTTPS URLs, repository-relative paths,
or logical artifact names. Absolute paths and parent traversal are invalid.
Release-schema and release-legend sources identify the profiles they support.

## Profile binding layer

`profile_bindings` is keyed by profile, so nested records omit the redundant
`profile` field. The containing key supplies profile identity. Core validation
requires the binding keys to match `profiles`.

### Feature bindings

`feature_bindings` preserves the version-4 physical feature metadata except for
the moved profile:

- table and column;
- semantic concept ID;
- controlled binding grain and binding role;
- physical type and schema nullability; and
- optional closed parameters and notes.

The only defined parameter is `parameters.slot`, and it is reserved for
`pathology.diagnosis_code_slot`. Every binding for that exact concept must
provide a positive, non-boolean integer slot; every other concept must omit
`parameters`. Slot values are not globally constrained to the current
profile's 1–10 range. When `notes` is present, it contains at least one
nonblank qualification. No note may record empirical counts or frequencies.
The profile-qualified physical identity is derived as `profile:table.column`.

### Object bindings

`object_bindings` explains how a clinical object is represented in a profile.
Each record identifies the object, table, relevant columns, representation,
claim references, and caveats. The controlled representations are:

- `canonical` — the profile's primary representation of the object;
- `partial` — only part of the object is represented;
- `co_located` — the row contains this object alongside other objects;
- `projection` — a convenience or denormalized representation; and
- `reference` — the row refers to, rather than fully represents, the object.

`columns` may be empty when the table-level row representation is the relevant
claim. An object binding does not imply that the object has a unique row or
that every object instance is captured. Its claim references must apply to the
containing profile; evidence scoped only to another release or layout cannot
substantiate the binding. Because object bindings have no standalone stable ID
or exact getter, object, discovery, and profile-table responses resolve each
binding's claims, contexts, and sources in an embedded `provenance` section.

### Tables and physical relationship bindings

`tables` retains profile-specific table grain, natural and technical key
candidates, uniqueness, completeness, evidence, and caveats. A key candidate
is descriptive metadata, not a database constraint.

`relationship_bindings` retains the version-4 physical relationship shape
except for the moved profile. It includes:

- stable physical relationship ID and kind;
- ordered source and target table-column endpoints;
- source completeness and bidirectional physical cardinality;
- evidence, caveats, and join hazards;
- zero or more linked `semantic_relationships`; and
- claim references.

Physical relationship kinds remain `hierarchy`, `reference`, and `projection`.
They are not interchangeable with the portable semantic relationship kinds.
A binding can support several semantic relationships or none, and a semantic
relationship may require several physical bindings.

Endpoint tuples must resolve to feature bindings in the same profile, have
equal arity and compatible physical types, and respect documented key
uniqueness and completeness. Hierarchy cycles are invalid; reference and
projection cycles can be legitimate. These checks do not prove clinical
capture, attribution completeness, or temporal co-availability.
Relationship-binding claim references are also constrained to evidence
applicable to the containing profile.

The footer-only source-profile verifier checks the table, column, type, and
schema-nullability surface derived from feature bindings. It does not scan
clinical values or establish keys, referential coverage, cardinality,
attribution, or outcome capture.

## Identity and cross-reference rules

Top-level semantic collections are keyed by stable lowercase identifiers.
Clinical-object, concept, relationship, temporal, aggregation, guardrail,
coverage, vocabulary, source, and context IDs occupy distinct namespaces but
must not be silently reinterpreted across kinds.

A concept ID identifies one meaning, not one physical occurrence. Equivalent
columns across normalized tables, denormalized views, databases, or releases
bind to the same concept. A new concept is required when clinical meaning
changes. Finding-level features and side-, exam-, or patient-level aggregates
are distinct unless the definition remains true at every represented object.

Core validation supplements JSON Schema by resolving:

- concept ownership and optional vocabulary, temporal, and aggregation links;
- semantic relationship endpoints;
- aggregation object and concept references;
- guardrail links;
- coverage subjects;
- every claim reference and source;
- every profile, table, column, key, and physical relationship reference; and
- the exact equality of declared profiles and `profile_bindings` keys.

## Discovery behavior

`discover` is the clinical-first query surface. It searches:

- clinical objects and concepts;
- semantic relationships;
- temporal semantics and aggregations;
- guardrails and coverage;
- relevant context claims.

It does not require a table name or stable identifier. Results expose the
entity kind and ID, score, matched fields, matched terms, and unmatched query
terms. Exact getters provide the complete entity after discovery. Profile
binding lookup is a secondary navigation step.

Portable `search_terms` contain clinical synonyms, not release column aliases.
When `profile` is selected, discovery may additionally index that profile's
table and column names and reports those matches as `binding.table` or
`binding.column`. An unprofiled clinical query therefore does not silently
promote physical names into the ontology.

Discovery diagnostics distinguish:

- filters that excluded otherwise matching entities;
- an unknown controlled filter;
- a vocabulary mismatch;
- explicitly unsupported coverage in a selected profile; and
- no indexed catalog coverage.

An empty result is therefore not presented as evidence that a clinical state,
event, or relationship is absent from the dataset. Deterministic token
matching remains transparent and dependency-free; results are sorted
deterministically.

Exact semantic getters return `kind`, `identifier`, the kind-specific entity,
and two computed sections:

- `related` contains stable IDs for adjacent objects, features,
  relationships, time semantics, aggregations, guardrails, and coverage as
  applicable, plus relevant object or relationship bindings;
- `provenance` resolves direct claim references into claim statements and
  review status, context titles and scope/profiles, and complete source
  records.

These sections are derived from the validated graph on every lookup. They are
not additional author-maintained adjacency or evidence copies.

The exact surfaces are:

- CLI: `object`, `feature`, `semantic-relationship`, `temporal`,
  `aggregation`, `guardrail`, `coverage`, and `context`;
- Python: `get_clinical_object`, `get_feature`,
  `get_semantic_relationship`, `get_temporal_semantic`, `get_aggregation`,
  `get_guardrail`, `get_coverage`, and `get_context`; and
- MCP: the corresponding `get_*` tools.

`get_context` follows the same envelope. Its `context` entity contains the
complete claims and optional workflow order; `related` lists referenced
features, profile tables, and physical relationship bindings; `provenance`
qualifies every local claim as `context-id#claim-id` and resolves its complete
source records.

CLI JSON responses wrap these core results in
`{"ok": true, "command": "...", "data": ...}`. Runtime and usage errors use
`{"ok": false, "command": "...", "error": {"type": "...", "message": "..."}}`
and exit with status 2. MCP inputs are closed against undeclared arguments.
Results are structured JSON objects, but MCP output schemas remain generic so
new explanatory fields do not require a tool-schema change.

## Adding semantic content

When extending the portable model:

1. Identify the clinical object and its instance grain before naming columns.
2. Reuse an existing object, concept, vocabulary, temporal semantic, or
   aggregation when meaning is unchanged.
3. Add semantic relationships with explicit direction, cardinality,
   optionality, attribution limits, and temporal qualification.
4. Attach claim references at the narrowest supported scope.
5. Register missing and unknown states without converting absence to a clinical
   negative.
6. Record supplied, analyst-defined, unsupported, and unresolved aggregation
   transitions explicitly.
7. Add reusable guardrails only when they constrain interpretation across
   questions.
8. Add coverage entries for important unsupported, unresolved, or uncataloged
   topics so discovery can explain gaps.
9. Add no physical names until the portable assertion is independently clear.

## Adding a profile

To bind another EMBED representation:

1. Add the stable profile ID and one matching `profile_bindings` entry.
2. Reuse the portable semantic collections without copying them.
3. Add feature bindings for physical columns.
4. Add object bindings, including partial, co-located, projected, and reference
   representations.
5. Declare every bound table, its binding grain, and assessed key candidates.
6. Add physical relationship bindings and link them to semantic relationships
   only where the representation supports that claim.
7. Preserve dangling references, row multiplication, nullable components,
   attribution gaps, and temporal leakage as caveats or join hazards.
8. Add profile-scoped claims and coverage only with applicable evidence.
9. Validate the footer surface and separately substantiate semantic capture,
   keys, joins, attribution, and availability.

Profile-specific statistics remain outside the portable catalog.

## Schema evolution

Content additions that preserve the documented contract can retain schema
version 5. Changes to required fields, field meaning, identifier resolution,
controlled facets, or query semantics require an explicit schema-version
decision and synchronized format, architecture, interface, and usage
documentation. Readers must reject unsupported versions rather than ignore
fields.
