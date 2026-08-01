# Catalog-set format

## Design

Schema version 7 is a composable catalog set. Portable clinical meaning, a
released dataset representation, and project-owned changes are separate
documents:

```text
catalog-set manifest
├── semantic catalog (portable meaning)
├── zero or more profile modules (released representation)
└── zero or more extension modules (project-owned additions/revisions)
```

The checked-in public manifest selects the portable semantic catalog and the
`open-v2` profile, with no project extensions enabled by default. The catalog
remains closed, count-free, and non-executable: modules contain no SQL,
dataframe expressions, cohort predicates, clinical rows, empirical counts, or
feature values.

See [architecture v7](architecture-v7.md) for the current architecture and
[profile-module migration](profile-module-migration.md) for the complete design
and migration decisions. [Architecture v6](architecture-v6.md) is retained as
history for the preceding monolithic format.

## Documents and schemas

The canonical public resources are:

- `catalog/catalog-set.json` and `catalog/catalog-set.schema.json`;
- `catalog/semantic/catalog.json` and
  `catalog/semantic/catalog.schema.json`;
- `catalog/profiles/open-v2.json` and
  `catalog/profiles/profile.schema.json`; and
- `catalog/extensions/extension.schema.json`.

All schemas use JSON Schema Draft 2020-12 and close authored object shapes with
`additionalProperties: false`. Runtime loading rejects duplicate JSON keys and
non-finite numbers before JSON Schema validation, then enforces graph closure,
provenance scope, ownership, profile isolation, identity, physical occurrence,
dependency, and revision invariants.

### Catalog-set manifest

The manifest declares one `semantic_catalog` locator, default `profiles`, and
default `extensions`. A locator is a closed union:

```json
{"kind": "bundled", "resource": "semantic/catalog.json"}
```

```json
{"kind": "file", "path": "../shared/semantic/catalog.json"}
```

Bundled locators resolve through package resources. File locators resolve
relative to their containing manifest. The loader never expands environment
variables or searches the working directory, user home, or module directories.
Explicit `profile_paths` and `extension_paths` are caller-supplied filesystem
paths.

### Semantic catalog

The semantic catalog has `semantic_schema_version: 7` and contains the portable
controlled values plus these ID-keyed registries:

- `clinical_objects` and `concepts`;
- `semantic_relationships`, `temporal_semantics`, and `aggregations`;
- reusable `guardrails`;
- portable `coverage` statements;
- portable `vocabularies`; and
- portable `sources` and `contexts`.

It contains no physical profiles or profile coverage. It validates and supports
portable semantic queries with no profile selected. Clinical object grain is a
descriptive meaning; physical row grains remain controlled binding metadata.

Concepts define one stable meaning and clinical ownership. Missing states stay
field-specific. Relationships keep direction, cardinality, optionality,
attribution limits, and temporal qualification separate. Temporal semantics
distinguish event, documentation, and availability time and never designate a
universal diagnosis date. Aggregations distinguish supplied, analyst-defined,
unsupported, and unresolved grain transitions. Guardrails constrain
interpretation without defining a cohort or analysis policy.

Substantive assertions cite a precise `context-id#claim-id`. Each claim retains
review status, sources, and caveats. Source locators are typed HTTPS,
repository-relative, or logical artifact references; absolute paths and parent
traversal are invalid.

### Profile module

A profile document has `profile_schema_version: 1`, exactly one `profile`, and
a `requires.semantic_schema_version` value. It owns:

- release-specific `sources`, `contexts`, `coverage`, and `vocabularies`;
- `qualifications` that connect profile evidence or applicability to portable
  records; and
- one `profile_binding` containing feature, object, table, relationship, and
  relationship-path bindings.

Every binding has an authored stable ID. A feature binding names its concept,
physical table and column, type, nullability, row grain, role, optional profile
vocabulary, and occurrence-specific interpretations. Object bindings describe
partial, co-located, projected, reference, or canonical representations and
may state bounded instance identity. Table keys are descriptive candidates,
not database constraints. Relationship bindings and ordered binding paths are
descriptive physical routes, never executable joins.

Profile-owned vocabulary IDs are module-qualified (for example,
`open-v2.pathology.severity`). Bindings select those IDs explicitly, so two
profiles can attach different code sets to the same portable concept without a
global vocabulary collision.

A profile cannot add or redefine portable clinical meaning. When a release
changes meaning, it binds a different portable concept. A qualification may
add evidence, applicability, or caveats to an existing portable subject; it
cannot replace the subject's definition, ownership, grain, cardinality, time
meaning, aggregation behavior, or guardrail statement.

