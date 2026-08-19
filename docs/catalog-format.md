# Catalog-set format

## Documents and versions

The current catalog is a deterministic composition of:

```text
catalog-set manifest (schema 1)
├── semantic catalog (schema 8)
├── zero or more profile modules (schema 2)
└── zero or more extension modules (schema 2)
```

The public manifest selects `catalog/semantic/catalog.json` and the `open-v2`
profile. `internal-v2` is bundled as a non-default working profile; its Phase 1
binding covers the wide internal MagView clinical table. All schemas use JSON
Schema Draft 2020-12 and close authored objects with
`additionalProperties: false`.

Schema v8 has no legacy input mode. A schema-v6 monolith, semantic schema 7,
profile schema 1, extension schema 1, wrong discriminator, or unknown version
causes a fatal startup error. The loader does not silently migrate or ignore
fields.

## Catalog-set manifest

The manifest names one semantic catalog plus default profile and extension
locators. Locators are closed unions:

```json
{"kind": "bundled", "resource": "semantic/catalog.json"}
```

```json
{"kind": "file", "path": "../shared/catalog.json"}
```

Bundled resources resolve through package data. File paths resolve relative to
the containing manifest. The resolver does not scan directories, expand
environment variables, or search the working directory or home directory.

## Semantic catalog

The semantic catalog contains controlled values and ID-keyed registries for
clinical objects, concepts, semantic relationships, temporal semantics,
aggregations, guardrails, coverage, vocabularies, sources, and contexts.

Objects define clinical instance meaning and descriptive grain independently
of storage. Concepts define reusable meaning and object ownership.
Relationships retain direction, cardinality, optionality, attribution limits,
and temporal qualification. Claims cite exact `context-id#claim-id` records.

The shared catalog includes the `image` object and `clinical.exam-image`
relationship. Their presence expresses shared meaning; it does not assert that
every profile supplies an image table, file layout, or verified physical key.

## Contributions and availability

Profiles and extensions have a closed `contributions` object with all semantic
families:

```json
{
  "clinical_objects": {},
  "concepts": {},
  "semantic_relationships": {},
  "temporal_semantics": {},
  "aggregations": {},
  "guardrails": {},
  "coverage": {}
}
```

Any module may introduce new meaning. Contributions do not need to exist in
the shared semantic catalog first. An optional availability record is either:

```json
{"scope": "portable"}
```

or:

```json
{"scope": "profiles", "profiles": ["internal-v2"]}
```

When omitted, semantic-catalog records default to portable availability and a
profile or extension contribution defaults to its target profile. Runtime
validation checks availability against loaded profiles and provenance scope.

The `internal-v2` profile demonstrates this mechanism in two independent ways.
Its Phase 1 binding maps the wide `magview_all_cohorts_PACS_v2_anon` clinical
table to shared and profile-owned clinical semantics, including an internal
putative pathology-specimen object whose reliability and identity remain
unresolved. It also records longitudinal patient identity, same-episode linked
accessions, accession-plus-finding-number identity, date-shift and event-time
meaning, supported procedure representation, categorical normalization,
invalid pathology-severity value `6`, and a technical cancer-registry
reference. Its `region_of_interest` object and
`clinical.image-region-of-interest` relationship remain semantic-only. Phase 1
establishes one required source image per ROI but leaves image metadata and
future cross-image ROI grouping outside the profile binding, while explicit
`not_cataloged` coverage leaves ROI tables, columns, identifiers, geometry,
coordinate systems, and physical linkage for Phase 2.

## Profile modules

A profile document has `profile_schema_version: 2`, one profile identity, a
requirement for semantic schema 8, semantic contributions, sources, contexts,
qualifications, vocabularies, and one physical `profile_binding`.

### Physical table inventory

Tables declare physical columns independently of mappings:

```json
{
  "id": "open-v2.binding.table.patients_anon",
  "table": "patients_anon",
  "grain": "one exported patient row",
  "columns": [
    {"name": "empi_anon", "physical_type": "int64", "nullable": true}
  ],
  "keys": [],
  "caveats": []
}
```

`grain` is optional descriptive text, not a closed global enum. Physical type
and schema nullability occur once on the table-owned column. Columns may remain
unmapped while their semantics are unresolved. Keys, object identity, and
relationship endpoints must reference declared columns.

### Feature mappings

A feature binding maps one physical occurrence to one concept:

