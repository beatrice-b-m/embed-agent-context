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
  serialized index column.
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

- **Question:** What is the risk-table record grain, and are the 13 NCI/IBIS
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

Results will be added here by query identifier after execution and challenge
review.

