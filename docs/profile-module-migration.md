# Profile-module migration

## Status and outcome

This document defines the agreed target state for the schema-v7 migration from
one closed catalog file to a composable catalog set. It is the durable
implementation reference for the active schema-v7 catalog-set contract.

The implemented catalog set lets the same EMBED clinical-semantic backbone load independently
authored physical profiles, including public V1, public V2, and uncommitted
internal working versions, without copying portable clinical meaning into every
profile or treating `open-v2` as part of the runtime structure. It must also
support explicitly selected project extensions that add work-in-progress
tables and features or intentionally reinterpret an existing concept without
claiming that the project representation belongs to the underlying dataset
release.

The composed result must preserve the current clinical-first Python, CLI, and
MCP query behavior where the answer is unambiguous. A profile and every project
extension remain descriptive, count-free, and non-executable. Loading any
module must never require access to clinical rows or local EMBED artifacts.

## Design principles

The migration follows these principles:

- portable semantic records retain stable meanings independent of a release or
  project;
- dataset profiles describe release-specific representation and evidence;
- project extensions describe project-owned additions or intentional revisions
  to one selected profile;
- every contribution retains its owning module, lifecycle, and applicability in
  the effective catalog;
- accidental or undeclared collisions are errors, while intentional semantic
  reinterpretation and binding replacement use explicit typed revisions;
- original records remain addressable and unchanged even when a project view
  prefers a replacement;
- composition never uses file order, JSON Patch, deep merge, or last-file-wins
  behavior; and
- dependencies are acceptable when they remove duplicated architecture or add
  clear capability. Minimal architecture, rather than zero dependencies, is
  the objective.

## Assessment of the current coupling

Schema v6 already distinguishes portable records from `profile_bindings` in
the object model, but the serialized, validation, and query contracts are
monolithic:

- `catalog/catalog.json` must declare at least one profile and contain a
  matching nonempty `profile_bindings` entry;
- `Catalog.from_mapping` parses and validates the portable graph and every
  profile in one operation;
- `load_catalog` accepts one JSON path, and the CLI and MCP server expose only
  that path;
- packaging installs one catalog and one schema resource;
- profile-specific sources, contexts, guardrails, and coverage share top-level
  registries with portable records;
- portable objects, concepts, relationships, temporal semantics, aggregations,
  and guardrails directly cite claims from `open-v2` contexts; and
- the immutable `Catalog` flattens records and bindings into global indexes
  without retaining contribution ownership.

The vocabulary placement is a further coupling. A concept currently selects
one vocabulary globally even when a released code list or its interpretation
may differ by profile. Moving only `profile_bindings` into another file would
therefore leave evidence, constraints, value semantics, discovery, and exact
query results tied to V2.

The direct Open V2 claim references are not a mechanical file-placement issue.
They require a module-owned qualification layer so composed results can recover
profile evidence without mutating portable records or exposing it when the
profile is not active.

## Target catalog set

Schema v7 uses independently validated document types:

```text
catalog/
├── catalog-set.json
├── catalog-set.schema.json
├── semantic/
│   ├── catalog.json
│   └── catalog.schema.json
├── profiles/
│   ├── profile.schema.json
│   └── open-v2.json
└── extensions/
    └── extension.schema.json
project-configs/
└── example-project.json
```

`catalog-set.json` is a small manifest. It identifies one semantic catalog,
the default profile modules included in a distribution, and any deliberately
selected extension modules. Installed public behavior remains
zero-configuration because the bundled manifest selects `open-v2` and no
project extensions by default.

The semantic catalog contains only portable registries, portable provenance,
portable vocabularies, and controlled values. It validates with no physical
profile loaded. A profile module contains one profile identity, its physical
binding, release-specific provenance and coverage, and module-owned
qualifications that connect its evidence to existing portable IDs.

An internal catalog set can select the bundled semantic catalog and an external
internal profile, or a caller can supply explicit profile paths. No internal
profile or evidence is copied into the public package.

The composition hierarchy is:

```text
portable semantic catalog
└── selected dataset profile
    └── zero or more explicitly selected project extensions
        └── dependent project extensions, when declared
```

A dataset profile answers, “How does this EMBED version represent the shared
clinical model?” An extension answers, “What does this project add, derive, or
intentionally reinterpret in that selected representation?” Keeping those
identities separate prevents a project table from being mistaken for part of
Open V2 or an internal primary release.

## Resource locators

Manifest resource references use an explicit closed locator union. A bundled
resource is resolved through package resources:

