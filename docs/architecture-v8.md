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
putative specimen, pathology-observation, and pathology-diagnosis objects
independently. The patient identifier persists longitudinally within the
profile, linked accessions are co-occurring same-episode exams, and clinical
finding identity is accession plus finding number. Null and `B` finding sides
are bilateral and project to both unilateral side identities; finding number
`-9` is the synthetic contralateral negative finding. Within one patient, a
complete procedure-date, type, and biopsy-side tuple identifies one procedure.
Specimen-level presence, completeness, reliability, identity, and cardinality
remain unresolved. Profile-owned specimen, staging, biomarker,
nodal, registry-reference, and source-workflow semantics remain available only
to `internal-v2`.

The same profile adds a second, independent physical schema:
the internal V1c `metadata_all_cohorts_v1c` image-metadata table at one row per
extracted DICOM image instance. It binds the `image` object, the profile's
`region_of_interest` object, co-located patient, exam, and image-derived
breast-side projections, a cross-table accession route for the exam-to-image
relationship, and a same-table route for the image-to-ROI relationship. Each ROI
still has exactly one required source image, but the physical representation is a
serialized per-image collection, so no ROI row grain, ROI identifier, or
cross-image ROI grouping is asserted. Coordinates use DICOM pixel-array
`[y_min, x_min, y_max, x_max]` order and originate from radiologist clinical
annotations; model-inferred DBT depth is explicitly flagged. Source DICOM
modality, the source DICOM image-type attribute, the pipeline-derived
mammographic image-type classification, view position, and image laterality
stay separate mappings.
Because the clinical surface is internal V2 while the paired image metadata is
internal V1c, the profile records the version boundary explicitly: V1c covers
every EMBEDv1 exam and patient but is narrower than clinical V2, and an
unmatched later clinical exam means missing extraction coverage
rather than an exam without images. The accession remains the distinct exam
identifier in the shared cross-table namespace and each accession belongs to
exactly one patient; cross-patient associations are invalid data-quality
errors. The anonymized DICOM locator is the intended image-file reference and
its basename is the dataset-version-scoped anonymized SOP Instance UID;
observed absence likely reflects anonymization failure. Standard DICOM Burned
In Annotation
semantics distinguish `YES`, `NO`, and absence without treating the source
declaration as pixel-data verification.

## Physical schemas and mappings

A profile table owns its physical column inventory. Each column records its
name, physical type, and schema nullability once. Table grain is optional,
descriptive text rather than a closed global enum. Keys and physical
relationship endpoints resolve against this inventory. A physical column may
remain unmapped while its meaning is investigated.

The inventory shape does not require an embedded source schema. When an artifact
declares none, as with the internal V1c delimited-text image metadata, the
recorded physical types are assessed parse types from a deterministic reader and
every column is conservatively nullable; the table caveats state that basis so a
parse assessment is never mistaken for a source-declared schema. Relationship
endpoints still require exactly equal physical types, so parse assessment must
not narrow an integer column to an observed magnitude.

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

The internal MagView binding exercises this wide-table model directly:
one physical row can project several clinical objects, and repeated finding or
procedure associations do not collapse those objects into one row-grain
identity. Patient dates share one patient-specific shift; exam and procedure
occurrence dates are confirmed while pathology-report time remains provisional;
the same shift applies to every anonymized EMBED date across tables and dataset
versions. Historical code meanings remain applicable unless superseded, all
alphabetic codes may be trimmed and uppercased for comparison, and known
comma-delimited fields have unordered component codes. Pathology-severity
value `6`, or null severity with a populated descriptor, is a data-quality error
rather than a clinical category. Curated Open V2
aggregate columns that are absent internally remain unbound rather than being
recreated from semantic similarity.

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

The controlled evidence value `observed_source_values` is intentionally
release-neutral. Version and profile applicability come from the containing
record and its claim-level source provenance. This keeps internal V1c evidence
truthful without introducing a new controlled value for every source version.

## History

[Architecture v7](architecture-v7.md) and the
[profile-module migration](profile-module-migration.md) document the preceding
v7/v1/v1 ownership and typed-revision design. They are historical and do not
override this decision. [Architecture v6](architecture-v6.md) and
[architecture v5](architecture-v5.md) preserve earlier monolithic designs.
