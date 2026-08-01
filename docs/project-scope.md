# Project scope and authoring requirements

## Purpose

This project maintains a concise clinical-semantic context backbone for agents
working with EMBED data. An unfamiliar agent should be able to begin with a
clinical question and determine:

- which clinical objects and observations are represented;
- what one instance of each object means;
- how a selected profile identifies a clinical instance, including identity
  scope and the absence of longitudinal identity;
- how objects relate, including cardinality, optionality, and attribution
  limitations;
- which features describe each object and what their codes and missing states
  mean;
- which event, documentation, and availability times are candidates for a
  timeline;
- how supplied or unsupported aggregation behaves across finding, side, exam,
  and patient levels;
- what evidence supports each assertion, at what profile scope, and which
  questions remain unresolved; and
- how a selected release binds those semantics to physical tables, columns,
  types, keys, joins, occurrence-specific interpretations, and composed paths.

The tool supplies trustworthy context for agents to design their own cohorts,
pipelines, and analyses. It does not prescribe those designs.

## Canonical deliverable

`catalog/semantic/catalog.json` is the source of truth for portable clinical
meaning. `catalog/profiles/open-v2.json` owns the released representation and
`catalog/catalog-set.json` selects the bundled defaults. Together they must
remain:

- valid against their version-matched standalone JSON Schemas;
- directly usable without a database, index service, or generated Markdown;
- clinically normalized independently of physical storage;
- explicit about evidence, coverage, missing states, uncertainty, attribution,
  time meaning, aggregation, identity scope, and occurrence interpretation;
- discoverable from clinical language without table names or stable IDs;
- safe to bind to normalized tables, denormalized views, databases, or future
  releases without copying semantic definitions; and
- count-free and non-executable.

Markdown documents explain the format and decisions but are not parsed as
catalog data. Human-readable references must be derived from the structured
catalog rather than maintained as competing sources of truth. Synchronization
is a reviewed, manual authoring responsibility; no generated-document pipeline
currently exists.

## Clinical-semantic model

Portable semantics are primary. The initial breast-imaging model represents:

```text
patient
└── breast-imaging episode
    └── imaging exam
        ├── breast side
        └── imaging finding
            └── imaging interpretation / recommendation
                └── linked procedure
                    └── pathology observation
                        └── pathology diagnosis
```

Radiology report and risk-assessment objects provide additional documentation
and clinical context. This diagram is navigation, not a deterministic workflow:
relationships can be optional, branching, many-to-many, incompletely
attributed, or unsupported in a profile.

Clinical objects define meaning and instance grain. Concepts define reusable
features owned by those objects. Semantic relationships define clinical
adjacency and attribution independently of joins. Temporal semantics,
aggregations, guardrails, and coverage capture the qualifications an agent
needs before selecting an analysis policy.

Physical tables are not the conceptual model. `profile_bindings` is a secondary
implementation layer containing:

- feature-to-column bindings;
- object-to-table representations;
- table grains and key candidates; and
- physical relationship bindings, composed binding paths, and join hazards.

A clinical object does not need its own table. One row can represent parts of
several objects, and the same semantic model can bind to a different layout.

## Breast-cancer outcome focus

The initial outcome representation must distinguish:

- invasive breast cancer;
- in-situ breast cancer;
- high-risk lesion;
- borderline lesion;
- benign finding;
- non-breast cancer; and
- unattached pathology.

The first six are represented diagnosis groups. `unattached_pathology` is a
missing or attachment state, not another diagnosis code. It does not establish
disease absence, benign pathology, adequate follow-up, or a negative outcome.

Pathology relationships must explain how observations and diagnoses can relate
to a patient, exam, breast side, imaging finding, and procedure. Finding-level
attribution can be optional or many-to-many. No foreign-key or deterministic
backfill guarantee may be inferred from a matching physical tuple.

Supplied side- and exam-level pathology severity uses the minimum value because
the represented scale is inverse. Finding-to-side, exam-to-patient, and
patient-level outcome reductions require an explicit policy unless the catalog
registers a supported aggregation. The catalog does not choose such a policy.