```json
{
  "semantic_catalog": {
    "kind": "bundled",
    "resource": "semantic/catalog.json"
  }
}
```

An external resource is resolved relative to the manifest that contains it:

```json
{
  "semantic_catalog": {
    "kind": "file",
    "path": "../shared/semantic/catalog.json"
  }
}
```

The same locator shapes apply to manifest-selected profiles and extensions.
Explicit CLI `--profile-file` and `--extension-file` arguments are ordinary
filesystem paths supplied by the caller. The loader does not expand environment
variables, search directories, inspect user-home locations, or infer modules
from the working directory.

Errors identify the containing manifest field, source file, and JSON path.
Effective-configuration fingerprints use canonical validated document content
and module identities, never absolute filesystem paths.

## Module identity and contribution ownership

Every composed record retains a contribution origin containing:

- document kind and module ID;
- module version when applicable;
- lifecycle status when applicable;
- target profile when applicable; and
- whether the contribution is portable, released profile content, or project
  content.

The composer may materialize an immutable `Catalog` query view, but it must not
discard this origin information while flattening indexes. Origin may be stored
on records or in an immutable sidecar index keyed by contribution identity.
Every exact and discovery result can therefore distinguish portable meaning,
released representation, and project-owned changes.

Every list record that can be referenced, qualified, revised, or returned in
provenance has an authored stable ID. This includes feature bindings, object
bindings, relationship bindings, relationship paths, qualifications, lineage
records, and revisions. Table identity remains profile-qualified and stable.

Three identities remain distinct:

```text
contribution identity
  project.demographic-availability.binding.cleaned-race

physical occurrence
  open-v2:cleaned_demographics.race

semantic target
  project.demographic-availability.cleaned_race
```

Two contributions may intentionally describe the same physical occurrence.
That is not automatically a collision. The composer rejects the composition
only when the effective interpretation is ambiguous and no allowed coexistence
or typed revision is declared.

## Qualification contract

Free-form semantic overlays are not permitted. Profiles and extensions use a
common `qualifications` registry to associate module-owned evidence,
applicability, and caveats with an existing semantic record.

A qualification has a closed shape equivalent to:

```json
{
  "id": "open-v2.qualifications.exam-time",
  "subject": {
    "kind": "temporal_semantic",
    "id": "time.exam-event"
  },
  "applicability": "supported",
  "summary": "Open V2 represents this through the exam study date.",
  "claim_refs": [
    "open-v2.temporal-availability-context#date-representation"
  ],
  "caveats": []
}
```

The exact schema follows these rules:

- `subject.kind` names a controlled portable semantic collection and
  `subject.id` resolves within that collection;
- applicability values initially include `supported`, `unsupported`,
  `unresolved`, and `interpretation_limit`;
- the qualification is active only when its owning profile or extension is
  active and applicable to the selected view;
- it may add evidence-backed qualifications and caveats but cannot replace a
  definition, ownership, grain, relationship cardinality, time meaning,
  aggregation behavior, or guardrail statement;
- its claims must resolve within the owning module or an explicitly permitted
  dependency; and
- constraints, provenance, discovery, and exact getters derive module-specific
  information from qualifications rather than copying it into portable
  records.

Guardrail applicability uses this same registry with `guardrail` as the subject
kind. A separate `guardrail_applicability` collection is unnecessary.
Profile-specific support and gaps that need discoverable stable records remain
under profile or extension `coverage`; qualifications do not replace coverage.

## Profile-module contract

A profile module has a closed shape equivalent to:

```json
{
  "$schema": "./profile.schema.json",
  "profile_schema_version": 1,
  "profile": {
    "id": "open-v2",
    "label": "EMBED Open Data V2"
  },
  "requires": {
    "semantic_schema_version": 7
  },
  "sources": {},
  "contexts": {},
  "coverage": {},
  "qualifications": {},
  "vocabularies": {},
  "profile_binding": {
    "feature_bindings": [],
    "object_bindings": [],
    "tables": [],
    "relationship_bindings": [],
    "relationship_binding_paths": []
  }
}
```

The exact schema follows these rules:

- A module defines exactly one profile. Profile IDs remain stable identifiers,
  not display names or implicit ordering labels.
- A module cannot add or redefine a clinical object, concept, semantic
  relationship, temporal semantic, aggregation, or guardrail. New portable
  meaning belongs in the semantic catalog and is reused by profiles.
- Qualifications connect release evidence and constraints to existing portable
  IDs without mutating them.
