# Feature-context investigation results

## Purpose and access record

This document records the evidence-gathering operations used to build the
feature-level context bundle. It contains aggregate findings only. It must not
contain copied clinical rows, identifiers, anonymized dates, or report text.

The access rules and completion criteria are defined in
[feature-context-investigation-plan.md](feature-context-investigation-plan.md).
All commands run through the locked project-local `uv` environment with
PyArrow 20.0.0.

## Structural and legend gates

### M001 — structural Parquet inventory

- **Question:** What physical feature surface is present?
- **Sources:** all eight files under `reference_files/clinical_tables/`.
- **Access:** Parquet footers only: schema names/types, row counts, row-group
  counts, producer metadata, and null counts where later needed. No data pages
  and no footer min/max values.
- **Aggregate result:** 243 table-column occurrences representing 125 unique
  column names. Counts by table are recorded in the investigation plan. Every
  table has one row group and an all-optional flat schema written by
  `parquet-cpp-arrow` 20.0.0.

### L001 — bounded legend/schema crosswalk

- **Question:** How much of the V2 physical feature surface is described by the
  released legend?
- **Sources:** the four columns of
  `reference_files/EMBEDv2-open-data-clinical-legend.csv` plus Parquet schema
  names.
- **Why metadata was insufficient:** Parquet schemas contain no feature
  descriptions or code meanings.
- **Access:** all 1,345 legend rows, decoded with `utf-8-sig`; source strings
  retained, with surrounding whitespace trimmed only for a derived comparison.
  No clinical table data pages.
- **Aggregate result:** 138 distinct legend headers after trimming. Fifty-seven
  header rows, 526 code cells, and 624 meaning cells contain surrounding
  whitespace. Sixty legend rows have blank code cells. The schemas have 125
  unique column names; 64 lack an exact trimmed legend header. Eleven of those
  have a case-only candidate. The remaining gaps include anonymized
  identifiers/dates, risk outputs, aggregate-level suffixes, pathology
  `path1`–`path10`, `combined_anon` export fields, report sequence/text, and the
  serialized index column. Of all 1,345 legend rows, 731 fall under the 78
  accepted exact/case/alias/shared headers and 614 fall under 60 headers
  orphaned from the released schemas.
- **Interpretation:** The legend is a large, partly legacy or broader data
  dictionary, not a complete one-to-one V2 schema contract. Header aliases and
  base-to-aggregate mappings require explicit evidence labels.

## Registered data-page probes

The following projected, aggregate-only probes are registered before execution.
No other data-page read is permitted during this investigation.

### Patient, exam, side, and risk

#### Q001 — patient categorical representation

- **Question:** What bounded V2 domains and null/blank states occur in the
  patient demographic fields that the legend does not fully define?
- **Table/columns:** `patients_anon`: `GENDER_DESC`, `race`, `ethnicity`,
  `patient_language`, `cohort_num`.
- **Why schema/legend is insufficient:** schema gives only physical types; the
  legend omits gender and gives no codes for several fields.
- **Operation:** projected per-column null, distinct, blank, and value-count
  aggregates. Values may be reported only as category labels with counts.

#### Q002 — patient grain

- **Question:** Is `empi_anon` a complete unique patient key, and is the
  serialized index a feature?
- **Table/columns:** `patients_anon`: `empi_anon`, `__index_level_0__`.
- **Why schema/legend is insufficient:** neither uniqueness nor index semantics
  are declared.
- **Operation:** null count, distinct count, duplicate-row count, and comparison
  of index position to row position; never output identifier values.

#### Q003 — exam descriptors and sentinels

- **Question:** What V2 domains occur in the exam descriptors and flags, and
  what are the scale/sentinel behaviors of age fields?
- **Table/columns:** `exam_level_anon`: `desc`, `modality_desc`, `mg_exam_type`,
  `tissueden`, `ASHKENAZI`, `age_at_study_anon`, `menopauseage_anon`,
  `pregnancyage_anon`, `menarcheage_anon`, `proc_flag`, `biopsy_flag`,
  `extract_flag`, `vtype`, `version`.
