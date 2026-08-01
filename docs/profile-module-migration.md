# Profile-module migration

## Status and goal

This document proposes the schema-v7 migration from one closed catalog file to
a composable catalog set. It is the implementation plan for review; schema v6
remains the active serialized contract until the corresponding migration phase
lands.

The goal is to let the same EMBED clinical-semantic backbone load independently
authored physical profiles, including public V1, public V2, and uncommitted
internal working versions, without copying portable clinical meaning into every
profile or treating `open-v2` as part of the runtime structure.

The composed result must preserve the current clinical-first Python, CLI, and
MCP query behavior. A profile remains descriptive, count-free, and
non-executable. Loading a profile must never require access to clinical rows or
local EMBED artifacts.

## Assessment of the current coupling

Schema v6 already distinguishes portable records from `profile_bindings` in
the object model, but the serialized and loading contracts are monolithic:

- `catalog/catalog.json` must declare at least one profile and contain a
  matching nonempty `profile_bindings` entry;
- `Catalog.from_mapping` parses and validates the portable graph and every
  profile in one operation;
- `load_catalog` accepts one JSON path, and the CLI and MCP server expose only
  that path;
- packaging installs one catalog and one schema resource;
- profile-specific sources, contexts, guardrails, and coverage share top-level
  registries with portable records; and
- portable objects, concepts, relationships, temporal semantics, and
  aggregations directly cite claims from `open-v2` contexts.

The vocabulary placement is a further coupling. A concept currently selects
one vocabulary globally even when a released code list or its interpretation
may differ by profile. Moving only `profile_bindings` into another file would
therefore leave both evidence and value semantics tied to V2.

## Target catalog set

Schema v7 should use three independently validated document types:

```text
catalog/
├── catalog-set.json
├── catalog-set.schema.json
├── semantic/
│   ├── catalog.json
│   └── catalog.schema.json
└── profiles/
    ├── profile.schema.json
    └── open-v2.json
```

`catalog-set.json` is a small manifest. It identifies one semantic catalog and
the default profile modules included in a distribution. It contains paths, not
inlined catalog content. Installed public behavior remains zero-configuration
because the bundled manifest selects `open-v2` by default.

The semantic catalog contains only the portable registries and controlled
values. It must be valid with no loaded physical profile. A profile module
contains one profile identity, its physical binding, release-specific
provenance and constraints, and additive annotations that connect its evidence
to existing portable IDs.

An internal catalog set can reference the installed semantic catalog and an
external internal profile, or a caller can supply explicit profile paths. No
internal profile or evidence is copied into the public package.

## Profile-module contract