- Coverage records remain in the profile module because support and unresolved
  gaps are assertions about a selected representation. Their stable IDs remain
  profile-qualified.
- Release-specific sources and contexts remain in the profile module. Their IDs
  are profile-qualified. General clinical and EMBED-wide sources and contexts
  remain in the semantic catalog.
- A feature binding may select a profile vocabulary. A concept retains a
  semantic-catalog vocabulary only when the code meanings are genuinely
  portable across profiles. Occurrence-specific exceptions remain on the
  binding.
- Physical table names, columns, types, keys, identities, relationships, and
  relationship paths remain exclusively under `profile_binding`.
- Every binding carries an authored stable ID in addition to its physical
  occurrence tuple.

If a working dataset version changes the clinical meaning of a field rather
than its physical occurrence or value representation, it must bind to a
different portable concept. Dataset profiles do not hide semantic drift with
overlays or profile inheritance.

## Project-extension contract

An extension module is a separately versioned, explicitly selected layer over
one dataset profile. It supports work such as a cleaned demographic table, a
harmonized value set, a derived feature, or an intentional project-specific
reinterpretation of an existing feature.

A closed extension document has a shape equivalent to:

```json
{
  "$schema": "./extension.schema.json",
  "extension_schema_version": 1,
  "extension": {
    "id": "project.demographic-availability",
    "version": "0.1.0",
    "label": "Demographic availability prototype",
    "lifecycle_status": "work_in_progress"
  },
  "applies_to": {
    "profile": "open-v2"
  },
  "requires": {
    "semantic_schema_version": 7,
    "profile_schema_version": 1,
    "extensions": []
  },
  "semantic_additions": {
    "concepts": {}
  },
  "qualifications": {},
  "feature_lineage": {},
  "sources": {},
  "contexts": {},
  "coverage": {},
  "vocabularies": {},
  "binding_additions": {
    "feature_bindings": [],
    "object_bindings": [],
    "tables": [],
    "relationship_bindings": [],
    "relationship_binding_paths": []
  },
  "revisions": []
}
```

The initial extension contract deliberately limits `semantic_additions` to
project-scoped concepts. Additional clinical objects, semantic relationships,
temporal semantics, aggregations, or guardrails require a later explicit schema
decision backed by a concrete use case.

The extension contract follows these rules:

- `applies_to.profile` names exactly one loaded dataset profile. An extension
  cannot float across profiles merely because releases have similarly named
  tables or columns.
- Extension IDs and all contributed stable IDs are namespace-qualified. An
  extension-owned ID begins with the full extension ID followed by `.`.
- Project-scoped concepts carry lifecycle and origin metadata. They do not
  become part of the portable EMBED backbone merely because they are queryable
  in the effective catalog.
- Existing portable concepts are reused whenever the project changes
  availability or physical representation but not meaning.
- Qualifications follow the same additive restrictions as profile
  qualifications.
- Project sources, contexts, coverage, and vocabularies are local to the
  extension. Another extension may reference them only through an explicit
  dependency.
- `binding_additions` can add physical tables and bindings or bind additional
  columns on an existing table. A table addition cannot mutate a released
  table's grain, keys, identity semantics, or existing columns.
- An extension never implies that one of its tables or features is distributed
  in the target dataset profile. Results retain the contributing extension ID,
  version, and lifecycle status.

Initial lifecycle values are `work_in_progress`, `candidate`, `adopted`, and
`deprecated`. Lifecycle is authoring and distribution state, not evidence
quality or scientific validity. Claim review status remains separately
recorded on context claims.

### Descriptive feature lineage

Each feature-lineage record identifies:

- one output concept;
- input concepts and, when profile-specific, input binding IDs;
- a concise semantic derivation summary;
- the target profile and contributing extension;
- claim references, known limitations, and lifecycle status; and
- an optional source locator for separately governed implementation material.

Lineage does not contain SQL, dataframe expressions, executable predicates,
embedded code, empirical counts, or clinical values. It explains what the
derived feature represents and where it came from; it does not run or validate
the feature pipeline. Existing aggregation records remain reserved for
clinically meaningful grain transitions rather than general ETL lineage.

## Intentional project revisions

Project work may intentionally change meaning. The composer therefore rejects
undeclared ambiguity, not every overlapping contribution. The first extension
schema supports two typed revisions.

### `reinterprets_concept`

A concept reinterpretation:

- identifies one existing portable or dependency-owned concept;
- identifies one replacement concept owned by the declaring extension;
- states the semantic difference, reason, claim references, and known
  limitations;