Outcome coverage must state what is known and unknown about capture and
follow-up. Absence of a recorded outcome is not proof that the outcome did not
occur. A represented binary endpoint may validly encode “no represented event
under this extraction policy,” but it must not be described as “never biopsied”
or “cancer-free.” Restricting an estimand to pathology-observed records is not
inherently invalid; the conditioning and its limits on generalizability must be
named.

Longitudinal pathology candidate discovery operates at patient scope even when
the requested output grain is an exam side or finding. A candidate pathology
accession belongs to the candidate pathology-associated exam and must not be
forced equal to the index exam accession.

Risk outputs with unresolved scale, horizon, model-version, exceptional-value,
or probability semantics can remain useful for association or ranking. They
must not be treated as calibrated probabilities or used for calibration and
Brier-score interpretation until those semantics are validated.

## Temporal semantics

Candidate dates are documented by what they represent, not collapsed into a
single diagnosis date. Relevant distinctions include:

- imaging-exam event time;
- procedure event time;
- specimen-collection event time;
- pathology documentation or report time; and
- the time at which information becomes available to an analysis.

Open-v2 can explicitly mark a clinically meaningful candidate such as specimen
collection time as unsupported when no supported feature represents it. The
catalog must not invent a proxy or silently substitute procedure or report
time. Missingness remains missing for the selected semantic endpoint. A
different time may be studied only as a separately named endpoint or sensitivity
analysis, never as a silent fallback or coalesced replacement.

No candidate is a universal diagnosis date. Agents and users remain responsible
for choosing task-specific anchors, follow-up windows, outcomes, exclusions,
censoring, and temporal feature boundaries. Downstream procedure, pathology, or
report information can create temporal leakage when applied to an earlier
target.

## Reusable reasoning guardrails

Guardrails state interpretation constraints that recur across analyses. Initial
coverage should include:

- null or absent pathology is not a negative diagnosis;
- imaging assessment is not pathology truth;
- downstream clinical information may cause temporal leakage;
- finding-to-pathology attribution may be optional or many-to-many;
- movement among finding, side, exam, and patient grain needs an explicit
  aggregation policy;
- different clinical timestamps answer different questions; and
- physical co-location does not prove contemporaneous availability.

Guardrails may link to relevant objects, concepts, relationships, time,
aggregation, coverage, and evidence. They must not grow into named research
workflows or encode cases, controls, exclusions, follow-up windows, or
preferred estimands. A controlled category distinguishes `prohibition`,
`analyst_choice`, and `interpretation_limit`; priority (`critical`, `high`, or
`standard`) makes the most important applicable constraints prominent without
turning them into policy.

## Discovery requirements

`discover` is the clinical-first entry point. It searches the portable semantic
collections and supporting context claims without requiring a caller to know a
table name or stable identifier.

Every match must explain why it matched through:

- entity kind and stable ID;
- matched fields and terms;
- unmatched query terms; and
- deterministic score.

Discovery uses deterministic query intents for clinically important language,
including longitudinal search, temporal fallback, probability calibration,
identity, laterality, and represented endpoints. Applicable high-priority
guardrails and unresolved coverage may receive reserved result slots. Every
boost remains visible in match reasons, explicit kind filters remain binding,
and ordering is deterministic.

No-result diagnostics must distinguish:

- filters excluding otherwise matching entries;
- unknown controlled filter values;
- vocabulary mismatch;
- explicit unsupported profile coverage; and
- no indexed catalog coverage.

An empty result must never be presented as evidence that a clinical object,
state, relationship, or event is absent from EMBED. Exact semantic getters
support follow-up navigation and return resolved constraints; profile-binding
lookup is secondary.

## Portability and count-free policy

Do not record empirical dataset summaries in the portable catalog or
agent-facing feature documentation. Prohibited examples include:

- table or row totals;
- null, non-null, blank, duplicate, or distinct-value counts;
- value frequencies or proportions;
- quantiles, observed extrema, and prevalence estimates; and
- release-specific match or cardinality measurements presented as clinical
  semantics.

