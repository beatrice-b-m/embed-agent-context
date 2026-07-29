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

context ──< claim >── source
   │
   ├──── concept
   ├──── profile / table
   └──── relationship
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

`grains`, `feature_kinds`, `domains`, `context_kinds`, `context_scopes`,
`source_kinds`, `source_locator_kinds`, and `claim_statuses`
: Controlled facets used by validation and filtering. Domains are
  multi-valued, so one concept can be both demographic and a social determinant
  of health, or both imaging and pathology-related. The context facets keep
  clinical background, non-versioned EMBED documentation, and claims about one
  physical profile distinguishable.

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

`sources`
: A registry of evidence locators keyed by stable ID. Each source records its
  kind, context scope, physical profiles when applicable, portable locator,
  version boundary, and notes. An empty profile list means that the source
  makes no claim about a physical catalog profile; it does not mean that the
  source applies to every profile.

`contexts`
: Sourced clinical and procedural context keyed by stable ID. A context has one
  homogeneous scope, controlled kind and domains, navigation-only summary,
  related catalog entities, individually reviewable claims, and caveats.
  Clinical workflows additionally contain ordered stages backed by claim IDs.

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

Context lookup accepts a stable context ID and returns the complete context
plus a deduplicated map of every cited source. Context search is independently
filterable by kind, scope, profile, domain, related concept, related table,
related relationship, claim status, and source. Text search covers context
navigation fields, claim text and caveats, and source titles, but not raw source
locators. A profile filter matches only contexts that explicitly declare that
profile; profile-independent context is not silently treated as universal.
Search results contain only the claims that matched claim-level filters or
text, along with their source details. Workflow stages are trimmed to those
matching claims so returned references remain internally resolvable. A context
matched only through navigation fields such as its title, domain, or search
terms can therefore have an empty `matching_claims` array and no returned
sources.

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

## Clinical context and provenance

Context records explain how existing feature and relationship definitions fit
into clinical or documentation processes. They do not execute joins, construct
cohorts, exclude rows, derive labels, or replace a versioned data toolkit.
Substantive assertions belong in `claims`; a context `summary` is only a
navigation aid.

Every claim has a stable local ID, a review status, one or more source IDs, and
its own caveats. A claim can therefore be addressed as
`context-id.claim-id` without treating the whole context as uniformly
authoritative. Status has these meanings:

- `verified` — directly supported at the declared scope by applicable,
  authoritative evidence;
- `reconciled` — competing or differently scoped evidence has been reviewed
  and the qualified statement records the result;
- `unverified` — useful source material has not passed the applicable review;
- `unresolved` — the available evidence does not establish the requested
  meaning or policy; and
- `contradicted` — retained provenance for a claim that conflicts with other
  evidence and must not be presented as current guidance.

Contexts are scope-homogeneous. `general_clinical` explains clinical background,
`embed_general` describes non-profile-specific EMBED material, and
`profile_specific` identifies one or more physical profiles. General and
non-versioned EMBED contexts cannot reference physical tables or
relationships. A profile-specific verified claim must cite an applicable
maintainer-confirmed, release-schema, or release-legend source; public or
internal background alone cannot promote a claim to verified V2 behavior.

Source locators are typed as stable HTTPS URLs, repository-relative paths, or
logical artifact names. Absolute workstation paths and parent traversal are
rejected. Release schema and legend sources must identify their physical
profiles. Contradicted claims require at least two sources so the conflict is
traceable.

Every context must connect to at least one existing concept, table, or
relationship. Profile-specific references must resolve within the declared
profile, including concept bindings. Ordered `workflow_steps` are required for
clinical workflows and must place every claim; non-workflow contexts must keep
that array empty. This supports branching caveats without turning free-form
Markdown order into an implicit API.

## Relationship validation

Every table declaration and relationship endpoint must resolve to bindings in
the same profile. Ordered endpoint tuples must have equal arity and compatible
physical types. Different key IDs for the same ordered column tuple must not
make conflicting kind, uniqueness, or completeness claims. When a relationship
source matches a documented key, `required` source completeness cannot
contradict an incomplete key and `optional` source completeness cannot
contradict a complete key.

Key and relationship IDs and profile references use the stable lowercase
identifier grammar and cannot contain trailing line terminators. Phase 2
caveat and join-hazard entries must contain at least one non-whitespace
character.

A relationship claiming at least one target per source must declare the source
endpoint `required`. A relationship claiming at most one target must point to a
candidate key documented as unique; the reciprocal at-most-one-source claim
requires a unique source key. Only hierarchy edges must be acyclic; reference
and projection edges may legitimately form cycles.

The default source-profile verifier remains footer-only. It verifies the
physical table and column surface through bindings but does not scan clinical
data to prove uniqueness, coverage, or cardinality.

## Adding a profile

To support another EMBED variant:

1. Add a stable profile ID.
2. Reuse existing concepts and vocabularies wherever meanings are unchanged.
3. Add bindings for the profile's physical columns.
4. Add a new concept only for a genuinely new or changed meaning.
5. Add one `tables` declaration for every bound physical table. Record its
   grain and each assessed natural or technical key candidate, including
   explicit uniqueness, completeness, evidence, and caveats when a tuple is
   non-unique or unresolved.
6. Add `relationships` for the profile's intended joins. Record ordered source
   and target columns, source completeness, cardinality in both directions,
   evidence, caveats, and join hazards such as dangling references,
   row multiplication, nullable components, or temporal leakage.
7. Validate all cross-references and compare the profile bindings with the
   source schema. Substantiate key and linkage claims separately because the
   footer-only source verifier cannot prove them.
8. Add or update profile-specific contexts only when their claims have
   applicable sources. Do not copy general or older-release behavior into the
   new profile, and preserve unresolved workflow policy as unresolved.
9. Add focused synthetic tests plus checked-in profile integration assertions
   for required table declarations, key caveats, and the expected relationship
   inventory, then update profile documentation.

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
as the current format. Readers inspect `schema_version` before applying
version-specific required-field and extension-field rules, so both legacy and
future documents receive an explicit unsupported-version error.

Schema version 2 added required `tables` and `relationships` collections.
Schema version 3 adds the controlled context facets plus required `sources` and
`contexts` collections. It also introduces claim-level review state, typed
source locators, profile-aware evidence validation, and ordered workflow
stages. Version-2 consumers must upgrade before loading a version-3 catalog.
Existing feature, code, table, and relationship result shapes remain
unchanged; clinical context uses a separate model and query surface.