- keeps both concepts queryable under their original stable IDs; and
- prefers the replacement only inside the effective project view in which the
  extension is active.

The original stable ID always retains its original meaning. Requesting it
returns the original record plus effective-view metadata such as
`superseded_in_view` and the replacement ID. Discovery and implementation
navigation may prefer the project concept while clearly labeling its ownership
and lifecycle.

### `replaces_binding`

A binding replacement:

- identifies one released-profile or dependency-owned binding by stable ID;
- identifies one replacement binding owned by the declaring extension;
- records the reason, claim references, limitations, and whether the original
  remains an alternative in the effective view;
- keeps the original binding intact and directly queryable; and
- prefers the replacement only in the applicable project view.

The replacement does not claim that its table or column belongs to the released
dataset. Arbitrary cross-kind supersession, mutation of portable definitions,
and general-purpose record versioning are outside the initial contract.

## Layer dependencies and conflicts

Extensions form an explicit dependency graph, not an ordered list of patches.
The loader topologically resolves `requires.extensions` and rejects missing
dependencies and cycles. Independent extensions compose identically in any
file order.

Composition is additive unless a supported typed revision explicitly changes
the preferred record in the effective project view. Duplicate module IDs,
contribution IDs, source IDs, context IDs, coverage IDs, vocabulary IDs, or
revision IDs are errors. Duplicate physical occurrences are validated for
semantic compatibility and require explicit coexistence or revision when they
would otherwise create ambiguity.

An extension cannot revise a record from an undeclared extension dependency.
It cannot mutate a base profile or portable semantic record in place. Typed
revisions preserve the original record, replacement, reason, and evidence in
provenance.

## Deterministic composition and validation

Runtime validation uses Draft 2020-12 JSON Schema before domain-object parsing.
`jsonschema` becomes a core dependency because it makes the checked-in schemas
the executable shape contract and removes duplicated closed-shape validation
from the Python parser. The runtime still rejects duplicate JSON keys and
non-standard numeric constants before schema validation.

Custom Python validation remains responsible for graph closure, provenance
scope, clinical ownership, profile isolation, lifecycle, identity,
occurrence, physical-path, dependency, and revision invariants. No additional
modeling or configuration framework is introduced merely to wrap JSON Schema.

The loader validates in this order:

1. Decode every document with duplicate-key and non-finite-number rejection.
2. Validate the manifest, semantic catalog, selected profile modules, and
   selected extension modules against their standalone JSON Schemas.
3. Parse validated documents into immutable module records while retaining
   contribution origins.
4. Reject duplicate module and contribution IDs.
5. Resolve extension dependencies and reject missing dependencies, cycles, and
   extensions whose target profile is not selected.
6. Resolve every qualification, binding, lineage input, context link, claim
   reference, coverage subject, and revision against the semantic catalog and
   permitted module dependency closure.
7. Validate physical-occurrence compatibility and typed revision authority.
8. Materialize one immutable effective `Catalog` view with origin,
   applicability, lifecycle, and revision indexes intact.
9. Run the existing cross-reference, scope, clinical-semantic, identity,
   occurrence, and physical-path invariants over the effective graph.
10. Compute a canonical effective-configuration fingerprint from validated
    module content and identities.

Composition never depends on profile or extension file order. A profile can
refer to portable records and records inside its own module, but not to another
profile's sources, contexts, coverage, vocabularies, bindings, qualifications,
or claims.

The semantic catalog validates and supports semantic queries without profiles.
Cross-profile checks run only after profiles are selected. A selected profile
with incomplete reference closure is an error rather than a partially usable
catalog.

An extension validates against its target profile without unrelated profiles
or extensions. A dependent extension validates against the explicit closure of
its dependency graph. The effective configuration records semantic schema
version, profile IDs and profile-schema versions, extension IDs and versions,
and the deterministic fingerprint.

## Effective-view and query behavior

Loading a catalog set creates an effective view. Loading an extension makes its
records queryable, but their applicability remains restricted to the
extension's target profile and dependency closure.

- An extension-owned stable ID can be retrieved whenever its extension is
  loaded.
- Selecting another profile excludes that extension's records from discovery
  and implementation results.
- Unprofiled discovery may return loaded extension content, but labels it as
  project-owned and reports target profile and lifecycle.
- Portable exact results report profile qualifications, extension
  qualifications, and active revisions in separate sections rather than
  merging them into the portable entity.
- Loading the target profile without the extension reproduces the released
  profile view.