The policy does not prohibit semantic numbers. Documented code values, units,
time horizons, physical types, the positive `parameters.slot` required only by
`pathology.diagnosis_code_slot` bindings, qualitative cardinality, and
genuinely defined sentinel meanings belong when they explain representation.
Schema nullability is physical metadata; how often null occurs is not.

Unresolved missing-value or sentinel behavior may be stated without a
frequency. Prefer “null semantics are not documented” over a release
measurement.

## Normalization and authoring rules

### Objects and concepts

Create one clinical object for one stable entity or observation grain. Create
one concept for one stable feature meaning and attach it to every owning
object. Reuse the concept across profiles and physical projections when meaning
is unchanged.

Create separate concepts when meaning changes. A finding-level presence flag,
side-level rollup, and exam-level rollup are not interchangeable merely because
their column names share a stem.

Technical concepts may have no clinical-object owner. They must remain
explicitly technical and must not be promoted to clinical identity, ordering,
or linkage across releases.

An object binding's optional `instance_identity` states identifying columns,
identity scope, reserved synthetic exceptions, physical rows per clinical
instance, and whether identity persists longitudinally. Row keys remain storage
metadata and must not be promoted to clinical identity.

### Missing states and vocabularies

Record field-specific missing states with their source representation, meaning,
evidence, and caveats. Do not apply catalog-wide null, delimiter, ordering,
repetition, or sentinel rules without evidence.

Reusable code dictionaries belong under `vocabularies`. Vocabulary completeness
and parsing behavior stay explicit. A released list is not automatically
exhaustive, and a composed string must not be split when delimiter semantics
are undocumented.

When the same portable concept has different value or null meaning at different
physical occurrences, record `occurrence_interpretations` on the feature
binding rather than applying one global meaning. Representation, meaning,
review status, claim references, and caveats remain occurrence-specific.

### Relationships

Every semantic relationship records:

- source and target clinical objects;
- relationship kind;
- directional cardinality;
- endpoint optionality;
- attribution meaning and limitations;
- temporal qualification;
- claim references and caveats.

These are clinical-semantic claims, not join claims. A profile's physical
relationship binding separately records tables, column tuples, source
completeness, physical cardinality, evidence, and join hazards.

When one semantic relationship requires multiple physical hops, register an
ordered `relationship_binding_paths` entry. Every step must resolve within the
same profile and adjacent endpoints must be compatible. The path is descriptive
navigation, not an executable join.

### Time, aggregation, and coverage

Temporal records distinguish event, documentation, and availability meaning.
Aggregation records distinguish provided, analyst-defined, unsupported, and
unresolved transitions. Coverage records make supported, unsupported,
unresolved, and uncataloged topics discoverable at the correct scope.

Unsupported and unresolved are useful results. Do not replace them with a
preferred proxy, derivation, or analysis default.

### Guardrails

Add a guardrail only when it constrains interpretation across research
questions. Link it to the semantic entities and claims that justify it. Do not
encode task-specific recipes, cohort alternatives, SQL, predicates, or
scientific-validity judgments.

## Evidence and source priority

When sources disagree, use the following order:

1. Facts supplied or confirmed by EMBED maintainers.
2. Definitions verified from the applicable release schema and legend.
3. Supporting internal material.
4. Public EMBED documentation and other external sources.

Public EMBED V1 material is not authoritative for V2 without verification.
External material can supply general clinical context but cannot fill a
profile-specific gap as verified release behavior.

Apply review state at claim level. Catalog membership does not itself make a
statement authoritative. Portable entities reference claims with
`context-id#claim-id`, preserving the exact assertion and scope. Conflicts and
unknowns remain traceable rather than being silently overwritten.

General clinical, EMBED-general, and profile-specific scopes remain distinct.
A profile-specific verified claim must cite applicable maintainer-confirmed,
release-schema, or release-legend evidence.

## Local source boundary

The ignored `reference_files/` directory contains local release artifacts used
to construct and verify profile bindings. Source-profile validation may read
Parquet footer schemas through the dedicated verifier and may consult the
release legend. It must not inspect or copy clinical rows, identifiers,
anonymized dates, report text, values, statistics, counts, or empirical
summaries. The directory is optional for a clone and must never be committed.

