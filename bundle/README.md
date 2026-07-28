# EMBED Open Data V2 clinical feature context

This directory is a portable, agent-facing reference for the released EMBED
Open Data V2 clinical tables. It explains the physical feature surface first:
where each column occurs, how it is represented, what the V2 legend says, what
bounded V2 checks observed, and what remains unknown.

It is not a database schema, a join engine, or a modeling policy. Read the
evidence and caveat columns before converting a field into a predictor, label,
or join key.

## Navigate the feature reference

- [Patient, exam, side, and risk features](patient-exam-side-risk.md)
- [Imaging-finding features](imaging-findings.md)
- [Pathology, report, and wide-table features](pathology-reports-and-wide-table.md)
- [Complete pathology code vocabularies](pathology-vocabularies.md)

Together these documents account for all 243 physical column occurrences
across the eight released Parquet tables, representing 125 unique physical
names. Repeated columns are documented at each physical level or explicitly
cross-referenced to a canonical level-specific definition.

## Table map

| Table | Rows | Physical columns | Safest current interpretation |
| --- | ---: | ---: | --- |
| `patients_anon` | 22,936 | 8 | Patient surface; `empi_anon` is complete and unique |
| `exam_level_anon` | 131,052 | 23 | Exam/accession surface; `acc_anon` is complete and unique |
| `side_level_anon` | 159,939 | 9 | Accession-side surface; `(acc_anon, side)` is unique when null side is retained as a state |
| `imaging_findings_anon` | 171,378 | 54 | Imaging-finding surface; the apparent accession/side/finding tuple is incomplete and not unique |
| `pathology_findings_anon` | 170,633 | 26 | Pathology projection aligned to finding tuples; no tested clinical tuple is unique |
| `reports_anon` | 125,959 | 6 | Report-sequence surface; no tested declared identifier tuple is fully unique |
| `risk_anon` | 77,499 | 16 | One row per represented accession; 12 NCI/IBIS-named numeric fields, two identifiers, an anonymized study date, and an export index |
| `combined_anon` | 172,553 | 101 | Wide indexed superset; construction is unresolved, so prefer normalized tables |

Row counts are release-file metadata. Grain statements are limited to
aggregate key checks and do not imply database constraints.

## Evidence labels

Claims in this bundle use these labels:

| Label | Meaning |
| --- | --- |
| **Maintainer confirmed** | Supplied or explicitly confirmed by an EMBED V2 maintainer |
| **Release schema** | Verified from the V2 Parquet schema or file metadata |
| **Release legend** | Stated by the released V2 legend |
| **Observed V2 values** | Verified by a registered projected-column aggregate |
| **Cross-table check** | Verified by a registered key-only comparison |
| **Inference** | Plausible but not established by a higher-priority source |
| **Internal background** | Supporting Cortex context, not independently verified as V2 behavior |
| **External background** | General or public context, not evidence of V2 behavior |
| **Unresolved** | Evidence is absent or conflicting; maintainer input is needed |

Evidence applies to a claim, not automatically to an entire row. A physical
type may be schema-verified while its units or clinical interpretation remain
unresolved.

## Rules for safe use

### Prefer level-specific tables

Use `patients_anon`, `exam_level_anon`, `side_level_anon`,
`imaging_findings_anon`, and `pathology_findings_anon` as the canonical places
to understand their respective features. `combined_anon` contains every
indexed imaging and pathology projection plus 83 additional indexed rows, but
no tested standard natural-key join reproduces its row count. Do not treat its
rows as a documented one-to-one finding table.

### Do not infer binary meaning from a flag-like name

Finding-level `mass`, `asymmetry`, `arch_distortion`, and `calc` are observed
0/1 fields. Their side- and exam-level suffixed counterparts take values above
one and are count-like. The exact aggregation rule is not documented.

### Keep null, zero, and sentinel candidates distinct

Null is not interchangeable with No or zero unless a source says so. Important
observed but undecoded values include:

- `numfind=-9`;
- imaging `size=-99`;
- imaging/pathology distance `-2`;
- risk output values `-35`, `-2`, and frequent `100`;
- zero-filled age-like fields and the all-zero non-null MRI `msize`; and
- null side rows at side and finding levels.

These are sentinel candidates or representation clues, not decoded meanings.
Use the feature entry's exact wording.

### Preserve coded strings

Many imaging and pathology strings contain comma-composed atomic codes. The
legend often defines atoms but not delimiter, ordering, repetition, or trailing
empty-component behavior. Preserve the source string for interpretation unless
a documented tokenizer is available. Physical case and misspellings such as
`modifers` are part of the V2 interface.

### Treat identifiers and anonymized dates as opaque

Identifiers establish only the aggregate relationships explicitly checked in
this bundle. Anonymized date columns are timestamp-typed, but the release
references do not establish offset stability, interval preservation, or
cross-patient calendar comparability. Do not derive longitudinal or
age-at-event claims without maintainer confirmation.

### Exclude serialized indexes from clinical context

`__index_level_0__` is explicitly declared as a pandas index in the six tables
where it appears. It is useful for explaining file construction but is not a
clinical feature or a portable natural key. In the four tables where
index-to-position equality was tested, no stored value equals its current row
position; that comparison was not made for imaging or risk.

### Separate contemporaneous features from later evidence

Report text, recommendations, linked studies, procedure dates, biopsy details,
and pathology may occur at different points in a clinical workflow. This
feature reference does not establish a prediction anchor or temporal
eligibility. Treat those fields as potential post-index information until a
use-specific cutoff is defined and verified.

## Legend coverage and version caution

The released legend contains 1,345 rows across 138 trimmed headers. It is not a
one-to-one contract for the V2 schemas:

- 61 unique physical names match a legend header exactly;
- 11 match only after a case comparison;
- anonymized aliases, suffixed aggregates, and `path1`–`path10` need explicit
  derived mappings;
- 30 unique physical names have no defensible legend match; and
- 60 legend headers do not occur in the released V2 schemas.

The unmatched legend entries are not imported as if they were V2 features.
Public EMBED V1 material is also not authoritative for V2. Unknown meanings,
units, sentinels, and derivations remain visible as unresolved.

## Highest-priority maintainer questions

1. What do the negative and 100-valued NCI/IBIS outputs mean, what units and
   horizons apply, and how are the four `IBIS_TD*` fields defined?
2. What are the code meanings for `path_severity` and its side/exam aggregates,
   and how are all suffixed finding aggregates derived?
3. What do `numfind=-9`, imaging `size=-99`, and distance `-2` mean?
4. What are `mdelayed.1`, `mother`, and `msize`, and is `mdelayed.1` a duplicate
   of `mdelayed`?
5. What production algorithm and intended authority define `combined_anon`,
   including its 83 indices absent from both finding tables?
6. Which ordering and interval properties do the anonymized dates preserve?
7. What clinical tuple, if any, uniquely identifies pathology and report rows?
8. Are legend code lists exhaustive, and how should undocumented observed codes
   and comma-composed values be parsed?

## Source and verification boundary

This feature layer uses:

- the eight Parquet files under `reference_files/clinical_tables/`;
- `reference_files/EMBEDv2-open-data-clinical-legend.csv`; and
- only the aggregate, projected checks registered in the project investigation
  record.

No report text was read. No clinical table row, identifier value, anonymized
date value, exam description, or row-level/free-text clinical content is
included in this bundle. Applicable release-legend code maps are intentionally
included as feature context. For the complete access ledger and aggregate
evidence, see the maintainer document
`docs/feature-context-investigation-results.md` in the source repository.