- **Why schema/legend is insufficient:** several fields or codes are absent;
  numeric age units and sentinel states are unstated.
- **Operation:** for `desc`, distinct/null/blank counts only; bounded domains
  for categorical fields; null counts, safe numeric range, and frequencies of
  nonpositive age values for age fields. No exam descriptions are output.

#### Q004 — exam aggregate flags

- **Question:** What bounded domains and missing states occur in the five
  exam-level aggregate fields?
- **Table/columns:** `exam_level_anon`: `path_severity_exam_level`,
  `mass_exam_level`, `asymmetry_exam_level`,
  `arch_distortion_exam_level`, `calc_exam_level`.
- **Why schema/legend is insufficient:** the suffixed fields are absent from the
  legend and base-field equivalence is not established.
- **Operation:** projected null, distinct, and value-count aggregates.

#### Q005 — side grain and aggregate flags

- **Question:** Is side level unique on accession and side, and what bounded
  domains occur in its totals and five aggregate fields?
- **Table/columns:** `side_level_anon`: all nine columns.
- **Why schema/legend is insufficient:** no key is declared and totals/suffixed
  aggregate fields are absent from the legend.
- **Operation:** null/distinct/duplicate counts for `(acc_anon, side)`; bounded
  value counts for `side`, totals, and aggregate fields. Never output accession
  values.

#### Q006 — risk grain and output scales

- **Question:** What is the risk-table record grain, and are the 12 NCI/IBIS
  outputs fractions, percentages, sentinels, or mixed representations?
- **Table/columns:** all 16 `risk_anon` columns.
- **Why schema/legend is insufficient:** the legend has no risk definitions or
  code/scale information.
- **Operation:** null/distinct/duplicate counts for accession key candidates;
  for each risk output, null count, finite range, quantiles, and counts below
  zero, within `[0,1]`, above one, and non-finite. Never output identifiers or
  dates.

### Imaging findings

#### Q007 — imaging coded domains

- **Question:** Do observed bounded codes agree with the legend for imaging
  flags, assessment/recommendation, mammography, ultrasound, and MRI fields?
- **Table/columns:** `imaging_findings_anon`: every non-identifier,
  non-free-text categorical column.
- **Why schema/legend is insufficient:** legend lists may be legacy,
  illustrative, compositional, or case-mismatched; missing states are unclear.
- **Operation:** projected null, distinct, blank, and value-count aggregates,
  grouped by modality. Do not output `acc_anon` or
  `linkedaccession_anon`.

#### Q008 — imaging numeric representation

- **Question:** What unit/sentinel evidence is present for finding number,
  size, distance, and MRI size?
- **Table/columns:** `imaging_findings_anon`: `numfind`, `size`, `distance`,
  `msize`.
- **Why schema/legend is insufficient:** units are missing for `numfind` and
  `msize`, and numeric sentinels are not stated.
- **Operation:** null count, finite range, selected quantiles, and frequencies
  of nonpositive values.

#### Q009 — imaging grain and linked-accession resolution

- **Question:** Is `(acc_anon, side, numfind)` a complete unique key, and do
  non-null linked accessions resolve to the exam table?
- **Table/columns:** `imaging_findings_anon`: `acc_anon`,
  `linkedaccession_anon`, `side`, `numfind`; `exam_level_anon`: `acc_anon`.
- **Why schema/legend is insufficient:** no key or relationship constraints are
  declared.
- **Operation:** aggregate key null/distinct/duplicate counts and identifier-only
  anti-join counts. Never output identifier values.

### Pathology, reports, and the wide table

#### Q010 — pathology coded and numeric domains

- **Question:** Do V2 pathology, biopsy, surgery, and location codes agree with
  the legend, and what unit/sentinel evidence is present for biopsy distance?
- **Table/columns:** `pathology_findings_anon`: all non-identifier and non-date
  columns.
- **Why schema/legend is insufficient:** `path1`–`path10` use a shared legend
  header, and several code lists and missing states are ambiguous.
- **Operation:** projected null, distinct, blank, and value-count aggregates
  for categorical fields; safe finite range, quantiles, and nonpositive counts
  for `bdistance`.