Query-time extension filters are not part of the initial interface. The loaded
catalog set defines the project view. A separate filter can be added later if a
real need emerges for interactively switching among many loaded independent
extensions.

### Profile selection and ambiguity

The no-profile behavior remains convenient only when the answer is
unambiguous:

- with no loaded profile, semantic getters return portable meaning only;
- with exactly one applicable loaded profile, callers may omit the profile;
- with several loaded profiles, portable fields can still be returned without
  a profile, but any operation requiring differing vocabularies,
  qualifications, or bindings returns a structured ambiguity error; and
- callers can explicitly select a profile for feature lookup, code lookup,
  discovery, and other affected getters.

`get_feature`, `lookup_code`, discovery vocabulary indexing, vocabulary
mismatch diagnostics, and code inclusion all use one shared profile-aware
vocabulary-resolution policy. Feature results show the vocabulary selected by
each binding and the vocabulary resolved for the selected view.

The Python loader grows an explicit composition interface while retaining a
transition path for schema-v6 callers:

```python
load_catalog(
    catalog_set=None,
    *,
    profile_paths=None,
    extension_paths=None,
    include_default_profiles=True,
    include_default_extensions=False,
)
```

The no-argument form loads the bundled manifest and `open-v2`. Explicit profile
and extension paths are never auto-discovered. During one deprecation window,
the positional path may identify a legacy schema-v6 monolith. Document type is
determined by closed discriminator fields, not filename guessing.

CLI and MCP startup add repeatable `--profile-file PATH`, repeatable
`--extension-file PATH`, and options to exclude manifest defaults. `--catalog`
accepts a catalog-set manifest during the transition, with help text naming the
accepted document types. Startup errors identify the failing file and JSON path
without exposing file contents.

Affected Python, CLI, and MCP feature and code queries accept optional profile
selection. Exact and discovery results identify contributing semantic,
profile, and extension modules. Validation summaries report the manifest,
semantic schema version, profile-module schema versions, extension-module
schema versions, loaded profile IDs, loaded extension IDs and versions, and
the effective configuration fingerprint.

## Implementation sequence

### Phase 1: make JSON Schema the runtime shape contract

- Promote `jsonschema` from a development dependency to a core dependency.
- Run schema validation in the loader after strict JSON decoding.
- Remove redundant manual closed-shape checks while retaining domain parsing
  and all semantic invariants.
- Preserve schema-v6 behavior and response shapes.
- Add parity tests proving the schema and runtime reject the same shape errors.

This phase provides immediate value and reduces the duplication that would
otherwise multiply across module types.

### Phase 2: introduce module identity and qualifications

- Add immutable contribution-origin records and indexes.
- Add authored stable IDs to every binding type that needs referenceability.
- Define qualification records and composed constraint/provenance behavior.
- Exercise portable records plus synthetic profile qualifications without yet
  splitting the canonical artifact.

### Phase 3: implement manifest and profile composition

- Introduce manifest, semantic-catalog, and profile-module schemas and parsers.
- Implement bundled and file resource locators.
- Permit a semantic catalog with zero profiles.
- Refactor validation into document-local, semantic-only, profile-local, and
  composed-graph stages.
- Add synthetic tests for duplicate IDs, unknown qualification targets,
  cross-profile references, incompatible schema versions, and order
  independence.

### Phase 4: split the canonical Open V2 artifact

- Mechanically extract the V2 binding, sources, contexts, coverage,
  qualifications, and profile vocabularies.
- Remove direct Open V2 claim references from portable records and recover
  their applicable evidence through profile qualifications.
- Make the catalog-set manifest and split files canonical.
- Update packaging to include every manifest-referenced resource and standalone
  schema.
- Compare normalized Open V2 query outputs with a frozen schema-v6 fixture.
  Enumerate every intentional response-shape or provenance difference.

The old monolith remains only as a frozen compatibility/equivalence fixture or
is removed after the deprecation window. It never remains a competing manually
edited source of truth.

The checked normalized-equivalence test preserves Open V2 inventory, stable
clinical meaning, physical occurrences, vocabulary codes, resolved provenance,
and the leading clinical answer for representative discovery questions. The
intentional schema-v7 differences are:

- portable records no longer embed direct Open V2 claim references;
- profile vocabulary IDs are module-qualified and selected by bindings;
- authored binding IDs, contribution origins, qualifications, lineage, and
  effective-revision metadata appear as separate result fields; and
- discovery ties can reorder within the same normalized result set because
  nested profile claim text is indexed through subject-level qualifications
  instead of portable-record fields.