```json
{
  "id": "open-v2.binding.feature.patient-id",
  "table": "patients_anon",
  "column": "empi_anon",
  "concept": "identity.patient_identifier",
  "status": "direct"
}
```

Status is `direct`, `derived`, `conditional`, `ambiguous`, or `unresolved`.
Mappings are identified by their authored IDs, not by `profile:table.column`,
so one column may have several mappings and one concept may map to many
columns. Downstream renamed columns simply map to the same stable concept.
Callers must inspect status and handle multiple applicable mappings rather than
assuming equivalence.

Optional `qualifiers` are a closed scalar-valued map. They preserve descriptive
metadata such as `{"slot": 1}` without reserving parameters for one pathology
concept. Optional occurrence interpretations retain value/null meaning,
evidence status, claims, and caveats. Vocabulary selection remains
mapping-specific.

### Object mappings and co-location

Object bindings name an object, table, relevant columns, evidence, and optional
instance identity. Three optional independent axes replace the former mixed
representation enum:

- `completeness`: `complete`, `partial`, or `unknown`;
- `authority`: `preferred`, `reference`, `alternative`, or `unspecified`; and
- `derivation`: `source`, `projected`, `derived`, or `unknown`.

Co-location is never authored as a role. It is computed when multiple object
bindings select the same table. Physical relationships may also have the same
source and target table; this records within-row navigation and is not a
table-graph cycle.

Relationship bindings and ordered binding paths remain descriptive physical
routes. They are not executable joins and do not promote matching tuples into
clinical attribution guarantees.

## Extension modules

An extension has `extension_schema_version: 2`, identity, semantic version,
lifecycle, one target profile, explicit extension dependencies, all-family
contributions, evidence records, optional lineage, and a `profile_binding` with
the same physical shapes used by profiles. Empty physical collections are
valid for semantic-only extensions.

There is no revision array and no `reinterprets_concept`, `replaces_binding`,
or `coexists_with` mechanism. Extensions add scoped records and mappings with
new stable IDs. Competing or conditional interpretations remain simultaneously
addressable and are surfaced as alternatives or ambiguity.

## Composition and queries

Loading retains origin, module, lifecycle, target profile, and availability
for every contribution. Duplicate IDs, missing dependencies, dependency
cycles, invalid scope, unresolved references, duplicate mapping IDs, and
incompatible physical endpoints are errors. Independent extension input order
does not change the effective view.

Portable queries need no profile. Profile-dependent operations require an
explicit profile when applicable contributions, qualifications, vocabularies,
or mappings differ. Python, CLI, MCP, and the curator use the same resolver.

The Python entry point is:

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

CLI and MCP startup accept repeatable `--profile-file` and `--extension-file`.
`--no-default-profiles` omits manifest-selected profiles. Startup failures
identify the document and JSON path without exposing file content.

## Footer verification

`scripts/validate_source_profile.py` compares a selected profile's complete
table and column inventory to direct-child Parquet footer schemas. It checks
file/table presence, exact column names, physical types, and schema
nullability. It reads no rows, values, statistics, counts, identifiers, dates,
or report text.

Footer agreement does not validate key uniqueness, referential coverage,
cardinality, clinical attribution, ROI geometry, outcome capture, or
availability. The verifier is intentionally exact rather than a partial
catalog-authoring scanner.

## Authoring from local source data

Footer verification is not the only permitted authoring evidence. In an
authorized environment, maintainers may perform minimal, question-specific
inspection of local source data to reconcile represented values, sentinels,
row grain, or physical relationships. This investigation remains outside the
runtime catalog and verifier.

Historical references—including the V1 Open Data dictionary and public EMBED
documentation—and the V2 Open Data legend must be checked against internal V2
rather than copied as profile truth. The authored result may contain reconciled
non-identifying controlled values and supported meanings, but never raw rows,
identifiers, report text, extracts, empirical counts, frequencies, or
distributions.

Represent a targeted source-data observation as a profile source with kind
`supporting_internal` and locator kind `logical_artifact`. Its version scope and
notes should identify the internal-V2 question it answered without recording a
local path, row, or source value.

## Authoring rule

Search existing stable IDs before adding meaning. Reuse shared semantics when
meaning is unchanged, but put legitimately profile-specific objects and
concepts in that profile's contributions with correct availability. Keep
physical columns in table inventories and semantic interpretation in mappings.
Record uncertainty explicitly; do not manufacture physical details from a
semantic scaffold.