#### Q011 — pathology grain and imaging relationship

- **Question:** Is there a unique pathology key using accession, side, finding
  number, procedure date, or pathology date, and how often does
  `(acc_anon, side, numfind)` resolve to imaging findings?
- **Table/columns:** `pathology_findings_anon`: `acc_anon`, `side`, `numfind`,
  `procdate_anon`, `pdate_anon`, `__index_level_0__`;
  `imaging_findings_anon`: `acc_anon`, `side`, `numfind`.
- **Why schema/legend is insufficient:** no key is declared and matching names
  do not establish a join.
- **Operation:** aggregate null/distinct/duplicate counts for successively
  specific keys and identifier-only semi/anti-join counts. Never output
  identifiers or dates.

#### Q012 — report grain without text

- **Question:** Is `(acc_anon, rseq)` a complete unique report key and what is
  the bounded sequence-number range?
- **Table/columns:** `reports_anon`: `empi_anon`, `acc_anon`,
  `studydate_anon`, `rseq`, `__index_level_0__`. `report_anon` is prohibited.
- **Why schema/legend is insufficient:** report keys and sequencing are not
  declared.
- **Operation:** aggregate null/distinct/duplicate counts for key candidates,
  safe range/value counts for `rseq`, and index-position comparison. Never read
  or output report text, identifiers, or dates.

#### Q013 — `combined_anon` construction

- **Question:** Which key-only join pattern can explain the wide table, and are
  its index and row grain inherited from an input table?
- **Table/columns:** `combined_anon`: `empi_anon`, `acc_anon`, `side`,
  `numfind`, `linkedaccession_anon`, `procdate_anon`, `pdate_anon`,
  `__index_level_0__`; corresponding key columns from patient, exam, side,
  imaging, and pathology tables.
- **Why schema/legend is insufficient:** the wide table's row count and
  construction are not declared.
- **Operation:** key-only null/distinct/multiplicity summaries, aggregate
  semi/anti-join counts, and index-position/source-index comparisons. Never
  output identifiers or dates.

## Probe results

All registered probes completed through the locked project environment. No
operation emitted an identifier, anonymized date, clinical row, exam
description, or report text.

### Q001 result — patient categories

- All 22,936 records have `GENDER_DESC=Female`; the field is absent from the
  legend.
- Race has five labels: Asian 1,557, Black 9,516, Other 470, Unknown 2,437,
  and White 8,956.
- Ethnicity has three labels: Hispanic or Latino 1,243, Not Hispanic or Latino
  17,739, and Unknown 3,954.
- Language is null on 4,868 records and has 49 non-null labels. English
  (16,946), Spanish (572), Korean (172), and Chinese (50) are the largest; the
  bounded domain contains no blank strings.
- Cohort values are 1 (11,441) and 2 (11,495).
- The legend names race, ethnicity, language, and cohort but supplies no
  enumerated codes or missing-value semantics.

### Q002 result — patient key and export index

`empi_anon` is complete and unique across 22,936 patient rows. The
`__index_level_0__` column is also complete and unique but never equals current
zero-based row position. Parquet pandas metadata explicitly declares it an
index column with no logical name. It is therefore a verified serialization
artifact, not a clinical feature.

### Q003 result — exam descriptors, flags, and ages

- `desc` is complete and nonblank with 232 distinct labels; no labels were
  output.
- `modality_desc` has MG 112,335, US 16,325, and MRI 2,392, exactly matching
  the legend codes.
- `mg_exam_type` is null on 23,182 rows and otherwise diagnostic 26,091,
  screening 81,775, or screening and diagnostic 4; the three non-null values
  match the legend.
- `tissueden` is null on 30,552 rows. Codes 1–4 occur and agree with the
  legend; the legend's code 5, “Normal male,” is unobserved.
- `ASHKENAZI` is null on 54,352 rows, N on 75,654, and Y on 1,046. It is absent
  from the legend.
- `proc_flag` contains Y on 7,470 rows and is otherwise null;
  `biopsy_flag` contains Y on 4,170 and is otherwise null. The legend describes
  both as derived flags but does not authorize interpreting null as No.
  `extract_flag` is complete with N 5,146 and Y 125,906.