### Extension module

An extension has `extension_schema_version: 1`, an ID, semantic version,
lifecycle status, exactly one target profile, and explicit extension
dependencies. Initial lifecycle values are `work_in_progress`, `candidate`,
`adopted`, and `deprecated`.

An extension may contribute namespaced project concepts, qualifications,
coverage, evidence, vocabularies, descriptive feature lineage, and additive
bindings. Every extension-owned stable ID begins with the full extension ID.
Feature lineage explains inputs, output meaning, limitations, evidence, and an
optional separately governed source locator; it contains no transformation
code or clinical values.

Two typed revisions are supported:

- `reinterprets_concept` keeps the original concept addressable and names an
  extension-owned replacement preferred only in the active project view.
- `replaces_binding` keeps the original binding addressable and names an
  extension-owned replacement for the applicable view.

Extensions form a dependency graph, not an ordered patch list. Composition
rejects missing dependencies, cycles, target-profile mismatches, namespace
violations, unauthorized revisions, and undeclared ambiguity. Independent
extensions compose identically in every file order.

## Contribution origin and effective view

Every returned or referenceable contribution retains its document kind,
module ID, module version and lifecycle when applicable, target profile when
applicable, and whether it is portable, released-profile, or project content.
Original records are never mutated by qualifications or revisions.

Loading produces one immutable effective view. With no profile loaded,
semantic getters return portable meaning. With one applicable profile,
profile-dependent queries may infer it. With several loaded profiles, callers
must select a profile whenever vocabularies, qualifications, or bindings differ;
otherwise the operation returns a structured ambiguity error.

`get_feature`, `lookup_code`, discovery vocabulary indexing and diagnostics,
and code inclusion use the same profile-aware vocabulary policy. Exact results
surface portable entities, qualifications, contribution origins, applicable
constraints, lineage, and active revisions in distinct sections rather than
merging module-owned assertions into the portable record.

`lookup_code` reports the resolved vocabulary contribution as `origin`. When
the lookup also resolves through a semantic feature or physical bindings, it
reports `feature_origin` and ID-associated `binding_origins` so callers retain
the ownership, target-profile, and lifecycle boundaries used to interpret the
code.

## Python, CLI, and MCP

The Python composition interface is:

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

The no-argument form loads the bundled manifest and `open-v2`. During the
transition, the positional path may also be a legacy schema-v6 monolith; the
loader determines document type from closed discriminator fields.

CLI and MCP startup accept repeatable `--profile-file PATH` and
`--extension-file PATH`. `--no-default-profiles` omits manifest-selected
profiles; `--include-default-extensions` explicitly opts into
manifest-selected extensions. `--catalog` accepts a catalog-set manifest or a
legacy schema-v6 document. Startup errors identify the file and JSON path
without exposing file contents.

CLI `feature` and `code`, and MCP `get_feature` and `lookup_code`, accept an
optional profile. `discover` already accepts one. CLI JSON success and error
envelopes remain stable, and MCP tools remain read-only with closed input
schemas.

`validate` reports the manifest, semantic schema version, module schema
versions, loaded profile IDs, loaded extension IDs and versions, controlled
facets, contribution inventory, and content-based configuration fingerprint.
The fingerprint never incorporates absolute paths or input ordering.

## Authoring and evolution

The optional `embed-context curate` adapter maintains two separate views. Its
authored view retains validated source documents, exact bytes, module
ownership, and record addresses; only one explicitly selected filesystem
module can be changed. Its effective view is an immutable composed `Catalog`
used for navigation, constraints, provenance, and discovery. Effective query
results, qualifications, origins, and computed relationships are never
serialized into an authored module.

Draft validation substitutes the prospective authored mapping into the shared
resolved composition and reruns the version-matched schema, composition, and
domain validators. Saving writes exactly the canonical bytes shown in the
viewer and atomically replaces only the selected module after all loaded file
digests are checked.

Search existing stable IDs before adding meaning. Put portable clinical meaning
in the semantic catalog, released representation and evidence in one profile,
and project-owned additions or intentional revisions in an explicitly selected
extension. Do not copy semantics into modules or use qualifications as free-form
overlays.

Changes to required fields, controlled values, locator behavior, identity
resolution, composition, or query semantics require a schema-version decision
and synchronized schemas, validators, tests, interfaces, and documentation.
Readers reject unsupported versions rather than ignoring fields.