### Phase 5: add profile-aware values and interfaces

- Move release-specific vocabularies from concepts to feature bindings.
- Add shared profile-aware resolution to feature lookup, code lookup,
  discovery, and diagnostics.
- Add profile selection to affected Python, CLI, and MCP surfaces.
- Test text and JSON success, ambiguity, and error envelopes.
- Advance software and semantic schema versions and document the authoring
  migration.

### Phase 6: prove portability with a second profile

- Author a small synthetic profile, or public V1 when evidence is ready,
  without copying clinical rows, counts, or distributions.
- Validate both profiles separately and together.
- Check that no V1-only or synthetic-profile load requires an `open-v2` claim,
  source, context, coverage record, vocabulary, table, binding, or
  qualification.

The second-profile proof is an acceptance criterion for decoupling, not an
optional content expansion.

### Phase 7: introduce the minimal extension model

- Add the extension schema, dependency resolver, lifecycle controls,
  namespaced project concepts, qualifications, lineage, and additive bindings.
- Retain module origin and lifecycle in every affected result.
- Reject missing dependencies, cycles, target-profile mismatches, namespace
  violations, and undeclared binding ambiguity.
- Keep manifest default extensions disabled.

### Phase 8: add typed project revisions

- Implement `reinterprets_concept` and `replaces_binding` only.
- Preserve original records while making replacements preferred in the active
  project view.
- Surface effective status, replacement IDs, rationale, and provenance in
  exact and discovery results.
- Reject unauthorized, cyclic, cross-profile, cross-kind, or dependency-unsafe
  revisions.

### Phase 9: prove project layering with a representative case

- Create a synthetic work-in-progress extension over one checked-in profile.
- Add a secondary binding for an existing concept, one namespaced project
  concept, one descriptive lineage record, and one dependent extension.
- Exercise one representative project meaning change through
  `reinterprets_concept` and `replaces_binding`.
- Verify order-independent composition, dependency closure, lifecycle, module
  provenance, effective preference, and direct access to the original records.
- Verify that loading the target profile without the extension reproduces the
  unmodified release view.

The proof uses synthetic metadata only. It does not inspect a real project
table, clinical rows, counts, distributions, or feature values.

## Acceptance criteria

The migration is complete when:

- the portable semantic catalog validates and supports semantic queries with no
  physical profile loaded;
- `open-v2` is a selected module, not a required top-level semantic key;
- profile evidence reaches results through qualifications rather than direct
  profile claim references on portable records;
- two profiles with different tables and code sets bind the same portable
  concept without mutating it;
- profile-dependent queries either resolve through an explicit or unique
  profile or return a structured ambiguity error;
- multiple extensions add bindings and namespaced work-in-progress concepts
  without mutating the released view;
- a project can intentionally reinterpret a concept and replace a binding
  through typed revisions while both original and replacement remain
  queryable;
- every result distinguishes portable, released-profile, and project-extension
  contributions and reports applicable lifecycle and lineage provenance;
- extension dependency order is deterministic and undeclared collisions are
  rejected;
- loading one profile cannot resolve references from another profile;
- default installed CLI and MCP behavior still loads public Open V2 with no
  project extensions;
- callers can explicitly load external profiles and extensions through Python,
  CLI, and MCP startup;
- split Open V2 results have a checked normalized equivalence test against the
  frozen pre-split artifact;
- configuration fingerprints are content-based and independent of file order
  and absolute path;
- wheel inspection verifies every bundled manifest target, standalone schema,
  and entry point; and
- all validation remains count-free and requires no EMBED data.

## Deliberate non-goals

- Profiles do not inherit from or patch other profiles.
- Extensions do not use general-purpose JSON Patch, deep merge, or
  last-file-wins semantics.
- The first extension schema does not add project clinical objects,
  relationships, temporal semantics, aggregations, or guardrails without a
  later evidence-backed schema decision.
- Typed revisions do not mutate original stable records, reuse an old stable ID
  for new meaning, or provide general-purpose record versioning.
- The loader does not search directories, environment variables, working
  directories, or user-home locations for modules.
- Profile and extension modules do not contain SQL, dataframe logic, cohort
  definitions, empirical validation results, clinical data, or executable
  transformations.
- Feature lineage does not contain or execute transformation code, cohort
  logic, empirical summaries, or clinical data.
- This migration does not claim that concepts derived during V2 review are
  represented in V1 or an internal version. Each profile states support, gaps,
  and evidence independently.