- All 27 observed `vtype` codes match the 27 legend codes. Version is 1 on
  75,597 rows and 2 on 55,455, matching the legend.
- `age_at_study_anon` is null on 16,337 rows and ranges from 18–89. The other
  three age fields are physically complete, range from zero to 76, 57, and 55,
  and contain 79,792, 59,543, and 34,415 zeroes respectively. Units and zero
  semantics are absent from the legend, so year-like scale and zero-as-sentinel
  remain inference.

### Q004 result — exam aggregates

`path_severity_exam_level` is null on 125,612 rows and otherwise takes 0–5.
The four finding aggregates are complete and include values greater than one:
mass reaches 12, asymmetry 6, architectural distortion 4, and calcification 11.
The base legend descriptions say “presence,” but those descriptions cannot be
transferred as binary definitions. The observed fields are count-like; exact
derivation and the severity scale remain unresolved.

### Q005 result — side-level grain and aggregates

- All 159,939 `(acc_anon, side)` tuples are distinct when null side is retained
  as a state. Accession is complete; side is null on 7,466 rows and otherwise B
  71,624, L 40,685, or R 40,164. B/L/R match the legend.
- The 7,466 null-side accessions have no non-null-side row.
- `total_L_find` and `total_R_find` are complete count-like values with maxima
  9 and 6.
- Each finding aggregate is null exactly on the 7,466 null-side rows and has
  count-like nonnegative values above one. `path_severity_side_level` is null
  on 154,228 rows and otherwise 0–5.
- Totals, suffixed aggregates, null-side meaning, derivation, and severity
  scale are absent from the legend.

### Q006 result — risk table

`acc_anon` is complete and unique across 77,499 rows; patient ID repeats across
17,816 patients. The serialized index is explicitly a pandas index. The table
contains 12—not 13—risk outputs:

| Output | Null | Observed range | Median | High-impact caveat |
| --- | ---: | --- | ---: | --- |
| `NCILIFE` | 1,927 | -35–100 | 8.5 | -35 occurs 1,057; -2 occurs 1,673; 100 occurs 9,237 |
| `IBISLIFE` | 21,054 | 0.1–100 | 10.9 | 100 occurs 7,460 |
| `IBISBRCA1` | 17,748 | 0.1–100 | 0.1 | 100 occurs once |
| `IBISBRCA2` | 17,748 | 0.1–100 | 0.1 | 100 occurs four times |
| `IBIS10` | 17,748 | 0.1–100 | 3.7 | 100 occurs 8,128 |
| `IBISPOP10` | 17,748 | 0.1–4.0 | 3.4 | Horizon/scale unstated |
| `IBISPOPL` | 17,748 | 0.1–13.4 | 9.0 | Horizon/scale unstated |
| `NCI5` | 19,323 | -35–100 | 1.6 | -35 occurs 709; -2 occurs 1,673; 100 occurs 6,838 |
| `IBIS_TD1` | 21,136 | 0.1–100 | 7.7 | 100 occurs 7,446 |
| `IBIS_TD2` | 21,136 | 0.1–100 | 9.7 | 100 occurs 7,446 |
| `IBIS_TD3` | 21,136 | 0.1–100 | 11.5 | 100 occurs 7,446 |
| `IBIS_TD4` | 21,136 | 0.1–100 | 15.3 | 100 occurs 7,446 |

No output has a non-finite value. Typical values and maxima support a
percentage-point-like rather than fractional representation, but the legend
contains none of these fields. Model definitions, horizons, units, negative
sentinels, density variants, and whether 100 is a cap, sentinel, or valid
extreme require maintainer confirmation.

### Q007 result — imaging coded domains

All 47 projected categorical fields have zero empty or whitespace-only values.
Null is distinct from an empty string.

- General fields: B/L/R side and all eight assessment codes agree with the
  legend. `linked_study_flag`, `stable`, `new`, and `addendum_flag` have
  observed flag domains but no legend code meanings. `location`,
  `secondaryfindings`, and `changed` contain comma-composed legend tokens.
  Recommendation has 229 serialized domains and five observed atomic tokens
  absent from the legend: `?`, `G`, `MC`, `MS`, and `MT`.
