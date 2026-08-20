# EMBED clinical-semantic model

## How to read the model

Begin with a clinical object or question. Follow semantic relationships to
adjacent objects, then inspect features, time meanings, aggregations,
guardrails, and coverage. Consult a profile binding only after selecting the
shared or profile-available concepts needed for the analysis.

A semantic relationship describes clinical meaning and attribution. A profile
relationship binding describes how one release can approximate that
relationship with tables and columns. Neither is executable join logic.
When a semantic relationship needs several physical hops, an ordered binding
path retains that composition and every step's hazards.

`open-v2` below is the stable profile ID for the registered open EMBED V2
physical layout; it is not catalog schema version 2. See the README
[glossary and version axes](../README.md#terms-and-version-axes) for the core
terminology.

## Breast-imaging objects

The initial graph distinguishes:

1. a patient;
2. a breast-imaging episode;
3. an imaging exam or accession;
4. breast side, acquired images, and imaging findings;
5. the finding-level imaging interpretation, including separate assessment and
   recommendation features;
6. a linked biopsy, surgery, or other procedure;
7. procedure-associated pathology observations;
8. the represented pathology diagnosis state;
9. radiology report versions; and
10. clinical risk-assessment rows.

The shared graph includes acquired images and their relationship to imaging
exams. The non-default internal-v2 profile now binds the wide MagView
clinical table to separate patient, partial-episode, exam, breast-side, finding,
interpretation, procedure, putative specimen, pathology-observation, and
pathology-diagnosis objects. Procedure-level information is supported, but the
presence, completeness, reliability, identity, and cardinality of specimen-level
information remain unresolved; current internal operations should not depend on
that specimen surface. Profile-owned staging, biomarker, nodal, and
source-workflow semantics do not become portable merely because they share the
wide table.

Internal-v2 also binds a second physical table: the internal V1c image-metadata
extraction, at one row per extracted DICOM image instance. It carries the image
object together with co-located patient, exam, and image-derived breast-side
projections, and it distinguishes source DICOM modality, the source DICOM
image-type attribute, the pipeline-derived mammographic image-type
classification, view position, and image laterality as separate features.
Because that extraction inventories no DICOM instance identifier, the profile
declares no image instance identity; the anonymized file locator is a technical,
incomplete, release-local row locator. It is nevertheless intended to be
defined for every extracted image: a missing value means the image file is
unavailable and is a data-quality defect. `acc_anon` remains the identifier of
one distinct exam across EMBED and shares its namespace across the clinical and
metadata tables; each accession belongs to exactly one patient, and a
cross-patient association is an invalid data-quality error rather than a
different exam identity.

DICOM Burned In Annotation retains its standard meaning: it declares whether
the image contains sufficient burned-in annotation to identify the patient and
the date the image was acquired. `YES` and `NO` are source declarations, an
absent attribute leaves that condition unknown, and none is a pixel-data
verification.

Each ROI still originates on exactly one required source image, and an ROI is
not equated with a clinical finding. Physically, an image row carries a
region-of-interest count with positionally aligned coordinate, frame-index, and
depth-derivation collections, so the table is not one row per ROI, no ROI
identifier exists, and a region is addressable only by collection position.
Coordinate axis order and reference frame, per-region provenance, and grouping of
corresponding ROIs across simultaneous FFDM, DBT, and synthetic 2D acquisitions
remain unresolved or future work.

The clinical surface here is internal V2 while the paired image metadata is
internal V1c. That boundary is deliberate and temporary: V1c covers a shorter
period and a smaller patient set, so a clinical exam without a matching image
row is outside current extraction coverage and is never an exam without images.
An inner accession join discards those exams silently. The image surface is
mammography-centred, full-period extraction is in progress, and no future
ultrasound or MRI columns are modelled.

An object does not imply a dedicated table. In open-v2, procedure, pathology
observation, diagnosis, and report-date fields can be co-located on a
pathology-finding row without acquiring a proven one-to-one clinical identity.
Likewise, assessment and recommendation are co-located on an imaging-finding
row without an independent interpretation identifier or timestamp.
Co-location is derived from multiple object mappings selecting the same table;
it is not an authored object role and can change in another representation.

Open-v2 finding number identifies a clinical finding only within its accession
after the documented reserved synthetic value is excluded. It does not persist
across accessions, episodes, or modalities, and multiple physical rows may
represent one finding. This instance identity is separate from row keys and
technical export indices.

Internal-v2 uses the same accession-plus-finding-number clinical identity;
side is a finding attribute rather than an identity component. Physical rows
may repeat that identity for multiple procedure or pathology attachments.
Every exam-level attribute is invariant within an accession, and conflicting
side or exam-level attributes across rows are data-quality errors rather than
new clinical identities. Finding number `-9` is the synthetic contralateral
BI-RADS 1/`N` finding added when a bilateral exam has only a unilateral
non-negative finding row. `empi_anon` persists across the
patient's internal V2 records and supports longitudinal traversal. Linked
accessions are explicitly linked co-occurring exams in one imaging episode,
such as diagnostic mammography and ultrasound, and never represent prior or
follow-up exams.

Laterality meaning is occurrence-specific. A null finding-side occurrence is
bilateral and equivalent to `B`; both project to the left and right unilateral
breast-side identities. A null biopsy or procedure side means unknown rather
than bilateral. Side-level records and wide projections retain their own
reviewed or unresolved interpretations.

## Pathology outcome states

The governed portable and Open V2 `pathology.severity` vocabulary uses this
closed represented code set:

| Code | Represented diagnosis state |
|---|---|
| `0` | Invasive breast cancer |
| `1` | In-situ breast cancer |
| `2` | High-risk lesion |
| `3` | Borderline lesion |
| `4` | Benign finding |
| `5` | Non-breast cancer |

Lower values are more severe. The six codes are not automatically two
analysis classes, and the catalog does not recommend combining them. In
internal-v2, code `5` is also non-breast cancer. Any represented code `6` is an
an invalid source value with no expected meaning outside the governed clinical scale; it must
be excluded or explicitly flagged rather than ordered or assigned a diagnosis
group.

In particular, `5` represents non-breast cancer; it is not benign pathology,
a healthy state, or absence of malignancy.

Null severity is the separately modeled `unattached_pathology` state. It means
that no pathology is attached through the represented field. It is not code
`4`, a negative tissue diagnosis, proof that no disease exists, or proof of
adequate follow-up.

Some valid source-system pathology descriptor codes have unresolved meanings.
Their presence must be retained without guessing a mapping.

## Attribution

Finding-to-procedure and finding-to-pathology attribution can be optional and
many-to-many. The open-v2 accession/side/finding tuple can contain incomplete
components or duplicate matches. Moving pathology onto finding rows therefore
requires an explicit attribution and row-multiplication policy.

Pathology can also be related to patient, exam, and breast side, but those
paths have different physical evidence and limitations. A table row that
contains all of these fields is not proof of a unique clinical event shared by
all of them.

Longitudinal candidate search begins at the patient and traverses the patient's
exam timeline even when the final output grain is exam side or finding. The
accession on a pathology observation belongs to its candidate
pathology-associated exam; requiring it to equal the index exam accession would
collapse longitudinal search into same-exam attachment.

## Time

The catalog distinguishes:

- imaging exam event time;
- linked procedure event time;
- specimen collection time;
- pathology report documentation time; and
- downstream information availability.

Open-v2 binds exam, procedure, and pathology-report date concepts. It has no
supported specimen-collection date binding and no universal availability
timestamp. All represented dates use a consistent per-patient anonymization
shift, preserving within-patient ordering and date differences while
obscuring absolute calendar values.

Internal-v2 applies one consistent patient-specific shift to every anonymized
date value across EMBED tables and dataset versions, preserving within-patient
ordering and differences.
`studydate_anon` is exam occurrence time, `procdate_anon` is procedure
occurrence time, and `age_at_study_anon` is derived from the shifted birth and
study dates with ages 90 years or older top-coded to 89. `pdate_anon` is
believed to be pathology-report documentation time but remains provisional;
`dt_final_anon` and `dt_rel_anon` remain unmapped.

No time is labeled as a universal diagnosis date. An analysis must choose an
anchor according to the question and must exclude information unavailable at
that anchor when leakage matters. Procedure, report, and other date semantics
must not be coalesced or fallback-substituted when the selected endpoint is
missing. A separately named endpoint or sensitivity analysis may use another
time without pretending it has the same meaning.

## Aggregation

The represented pathology severity is derived from the most severe attached
pathology descriptor group. Side- and exam-level severity aggregates use the
minimum numeric value because the scale is inverse. Open-v2 support for those
two supplied rollups is recorded through profile-specific coverage and result
feature bindings; `provided` does not imply that every future profile contains
the same fields.

Internal-v2 maps its represented finding-associated pathology severity
as the most severe group selected by the extraction's fixed mapping over the
ten pathology descriptor slots, without binding Open V2's curated side- and exam-level aggregate columns, and
it has no supplied patient-level severity aggregate. A downstream grouping
that seeks the most severe represented value must declare its linkage and
grain, treat null severity with any populated descriptor and code `6` as
data-quality errors, and use the
minimum over the governed comparable values. It is analyst-defined, not a
supplied internal feature or universal default.

A new finding-level reduction across attributed pathology occurrences requires
an analyst-declared policy because attribution is optional and many-to-many. No
canonical patient-level outcome rollup is provided. Patient-level questions
must address multiple sides, exams, procedures, diagnoses, changing states,
and time explicitly.

## Capture and uncertainty

The catalog does not establish complete breast-cancer outcome capture,
outside-system follow-up, a censoring mechanism, an interval-cancer rule, or a
minimum observation window. Absence of a represented diagnosis is therefore
not proof of disease absence.

Restricting observations to attached pathology also conditions on a
represented tissue-sampling procedure. Because not every patient, exam, side,
or finding proceeds to sampling, pathology-observed groups may differ
systematically from unsampled groups. The catalog exposes this selection
mechanism but does not declare the resulting estimand invalid and does not
choose an inclusion, exclusion, weighting, or causal analysis policy. The
conditioning and generalizability boundary must be named.

A binary endpoint can mean “no represented event under the declared extraction
policy.” It cannot, without additional evidence, be strengthened to “never
biopsied,” “cancer-free,” or complete negative follow-up. Same-day boundaries,
episode definitions, tie-breaking, follow-up opportunity, and observation
proxies are analyst choices that must remain explicit.

Open-v2 risk outputs can support association or ranking questions while their
scale, horizon, model version, exceptional values, or probability semantics
remain unresolved. Probability calibration, Brier scores, and similar
probability-based interpretations require those semantics to be validated
first.

Coverage records distinguish a documented unsupported or unresolved surface
from a failed search. A `no_catalog_coverage` diagnostic means only that the
portable catalog has no indexed record for the query; it is not evidence that
the clinical concept is absent from EMBED or clinical care.
