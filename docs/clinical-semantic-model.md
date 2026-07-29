# EMBED clinical-semantic model

## How to read the model

Begin with a clinical object or question. Follow semantic relationships to
adjacent objects, then inspect features, time meanings, aggregations,
guardrails, and coverage. Consult a profile binding only after selecting the
portable concepts needed for the analysis.

A semantic relationship describes clinical meaning and attribution. A profile
relationship binding describes how one release can approximate that
relationship with tables and columns. Neither is executable join logic.

## Breast-imaging objects

The initial graph distinguishes:

1. a patient;
2. a breast-imaging episode;
3. an imaging exam or accession;
4. breast side and imaging findings;
5. the finding-level imaging interpretation, including separate assessment and
   recommendation features;
6. a linked biopsy, surgery, or other procedure;
7. procedure-associated pathology observations;
8. the represented pathology diagnosis state;
9. radiology report versions; and
10. clinical risk-assessment rows.

An object does not imply a dedicated table. In open-v2, procedure, pathology
observation, diagnosis, and report-date fields can be co-located on a
pathology-finding row without acquiring a proven one-to-one clinical identity.
Likewise, assessment and recommendation are co-located on an imaging-finding
row without an independent interpretation identifier or timestamp.

## Pathology outcome states

`pathology.severity` uses this closed represented code set:

| Code | Represented diagnosis state |
|---|---|
| `0` | Invasive breast cancer |
| `1` | In-situ breast cancer |
| `2` | High-risk lesion |
| `3` | Borderline lesion |
| `4` | Benign finding |
| `5` | Non-breast cancer |

Lower values are more severe. The six codes are not automatically two
analysis classes, and the catalog does not recommend combining them.
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

No time is labeled as a universal diagnosis date. An analysis must choose an
anchor according to the question and must exclude information unavailable at
that anchor when leakage matters.

## Aggregation

The represented pathology severity is derived from the most severe attached
pathology descriptor group. Side- and exam-level severity aggregates use the
minimum numeric value because the scale is inverse. Open-v2 support for those
two supplied rollups is recorded through profile-specific coverage and result
feature bindings; `provided` does not imply that every future profile contains
the same fields.

No supplied finding-level severity is established because attribution is
optional and many-to-many. No canonical patient-level outcome rollup is
provided. Patient-level questions must address multiple sides, exams,
procedures, diagnoses, changing states, and time explicitly.

## Capture and uncertainty

The catalog does not establish complete breast-cancer outcome capture,
outside-system follow-up, a censoring mechanism, an interval-cancer rule, or a
minimum observation window. Absence of a represented diagnosis is therefore
not proof of disease absence.

Restricting observations to attached pathology also conditions on a
represented tissue-sampling procedure. Because not every patient, exam, side,
or finding proceeds to sampling, pathology-observed groups may differ
systematically from unsampled groups. The catalog exposes this selection
mechanism but does not choose an inclusion, exclusion, weighting, or causal
analysis policy.

Coverage records distinguish a documented unsupported or unresolved surface
from a failed search. A `no_catalog_coverage` diagnostic means only that the
portable catalog has no indexed record for the query; it is not evidence that
the clinical concept is absent from EMBED or clinical care.