- Mammography: the four basic finding flags are complete 0/1 fields. Mass
  margin/density and calcification distribution agree with the legend.
  `massshape` adds undocumented `9`, `D`, `L`, and `M`; `calcfind` adds `N`;
  and `consistent` adds `B`. Several fields compose multiple legend tokens with
  commas. `calcnumber` is stored as a string and includes negative numeric-like
  codes with no sentinel definition.
- Ultrasound: observed tokens for `USFinding`, shape, orientation, margins,
  the misspelled `modifers`, echotexture, posterior features, vascularity, and
  surrounding tissue agree with the legend. Several are comma-compositional,
  which the legend does not explicitly explain.
- MRI: most lowercase physical headers map only by case to uppercase legend
  headers. `mdist` has an undocumented `M`. `mother` has no legend header.
  `mdelayed` and `mdelayed.1` have nearly identical L/P/S/W distributions, but
  only the former has a case-only legend match and equivalence is unverified.
  `msize` has no legend entry. `MBPE_SYM` maps only by case to `mbpe_sym`.

The complete feature-level domains and meanings are retained in the bundle;
observed disagreement is never silently normalized away.

### Q008 result — imaging numeric fields

| Field | Null | Observed range | Nonpositive evidence | Legend evidence |
| --- | ---: | --- | --- | --- |
| `numfind` | 12,810 | -9–9 | -9 on 21,407; zero once | “Finding Number”; no sentinel |
| `size` | 34,217 | -99–83 | 1,107 negative; 131,460 zero | millimeters; no sentinel |
| `distance` | 34,217 | -2–54 | 78 negative; 123,736 zero | centimeters; no sentinel |
| `msize` | 49,750 | 0 only | all 121,628 non-null values zero | no legend entry |

The negative values are observed sentinel candidates, not decoded meanings.

### Q009 result — imaging grain and linked accessions

Among 171,378 imaging rows, 12,812 have an incomplete
`(acc_anon, side, numfind)` tuple. The 158,566 complete rows contain 158,497
distinct keys, with 69 duplicate groups and maximum multiplicity two.
Therefore the candidate tuple is neither complete nor unique.

Of 21,414 non-null linked-accession rows, 21,410 resolve to the unique exam
accession surface and four do not. The same four distinct links are unresolved.

### Q010 result — pathology domains

- Side and finding number closely mirror the imaging surface: side is null on
  7,466 rows and otherwise B/L/R; `numfind` is null on 11,042, equals -9 on
  21,407, zero once, and otherwise 1–9.
- `path_severity` is null on 163,057 and otherwise 0–5, but has no legend
  definition.
- Biopsy type, technique, side, complication, surgery, and lymph-surgery values
  are subsets of their legend lists. `bdepth` is principally A/M/P and also has
  three occurrences of the legend-listed grid codes `5` and `8`.
- `path1`–`path9` collectively use 131 codes; `path10` is entirely null. The
  shared `path (1-10)` legend lists 182 codes. Of those, 115 occur and 67 are
  unobserved, while 16 observed codes are undocumented:
  `AC`, `ACG`, `ADT`, `CCA`, `FAT`, `FMC`, `HF`, `IVC`, `LNR`, `LPI`, `MCA`,
  `MCI`, `MF`, `MLL`, `PAC`, and `PAP`.
- `loc` uses 53 atomic/composite forms built from legend tokens, sometimes with
  a trailing delimiter; composition semantics are undocumented.
- `bdistance` is null on 163,033. Its 7,600 finite values range from -2 to 54;
  nine are negative and 6,091 are zero. The legend says centimeters but does
  not decode -2 or distinguish valid zero from a sentinel.

No projected pathology string field contains an empty/whitespace-only value.

### Q011 result — pathology grain and imaging relationship

No tested clinical tuple uniquely identifies pathology rows:

| Candidate | Complete rows | Distinct | Duplicate rows | Maximum multiplicity |
| --- | ---: | ---: | ---: | ---: |
| accession + side + finding | 159,589 | 158,497 | 1,092 | 4 |
| above + procedure date | 7,600 | 7,437 | 163 | 4 |
| above + pathology date | 7,600 | 7,445 | 155 | 3 |
| above + both dates | 7,600 | 7,452 | 148 | 3 |

The serialized index is complete/unique and explicitly a pandas index, but
never matches current row position. Every complete pathology triple resolves
to imaging, although 70 pathology rows match two imaging rows. Another 11,044
pathology rows have an incomplete triple.

### Q012 result — report grain without text

The probe projected only patient, accession, study date, sequence, and export
index. `report_anon` was never read.

All projected columns are complete. `(acc_anon, rseq)` has 422 duplicate rows;
adding patient and study date leaves six duplicate pairs. `rseq` ranges 0–6,
with 114,494 of 125,959 rows at sequence 1. The serialized pandas index is the
only tested complete unique field and never equals current row position.

### Q013 result — wide-table construction

`combined_anon` has 172,553 rows. All rows resolve by patient ID to the patient
table and by patient-accession to the exam table. All complete side keys and
finding triples resolve to their level-specific surfaces. Four non-null linked
accessions fail to resolve, matching the imaging result.

No tested standard imaging/pathology join explains the row count:

| Join key | Predicted rows | Observed comparison |
| --- | ---: | --- |
| accession | 266,052 | Not close |
| accession + side | 195,877 | Not close |
| accession + side + finding | 172,471 | Closest, but 82 fewer |

The physical index provides the stronger clue. Every indexed imaging projection
and every indexed pathology projection occurs in the wide table. Their index
union contains 172,470 values; the wide table contains the full union plus 83
additional indices. Its index is unique but is not current row position.

The verified conclusion is limited: `combined_anon` is a shared indexed
superset/row surface containing all level-specific finding projections plus 83
additional rows. Its exact construction algorithm, 82-row deviation from the
closest natural-key join, and authority relative to normalized tables remain
unresolved. Agents should prefer the level-specific tables for definitions and
joins unless maintainers document the wide table.

## Crosswalk outcome

The schema/legend mapping has six evidence classes:

| Mapping class | Unique names | Physical occurrences | Treatment |
| --- | ---: | ---: | --- |
| Exact trimmed header | 61 | 130 | Use legend claims at `Release legend` level |
| Case-only header | 11 | 22 | Preserve physical case; show derived match |
| Explicit anonymized alias | 5 | 15 | Show physical and legend names together |
| Shared `path (1-10)` header | 10 | 20 | Apply as a shared candidate dictionary, noting conflicts |
| Base name for level suffix | 8 | 8 | Use base meaning only as inference, not equivalence |
| No defensible match | 30 | 48 | Schema/observed evidence only; mark meaning gaps |

Sixty legend headers are not represented in the released V2 schemas under any
accepted match. They are retained as an orphan-coverage result rather than
being imported into the feature bundle:

`accession`, `accession_type`, `anterior`, `binit`, `biop_loc`, `biopsite`,
`cancer_outcome_registry_id`, `case`, `comment`, `concord`, `dcissize`,
`diag_out`, `eic`, `est`, `estp`, `extracap`, `fish`, `focality`, `her2`,
`hgrade`, `inferior`, `init`, `invsize`, `isocell`, `ki67`, `largedp`,
`lateral`, `linkedaccession_type`, `ltcomp`, `macrometa`, `medial`,
`methodevl`, `micrometa`, `nfocal`, `node_pos`, `node_rem`, `path_dr`,
`path_loc`, `pocomp`, `posterior`, `proccode`, `rnumber`, `sdate`,
`snode_rem`, `specembed`, `specinteg`, `specnum`, `specsize`, `sprocs`,
`stage`, `study`, `superior`, `surg_loc`, `surgeon`, `tech_init`, `tnmdesc`,
`tnmm`, `tnmpn`, `tnmpt`, and `tnmr`.

This crosswalk establishes full denominators, not full semantic certainty:
unknown sentinel behavior may remain explicitly “not documented; not
value-probed,” and unmatched legend entries are not treated as released V2
features.
