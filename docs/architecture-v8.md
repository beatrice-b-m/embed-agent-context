# Architecture v8: scoped contributions and independent physical schemas

## Decision

Schema v8 keeps deterministic catalog-set composition while removing the
ontology and physical-binding restrictions that made schema v7 difficult to
extend. The current version axes are software `0.10.0`, semantic schema `8`,
profile-module schema `2`, extension-module schema `2`, catalog-set manifest
schema `1`, registered public profile `open-v2`, optional MCP SDK `2.0.0`, and
lockstep curator companion `0.10.0`.

The bundled manifest still selects the shared semantic catalog and `open-v2`.
`internal-v2` is an explicit, non-default working profile. Extensions remain
explicitly selected. Every module is descriptive, count-free, and
non-executable.

## Semantic contributions and availability

The semantic catalog supplies shared meaning. Profiles and extensions may also
contribute every semantic family:

- clinical objects and concepts;
- semantic relationships and temporal semantics;
- aggregations and guardrails; and
- coverage statements.

This is an availability boundary, not an ontology permission hierarchy. A
record may declare `availability` as `portable` or name one or more profiles.
When omitted, the module supplies the default: semantic-catalog records are
portable and profile or extension contributions apply to their target profile.
Composition rejects duplicate stable IDs and invalid scope, but a
profile-specific concept need not first be promoted into the shared catalog.

Sources, contexts, vocabularies, qualifications, and extension lineage remain
module-owned records. Origins identify the document, module, lifecycle, target
profile, and availability used for a result. Multiple applicable meanings are
reported as ambiguity; modules do not silently overwrite one another.

The shared catalog now includes the `image` object and the exam-to-image
relationship because images occur across EMBED representations. The
non-default `internal-v2` profile now inventories the wide
`magview_all_cohorts_PACS_v2_anon` clinical table and binds its co-located
patient, partial-episode, exam, side, finding, interpretation, procedure,
specimen, pathology-observation, and pathology-diagnosis objects independently.
Profile-owned specimen, staging, biomarker, nodal, and source-workflow
semantics remain available only to `internal-v2`. The profile's
`region_of_interest` object and image-to-ROI relationship remain semantic-only;
image metadata, DICOM attributes, image identity and enrichments, and all
image/ROI physical bindings are deferred to Phase 2.

## Physical schemas and mappings

A profile table owns its physical column inventory. Each column records its
name, physical type, and schema nullability once. Table grain is optional,
descriptive text rather than a closed global enum. Keys and physical
relationship endpoints resolve against this inventory. A physical column may
remain unmapped while its meaning is investigated.

Feature bindings are semantic mappings, not column declarations. Each mapping
has a stable ID, table, column, concept, and status:

- `direct`;
- `derived`;
- `conditional`;
- `ambiguous`; or
- `unresolved`.

Mappings are many-to-many. Several columns may express one concept, and one
physical occurrence may have several explicitly identified interpretations.
Optional `qualifiers` preserve scalar descriptive metadata, such as a repeated
slot number, without hard-coding a domain concept into infrastructure.
Occurrence interpretations continue to qualify value or null meaning.

Object bindings no longer carry a mixed `representation` enum. Optional,
independent axes describe `completeness`, `authority`, and `derivation`;
`instance_identity` remains separate. Co-location is inferred whenever several
objects bind to the same table. Same-table physical relationships are valid
descriptive navigation and do not create a table-graph cycle.

The internal Phase 1 MagView binding exercises this wide-table model directly:
one physical row can project several clinical objects, and repeated finding or
procedure associations do not collapse those objects into one row-grain
identity. Curated Open V2 aggregate columns that are absent internally remain
unbound rather than being recreated from semantic similarity.

## Extensions and composition

Extension schema v2 uses the same `contributions` and `profile_binding` shapes
as profiles. Typed concept and binding revisions are removed. An extension
expresses a competing, derived, conditional, or preferred interpretation by
adding a scoped contribution or mapping with its own stable ID. Original
records remain addressable because composition is additive.

Extension dependencies are still topologically resolved. Composition remains
independent of file order and rejects missing dependencies, cycles, target
profile mismatches, unresolved references, duplicate IDs, and invalid
availability.

## Loading and compatibility

Schema v8 is an intentional breaking contract. The runtime accepts semantic
schema `8`, profile schema `2`, and extension schema `2` only. Schema-v6
monoliths and schema-v7/v1/v1 modules are not compatibility inputs. Passing an
old or unknown document is a fatal startup validation error with file and JSON
path context; fields are never ignored or translated silently.

Python, CLI, MCP, and the curator compose the same immutable effective view.
Profile-dependent queries require profile selection when applicable
contributions, vocabularies, qualifications, or mappings differ.

## Footer verification

The source-profile verifier reads only Parquet footer schemas. It compares the
selected profile's complete table-owned column inventory with direct-child
Parquet files, including names, physical types, and schema nullability. It does
not read rows, counts, statistics, identifiers, dates, report text, or values,
and it does not establish key uniqueness, referential coverage, cardinality,
clinical attribution, outcome capture, or availability. Missing local
artifacts remain an explicit operational prerequisite, not a catalog error.

## Authoring evidence from source data

The runtime and clone-safe validation remain independent of EMBED data. During
authorized profile authoring, however, a maintainer may inspect the minimum
source rows or values needed to resolve a specific question about represented
codes, sentinels, grain, or relationships. This is a human/agent evidence
workflow, not a new runtime interface and not an expansion of the footer
verifier.

Direct internal V2 observations are reconciled with maintainer knowledge, the
V2 Open Data legend, supporting internal material, the non-comprehensive V1
Open Data dictionary, and public EMBED documentation. Historical references do
not override current source evidence, while observed occurrence alone does not
prove clinical meaning or exhaustiveness. Only the reconciled, non-identifying,
count-free conclusion enters the catalog.

## History

[Architecture v7](architecture-v7.md) and the
[profile-module migration](profile-module-migration.md) document the preceding
v7/v1/v1 ownership and typed-revision design. They are historical and do not
override this decision. [Architecture v6](architecture-v6.md) and
[architecture v5](architecture-v5.md) preserve earlier monolithic designs.