The incomplete alpha context system and Cortex knowledge-base notes are design
and hazard-discovery inputs, not runtime dependencies or unreviewed clinical
authorities. Recipes from those systems must not become executable V2 policy.
Canonical assertions still require portable sources at the applicable scope.

## Minimal tooling boundary

The catalog loader, strict validator, exact getters, binding queries, and
deterministic discovery use only the Python standard library. Embeddings,
vector databases, search services, SQLite FTS, and fuzzy-matching dependencies
remain outside the core.

The optional stdio MCP adapter calls the same core API as the CLI, writes
protocol messages only to stdout, and exposes read-only tools. The optional
local curation viewer is a separate companion distribution; its Python modules
and browser assets are not present in the base wheel.

Source distributions retain canonical resources under `catalog/`; built
wheels bundle the JSON and JSON Schema so the default loader and installed
commands do not depend on the checkout working directory. Draft 2020-12 JSON
Schema validates closed shapes and local conditions. The core validator
separately enforces graph, provenance, clinical, and profile invariants.

## Non-goals

The project does not:

- encode SQL, dataframe operations, executable joins, or pipelines;
- select preferred cohort definitions, labels, anchors, windows, exclusions,
  censoring, or aggregation policies;
- claim that a cohort or analysis is scientifically valid;
- treat physical tables or denormalized rows as the clinical model;
- anticipate every research workflow;
- provide clinical advice;
- expose clinical rows, identifiers, or report text; or
- add empirical counts or distributions to the portable catalog.

## Profile binding requirements

A profile is complete when:

- its key exactly matches one declared profile;
- each feature binding references a portable concept and a declared table;
- each nonempty object binding references a portable object, declared table,
  and bound columns;
- declared `instance_identity` is scoped and does not confuse physical rows
  with persistent clinical identity;
- occurrence interpretations qualify the physical binding whose value or null
  meaning they describe;
- every bound table has one table specification at the correct binding grain;
- key candidates state kind, uniqueness, completeness, evidence, and caveats;
- physical relationship endpoints resolve to compatible bound columns;
- relationship bindings retain source completeness, bidirectional
  cardinality, evidence, caveats, join hazards, claim references, and relevant
  semantic links;
- composed relationship paths contain valid ordered steps with compatible
  adjacent tables; and
- unsupported capture or representation is recorded through coverage rather
  than inferred from missing columns.

Footer validation verifies physical table, column, type, and schema-nullability
surfaces only. It does not establish uniqueness, referential coverage,
cardinality, clinical attribution, outcome capture, or availability.

## Documentation synchronization

Any functional catalog, CLI, MCP, curator, packaging, or schema change must
update relevant usage, format, architecture, and configuration documentation
in the same logical commit. Examples and cross-references must be checked for
stale identifiers, commands, filters, fields, and file paths. The current
architectural decision is documented in
[`architecture-v7.md`](architecture-v7.md). Earlier architecture pages are
retained as history.

## Completion criteria

A clinical-semantic change is complete when it:

- passes strict schema and core cross-reference validation;
- defines clinical meaning and instance grain independently of storage;
- records adjacent-object relationships with cardinality, optionality,
  attribution limits, and temporal qualification;
- attaches concepts to correct objects and preserves code and missing-state
  meaning;
- distinguishes event, documentation, and availability time without selecting
  a universal diagnosis date;
- records provided, analyst-defined, unsupported, and unresolved aggregation
  transitions explicitly;
- uses reusable guardrails instead of task-specific workflows;
- records supported, unsupported, unresolved, and uncataloged coverage at the
  correct scope;
- preserves claim-level provenance and unresolved questions;
- keeps profile tables, columns, types, keys, and joins in the secondary
  binding layer;
- represents bounded clinical-instance identity, occurrence-specific meanings,
  and multi-edge physical paths explicitly;
- adds no executable policy or empirical dataset summary;
- supports clinical-first discovery with match explanations and diagnostic
  no-result states, deterministic intent boosts, and constraint-aware result
  composition;
- includes focused synthetic tests and checked-in integration assertions for
  changed behavior; and
- includes synchronized documentation and a focused Git commit.