A profile module should have a closed shape equivalent to:

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
  "guardrail_applicability": {},
  "vocabularies": {},
  "semantic_annotations": {
    "clinical_objects": {},
    "concepts": {},
    "semantic_relationships": {},
    "temporal_semantics": {},
    "aggregations": {},
    "guardrails": {}
  },
  "profile_binding": {
    "feature_bindings": [],
    "object_bindings": [],
    "tables": [],
    "relationship_bindings": [],
    "relationship_binding_paths": []
  }
}
```

The exact schema should follow these rules:

- A module defines exactly one profile. Profile IDs remain stable identifiers,
  not display names or implicit ordering labels.
- A module cannot add or redefine a clinical object, concept, semantic
  relationship, temporal semantic, aggregation, or guardrail. New portable
  meaning belongs in the semantic catalog and is reused by profiles.
- `semantic_annotations` can add claim references and explicit caveats to an
  existing portable ID. It cannot replace definitions, ownership, grain,
  cardinality, time meaning, aggregation behavior, or guardrail statements.
- `guardrail_applicability` associates a portable guardrail with this profile
  and records the applicable profile claims and caveats. This avoids defining
  the same reasoning rule separately in every profile.
- Coverage records remain in the profile module because support and unresolved
  gaps are assertions about a selected representation. Their stable IDs should
  remain profile-qualified.
- Release-specific sources and contexts remain in the profile module. Their
  IDs must be profile-qualified. General clinical and EMBED-wide sources and
  contexts remain in the semantic catalog.
- A feature binding may select a profile vocabulary. A concept may retain a
  semantic-catalog vocabulary only when the code meanings are genuinely
  portable across profiles. Occurrence-specific exceptions remain on the
  binding.
- Physical table names, columns, types, keys, identities, relationships, and
  relationship paths remain exclusively under `profile_binding`.

If a working version changes the clinical meaning of a field rather than its
physical occurrence or value representation, it must bind to a different
portable concept. Profile overlays must not be used to hide semantic drift.

## Deterministic composition

The loader should validate in this order:

1. Validate the catalog-set manifest, semantic catalog, and each profile module
   against their standalone JSON Schemas.
2. Reject duplicate profile IDs and duplicate contributed registry IDs. Never
   use last-file-wins behavior.
3. Resolve every annotation, binding, context link, claim reference, coverage
   subject, and guardrail-applicability target against the semantic catalog and
   its owning module.
4. Materialize one immutable `Catalog` view with the selected profiles.
5. Run the existing cross-reference, scope, clinical-semantic, identity,
   occurrence, and physical-path invariants over the composed graph.

Composition must not depend on profile-file order. A profile can refer to
portable records and to records inside its own module, but not to another
profile's sources, contexts, coverage, vocabularies, bindings, or claims. This
keeps a profile independently loadable and prevents an internal working version
from silently depending on public V2.

The semantic catalog must also validate without profiles. Cross-profile checks
run only after profiles are selected. A selected profile with incomplete
reference closure is an error rather than a partially usable catalog.

## Query and loading interfaces

The Python loader should grow an explicit composition interface while keeping a
transition path for schema-v6 callers:

```python
load_catalog(
    catalog_set=None,
    *,
    profile_paths=None,
    include_default_profiles=True,
)
```

The no-argument form loads the bundled manifest and `open-v2`. Explicit profile
paths add or replace only through declared selection rules; they are never
auto-discovered from the working directory or environment. During one
deprecation window, the positional path may still identify a legacy schema-v6
monolith.

CLI and MCP startup should add repeatable `--profile-file PATH` and an option to
exclude manifest defaults. `--catalog` can accept a catalog-set manifest during
the transition, with help text making the accepted document types explicit.
Startup errors must identify the failing file and JSON path without exposing
file contents.

Feature and code queries need profile-aware vocabulary behavior:

- feature results identify the vocabulary selected by each binding;
- `lookup_code` accepts an optional profile;
- an omitted profile remains convenient when every selected profile resolves to
  the same vocabulary; and
- differing value sets without a selected profile produce a structured
  ambiguity error, never an arbitrary result.

All current profile filters continue to use the IDs of the composed profiles.
Validation summaries should report the manifest, semantic schema version,
profile-module schema versions, and loaded profile IDs.

## Migration phases

### Phase 1: composition foundation

- Introduce manifest and profile-module schemas plus strict parsers.
- Add synthetic tests for duplicate IDs, unknown overlay targets,
  cross-profile references, incompatible schema versions, and order
  independence.
- Permit a semantic catalog with zero profiles in the runtime model.
- Keep the checked-in schema-v6 catalog as the default artifact while the new
  composer is exercised with fixtures.

This phase changes no clinical content and provides a reversible implementation
seam.

### Phase 2: split the canonical Open V2 artifact

- Mechanically extract the V2 binding, profile sources and contexts, coverage,
  applicability, annotations, and profile vocabularies.
- Make the catalog-set manifest and split files canonical.
- Update packaging to include every manifest-referenced resource and standalone
  schema.
- Verify that the composed Open V2 catalog produces the same query results as
  the schema-v6 catalog, apart from intentional schema and provenance-shape
  changes.

The old monolith should be retained only as a temporary test fixture or removed;
it must not remain a competing manually edited source of truth.

### Phase 3: profile-aware values and interfaces

- Move release-specific vocabularies from concepts to feature bindings.
- Add profile selection to Python, CLI, and MCP code lookup and feature
  navigation.
- Update response documentation and test JSON/text success, ambiguity, and
  error envelopes.
- Advance the software and semantic schema versions and document the authoring
  migration.

### Phase 4: prove portability with a second profile

- Author public V1 or a small synthetic profile without copying any V1 clinical
  rows, counts, or distributions.
- Validate both profiles separately and together.
- Check that no V1-only load requires an `open-v2` claim, source, context,
  coverage record, vocabulary, table, or binding.
- Use the same process for internal profiles, keeping their modules and
  evidence outside the public repository when required.

The second-profile proof is an acceptance criterion for decoupling, not an
optional content expansion.

## Acceptance criteria

The migration is complete when:

- the portable semantic catalog validates and supports semantic queries with no
  physical profile loaded;
- `open-v2` is a module selected by a manifest, not a required top-level key in
  the semantic schema or parser;
- two profiles with different tables and code sets can bind the same portable
  concept without mutating it;
- loading one profile cannot resolve references from another profile;
- default installed CLI and MCP behavior still loads public Open V2;
- callers can explicitly load an external profile through Python, CLI, and MCP
  startup;
- split Open V2 results have a checked equivalence test against the pre-split
  artifact;
- wheel inspection verifies every bundled manifest target and entry point; and
- all validation remains count-free and requires no EMBED data.

## Deliberate non-goals

- Profiles do not inherit from or patch other profiles. Shared physical
  fragments can be considered later only if real duplication justifies a
  separate, explicit module mechanism.
- The loader does not search directories, environment variables, or user home
  locations for profiles.
- Profile modules do not contain SQL, dataframe logic, cohort definitions,
  empirical validation results, or clinical data.
- This migration does not claim that concepts derived during V2 review are
  represented in V1 or an internal version. Each profile must state support,
  gaps, and evidence independently.
