# Catalog format

## Design

The catalog separates semantic knowledge from physical representation:

```text
concept ──< binding >── profile / table / column / grain
   │
   └──── optional vocabulary ── code → meaning

profile / table ──< key candidate
       │
       └──── relationship ── profile / table
```

This is intentionally a small registry rather than a generic knowledge graph.
It gives agents stable feature identities and useful filters without requiring
an ontology engine, database, generated documentation, or probabilistic search.

## Top-level objects

`schema_version`
: Integer format version. Readers reject unsupported versions.

`profiles`
: Stable identifiers for physical dataset variants. Concepts are shared across
  profiles; bindings select a profile.

`grains`, `feature_kinds`, and `domains`
: Controlled facets used by validation and filtering. Domains are
  multi-valued, so one concept can be both demographic and a social determinant
  of health, or both imaging and pathology-related.

`concepts`
: Object keyed by stable semantic IDs. Each concept contains a label,
  definition, feature kind, domains, search terms, caveats, and evidence. A
  coded concept may reference one vocabulary.

`bindings`
: Physical occurrences. A binding records profile, table, column, concept,
  grain, role, physical type, schema nullability, and optional semantic
  parameters. Phase 1 permits only a positive `slot` parameter for repeated
  pathology positions; the parameter object is closed so empirical summaries
  cannot be added under alternate names. Roles distinguish canonical
  occurrences, references, wide-table projections, and technical fields.

`vocabularies`
: Reusable code-to-meaning maps. Each vocabulary declares whether its code list
  is known to be closed and whether values are atomic, share a slot dictionary,
  or use an undocumented comma-composed representation.

`tables`
: Profile-specific table declarations. Each declaration fixes the table grain
  and records natural or technical key candidates with explicit uniqueness,
  completeness, evidence, and caveats. A candidate may be non-unique or
  unresolved; its presence is not a database-constraint claim.

`relationships`
: Profile-scoped, directional linkage claims. Source and target endpoints use
  ordered physical-column tuples. Relationship kind, source completeness,
  cardinality in both directions, evidence, caveats, and join hazards remain
  explicit and separate from semantic feature concepts.

The authoritative field constraints are in
[`catalog/catalog.schema.json`](../catalog/catalog.schema.json).

## Identity and deduplication

A concept ID identifies meaning, not a column occurrence. A raw column name can
therefore appear in several tables and still resolve to one concept.
`table.column` identifies a physical name. `profile:table.column` identifies
exactly one profile binding. An unqualified physical name is accepted across
profiles when every matching binding has the same concept; otherwise lookup
reports the ambiguity and lists qualified choices. Parameterized repeated slots
point to one concept and carry their slot in the binding.

Bindings at different grains may share a concept only when the definition
remains true at every bound grain. Finding-level presence and level-specific
aggregates use separate concepts because they are not interchangeable.

## Query behavior

Exact lookup resolves a concept ID, physical name, or profile-qualified
physical name. Code lookup accepts any of those forms or a vocabulary ID and
matches code strings exactly, including case.

Table lookup accepts an explicit profile and table name and returns the table
declaration plus its incoming and outgoing relationships. Relationship lookup
accepts a stable relationship ID. Relationship search is independently
filterable by profile, either endpoint table, directional source or target
table, and relationship kind; results are sorted deterministically by ID.
These APIs do not alter existing feature lookup or search result shapes.

Search scans the in-memory catalog linearly. It considers concept IDs, physical
names, labels, definitions, search terms, facets, caveats, and vocabulary
meanings. A small prompt-word stoplist plus weighted token overlap makes short
natural descriptions useful without adding a fuzzy-search or embedding
dependency. It applies a small plural normalization and indexes
punctuation-collapsed identifier aliases, so inputs such as `breast masses` and
`ACCAnon` work without a general fuzzy matcher. Results are sorted
deterministically and deduplicated by concept; their `bindings` array shows the
physical occurrences that satisfied the query and filters.

Filters are available for profile, table, grain, domain, and feature kind. The
text query may be omitted when at least one filter is present, which supports
requests such as all pathology concepts or all demographic features at patient
grain.

## Evidence and caveats

Evidence labels describe why a semantic claim is present; they are not
confidence scores. Definitions should say only what the evidence supports.
Unknown units, code completeness, derivations, temporal availability, delimiter
rules, and missing-value semantics belong in caveats.

The catalog records no empirical distribution. See the count-free policy in
[`project-scope.md`](project-scope.md).

Relationship cardinality is qualitative and directional. It never records
release row totals, match rates, orphan counts, or duplicate counts. Column
nullability, source-endpoint completeness, and referential coverage are
different claims and must not be substituted for one another.

## Relationship validation

Every table declaration and relationship endpoint must resolve to bindings in
the same profile. Ordered endpoint tuples must have equal arity and compatible
physical types. A relationship claiming at most one target must point to a
candidate key documented as unique. Only hierarchy edges must be acyclic;
reference and projection edges may legitimately form cycles.

The default source-profile verifier remains footer-only. It verifies the
physical table and column surface through bindings but does not scan clinical
data to prove uniqueness, coverage, or cardinality.

## Adding a profile

To support another EMBED variant:

1. Add a stable profile ID.
2. Reuse existing concepts and vocabularies wherever meanings are unchanged.
3. Add bindings for the profile's physical columns.
4. Add a new concept only for a genuinely new or changed meaning.
5. Validate cross-references and compare the profile bindings with the source
   schema.
6. Add synthetic tests and update profile documentation.

Profile-specific statistics must remain outside the feature catalog. If a
future use case needs empirical profiling, it should be a separate,
explicitly-scoped artifact with its own lifecycle.

The footer-only `scripts/validate_source_profile.py` verifier derives the
selected profile's expected table and column manifest from bindings. It does
not contain a hard-coded release occurrence total.

## Schema evolution

Compatible content additions keep the current schema version. A change that
alters required fields, field meaning, identifier resolution, or query
semantics requires a version decision and migration note. Consumers must fail
clearly on an unsupported schema version rather than silently interpreting it
as the current format.

Schema version 2 adds required `tables` and `relationships` collections.
Version-1 consumers must upgrade before loading a version-2 catalog. Existing
feature lookup, search, and code-lookup result shapes remain unchanged;
linkage queries use separate APIs.
