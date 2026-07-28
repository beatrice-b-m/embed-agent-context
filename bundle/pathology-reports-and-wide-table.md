# Pathology, reports, and the wide table

[Bundle entry point](README.md) ·
[Patient, exam, side, and risk](patient-exam-side-risk.md) ·
[Imaging findings](imaging-findings.md) ·
[Complete pathology vocabularies](pathology-vocabularies.md)

This page describes every physical feature in `pathology_findings_anon` and
`reports_anon`, then accounts for all 101 physical columns in `combined_anon`.
Prefer the level-specific tables and their canonical feature descriptions.
The wide table is useful as a released convenience surface, but its production
algorithm and authority are not documented.

Evidence labels follow the definitions in the [bundle entry
point](README.md):

- **Release schema** — physical Parquet schema or footer metadata.
- **Release legend** — exact legend statement, or an explicitly named derived
  match.
- **Observed V2 values** — aggregate result from registered probe Q010 or Q012.
- **Cross-table check** — aggregate key-only result from Q011 or Q013.
- **Inference** — a bounded interpretation not established by release
  documentation.
- **Unresolved** — maintainer confirmation is needed.

No report text was read during this investigation. The only report data-page
projection was
`empi_anon, acc_anon, studydate_anon, rseq, __index_level_0__`.

## Pathology findings

### Grain and identity

`pathology_findings_anon` has 170,633 rows and 26 all-optional physical
columns. **Release schema**

No tested clinical key is unique:

| Candidate key | Complete rows | Distinct complete keys | Duplicate rows / groups | Maximum multiplicity |
| --- | ---: | ---: | ---: | ---: |
| `acc_anon` | 170,633 | 131,052 | 39,581 / 32,834 | 16 |
| `acc_anon, side` | 163,167 | 152,473 | 10,694 / 8,798 | 12 |
| `acc_anon, side, numfind` | 159,589 | 158,497 | 1,092 / 987 | 4 |
| Above plus `procdate_anon` | 7,600 | 7,437 | 163 / 143 | 4 |
| Above plus `pdate_anon` | 7,600 | 7,445 | 155 / 147 | 3 |
| Above plus both dates | 7,600 | 7,452 | 148 / 140 | 3 |
| `__index_level_0__` | 170,633 | 170,633 | 0 / 0 | 1 |

**Cross-table check (Q011).** The serialized index is complete and unique, but
zero of its 170,633 values equals the zero-based row position. Treat it as a
retained source/export index, not as a clinically meaningful finding number or
a documented durable identifier.

Every one of the 159,589 pathology rows with a complete
`(acc_anon, side, numfind)` key resolves to `imaging_findings_anon`; all 158,497
distinct complete keys resolve. Of those pathology rows, 159,519 have one
imaging match and 70 have two. The other 11,044 pathology rows have an
incomplete triple and were not matched under null-equal semantics.
**Cross-table check (Q011).** This establishes release-specific resolution, not
clinical one-to-one equivalence.

### Identity, timing, and severity columns

| Physical column | Type | Feature context |
| --- | --- | --- |
| `pathology_findings_anon.acc_anon` | `int64` | Anonymous exam/accession identifier. It is complete but repeated. The legend describes base header `acc` as the unique site record identifier for an exam; applying that meaning to the suffixed physical field is **Inference**. **Release schema; Release legend for base header; Cross-table check** |
| `pathology_findings_anon.side` | `string` | Finding side. Legend codes are `L` left, `R` right, and `B` both. Observed: `B` 71,957; `L` 46,059; `R` 45,151; null 7,466. **Release legend; Observed V2 values** |
| `pathology_findings_anon.numfind` | `int8` | Finding number. Observed: null 11,042; `-9` 21,407; `0` 1; `1` 120,782; `2` 13,492; `3` 2,940; `4` 695; `5` 181; `6` 61; `7` 22; `8` 8; `9` 2. The legend defines no codes, so the meaning of `-9` and the exceptional zero is **Unresolved**. **Release legend; Observed V2 values** |
| `pathology_findings_anon.path_severity` | `int8` | Finding-level pathology severity. Observed: null 163,057; `0` 1,909; `1` 751; `2` 1,076; `3` 64; `4` 3,634; `5` 142. There is no matching legend header, and ordinality or meanings must not be inferred from the integers. **Observed V2 values; Unresolved** |
| `pathology_findings_anon.procdate_anon` | `timestamp[ns]` | Anonymized procedure date. The base legend header `procdate` says “Procedure Date”; applying it to the suffixed field is **Inference**. Footer metadata reports 163,033 nulls. Date-shift and interval-preservation behavior is **Unresolved**. **Release schema; Release legend for base header** |
| `pathology_findings_anon.pdate_anon` | `timestamp[ns]` | Anonymized pathology-report date. The base legend header `pdate` says “Pathology report date”; applying it to the suffixed field is **Inference**. Footer metadata reports 163,033 nulls. Date-shift and interval-preservation behavior is **Unresolved**. **Release schema; Release legend for base header** |
| `pathology_findings_anon.__index_level_0__` | `int64` | Complete, unique retained index; not row position and not documented as a clinical key. **Release schema; Cross-table check** |

The two date columns are simultaneously complete in only 7,600 rows.
Procedure, surgery, pathology, and report-date fields may represent information
recorded after the imaging exam. Do not use them as contemporaneous predictors
unless a prediction anchor and information-availability policy explicitly
permit them.

### Procedure and surgery columns

All string columns projected by Q010 had zero empty or whitespace-only values.
Null is common, but the legend does not assign null a clinical meaning.
The [pathology vocabulary appendix](pathology-vocabularies.md) contains every
applicable legend code and meaning, including codes not observed in this
release.

| Physical column | Type | Observed domain and release meaning |
| --- | --- | --- |
| `pathology_findings_anon.type` | `string` | Biopsy type: `B` needle-biopsy pathology 6,381; `S` surgical pathology 1,219; null 163,033. The observed domain is a subset of the legend. **Release legend; Observed V2 values** |
| `pathology_findings_anon.technique` | `string` | Biopsy technique: `CA` 22, `CB` 7, `EB` 51, `FNA` 18, `MA` 5, `MR` 71, `MRX` 234, `SA` 27, `SB` 1,850, `TB` 55, `UA` 9, `UB` 3,926; null 164,358. All observed codes are legend-listed. **Release legend; Observed V2 values** |
| `pathology_findings_anon.bside` | `string` | Biopsy side: `B` both 37, `L` left 3,857, `R` right 3,699; null 163,040. **Release legend; Observed V2 values** |
| `pathology_findings_anon.bcomp` | `string` | Biopsy complication. Only `H` hematoma requiring surgery (1) and `I` infection requiring antibiotics (3) occur; null 170,629. The legend also lists unobserved `L`, `N`, `P`, and `X`. **Release legend; Observed V2 values** |
| `pathology_findings_anon.surgery` | `string` | Surgery type: `A` 2, `E` 185, `L` 256, `M` 747, `O` 9, `RE` 5, `SE` 12; null 169,417. All observed codes are legend-listed; the legend contains additional unobserved surgery codes. **Release legend; Observed V2 values** |
| `pathology_findings_anon.lymphsurg` | `string` | Lymph-node surgery type: `AN` 37, `HAN` 2, `NS` 85, `O` 1, `S` 517; null 169,991. All observed codes are legend-listed; `IMN` and `LAN` are listed but unobserved. **Release legend; Observed V2 values** |

The legend meanings for the observed surgery codes are:

- `A` axillary dissection; `E` excisional breast biopsy; `L` lumpectomy;
  `M` mastectomy, all types; `O` other; `RE` re-excision; `SE` surgical
  excision.
- `AN` axillary lymph-node dissection; `HAN` high axillary lymph-node
  dissection; `NS` lymph nodes not sampled; `O` other; `S` sentinel-node
  biopsy.

These are potentially post-index procedure/outcome features. Their timing
relative to an imaging exam is not established here; a documented task anchor
must determine whether they are eligible.

### Pathology-code slots

The physical columns are `path1`, `path2`, `path3`, `path4`, `path5`, `path6`,
`path7`, `path8`, `path9`, and `path10`, all `string`. The legend has no exact
header for any slot; its shared header is `path (1-10)`, so applying that list
to the physical columns is an explicit derived match. **Release schema; Release
legend**

| Column | Null rows | Distinct non-null codes |
| --- | ---: | ---: |
| `pathology_findings_anon.path1` | 163,046 | 117 |
| `pathology_findings_anon.path2` | 166,288 | 82 |
| `pathology_findings_anon.path3` | 168,553 | 59 |
| `pathology_findings_anon.path4` | 169,700 | 44 |
| `pathology_findings_anon.path5` | 170,251 | 31 |
| `pathology_findings_anon.path6` | 170,496 | 22 |
| `pathology_findings_anon.path7` | 170,580 | 16 |
| `pathology_findings_anon.path8` | 170,621 | 3 |
| `pathology_findings_anon.path9` | 170,632 | 1 |
| `pathology_findings_anon.path10` | 170,633 | 0 |

Across `path1` through `path9`, 131 codes occur. The shared legend lists 182
codes: 115 are observed and 67 are unobserved. Sixteen observed codes have no
entry in that legend list:

`AC`, `ACG`, `ADT`, `CCA`, `FAT`, `FMC`, `HF`, `IVC`, `LNR`, `LPI`, `MCA`,
`MCI`, `MF`, `MLL`, `PAC`, `PAP`.

**Observed V2 values; Release legend conflict.** Do not silently label those 16
codes, and do not assume the legend list is exhaustive. The slot ordering,
whether codes may repeat across slots, and whether later slots are secondary
findings are **Unresolved**.

See the [complete shared pathology-code map](pathology-vocabularies.md#shared-path-1-10-map)
for all 182 legend-listed code meanings.

### Biopsy location and distance

| Physical column | Type | Feature context |
| --- | --- | --- |
| `pathology_findings_anon.loc` | `string` | Biopsy location. Null 167,122; 3,511 non-null values across 53 serialized forms. Legend atoms cover clock positions `1`–`12`, quadrants and regions, but observed values also contain comma-delimited combinations and trailing empty components. The delimiter, component ordering, and whether the list is compositional are **Unresolved**. **Release legend; Observed V2 values; Inference for splitting** |
| `pathology_findings_anon.bdepth` | `string` | Depth. Observed: `A` 294, `M` 573, `P` 447, `5` 1, `8` 2; null 169,316. The legend defines `A/M/P` as anterior/middle/posterior and numeric `1`–`9` as a 3×3 location grid, including `5 = 2B` and `8 = 3B`. **Release legend; Observed V2 values** |
| `pathology_findings_anon.bdistance` | `double` | Distance in centimeters according to the legend. Null 163,033; 7,600 finite; range −2 to 54; quartiles 0/0/0; 9 negative, 6,091 zero, and 6,100 nonpositive. No nonfinite values. The meaning of −2 and whether zero is a sentinel or a measured distance are **Unresolved**. **Release legend; Observed V2 values** |

For `loc`, every observed nonempty comma-separated atom is legend-listed, but
the serialized combinations themselves are not. Preserve the raw string until
maintainers confirm a parsing rule.
The [location and depth maps](pathology-vocabularies.md#location-maps) list all
legend-defined atomic codes.

## Reports

`reports_anon` has 125,959 rows and six all-optional schema fields. The five
non-text columns inspected by Q012 contained no nulls. No `report_anon`
data-page value or content was accessed; its zero null count comes only from
footer metadata.

| Physical column | Type | Feature context |
| --- | --- | --- |
| `reports_anon.empi_anon` | `int64` | Anonymous patient identifier. The legend calls it the unique patient identifier. There are 22,938 distinct values in the report table. **Release schema; Release legend; Observed V2 values** |
| `reports_anon.acc_anon` | `int64` | Anonymous exam/accession identifier. There are 114,292 distinct values. Applying the base legend header `acc` to this suffixed field is **Inference**. **Release schema; Release legend for base header; Observed V2 values** |
| `reports_anon.studydate_anon` | `timestamp[ns]` | Anonymized exam date. The legend calls it “Exam date”; Q012 and footer metadata show no nulls. Preservation of time intervals and ordering after anonymization is **Unresolved**. **Release schema; Release legend; Observed V2 values** |
| `reports_anon.rseq` | `int8` | “Report sequence number” is **Inference** from the name; no legend definition was found. Observed domain: `0` 95, `1` 114,494, `2` 10,555, `3` 616, `4` 170, `5` 16, `6` 13. The meaning of zero and whether the sequence is chronological are **Unresolved**. **Release schema; Observed V2 values** |
| `reports_anon.report_anon` | `string` | Report representation is physically a string, and footer metadata reports no nulls. No content, value, length, vocabulary, or blank check was performed, and no exact legend definition was found. **Release schema only** |
| `reports_anon.__index_level_0__` | `int64` | Complete and unique in the five-column key projection, but never equal to row position. Parquet metadata declares it a pandas index; it is not a documented report identifier. **Release schema; Observed V2 values** |

### Report grain

| Candidate key | Distinct of 125,959 | Duplicate rows / groups | Maximum multiplicity |
| --- | ---: | ---: | ---: |
| `empi_anon` | 22,938 | 103,021 / 18,217 | 53 |
| `acc_anon` | 114,292 | 11,667 / 10,827 | 9 |
| `empi_anon, acc_anon` | 114,292 | 11,667 / 10,827 | 9 |
| `acc_anon, studydate_anon` | 121,996 | 3,963 / 3,788 | 5 |
| `acc_anon, rseq` | 125,537 | 422 / 421 | 3 |
| `acc_anon, studydate_anon, rseq` | 125,953 | 6 / 6 | 2 |
| Above plus `empi_anon` | 125,953 | 6 / 6 | 2 |
| `__index_level_0__` | 125,959 | 0 / 0 | 1 |

**Observed V2 values (Q012).** `(acc_anon, rseq)` is not a unique report key,
and adding patient and study date still leaves six duplicated pairs. A report
should therefore be described as a released report row associated with patient,
accession, date, and sequence—not as a uniquely identified report—unless the
export index is deliberately retained with appropriate provenance caveats.

The report table has 22,938 distinct patient identifiers, while
`patients_anon` and `combined_anon` each have 22,936. No report-to-patient
anti-join was registered, so this count difference does not establish which
identifiers differ or why. **Observed V2 values; Unresolved**

## `combined_anon`

### What the key checks establish

`combined_anon` has 172,553 rows and 101 all-optional physical columns.
**Release schema**

- All 172,553 rows resolve exactly once by `empi_anon` to `patients_anon` and
  exactly once by `(empi_anon, acc_anon)` to `exam_level_anon`.
- All 163,329 complete `(acc_anon, side)` rows resolve to `side_level_anon`.
- All 159,741 complete `(acc_anon, side, numfind)` rows resolve to both finding
  tables.
- Of 21,924 non-null linked-accession rows, 21,920 resolve to the exam table and
  four do not; 150,629 linked accessions are null.
- The combined index is complete and unique but matches zero row positions.

**Cross-table check (Q013).**

Every imaging projected key/index row and every pathology projected key/index
row occurs in `combined_anon`, using null-equal comparison of represented
values:

| Index-set relationship | Count |
| --- | ---: |
| Imaging indices | 171,378 |
| Pathology indices | 170,633 |
| Intersection | 169,541 |
| Imaging only | 1,837 |
| Pathology only | 1,092 |
| Union | 172,470 |
| Combined indices outside that union | 83 |

The union is wholly contained in combined. Combined ordering is not source
ordering: only 101 of 171,378 compared positions equal the imaging index, and
55 of 170,633 equal the pathology index.

A standard join does not reproduce the table:

| Imaging/pathology join key | Relevant standard prediction | Predicted rows | Observed combined rows |
| --- | --- | ---: | ---: |
| `acc_anon` | Any standard join; key sets coincide | 266,052 | 172,553 |
| `acc_anon, side` | Null-equal joins or SQL left join | 195,877 | 172,553 |
| `acc_anon, side, numfind` | Null-equal joins or SQL left join | 172,471 | 172,553 |

For the closest triple-key pattern, 169,506 of 169,541 key groups have the
predicted multiplicity, but 35 differ and combined has 82 additional rows.
**Cross-table check (Q013).** The evidence supports a shared indexed superset
or row surface, not a documented multiplicative join. The exact construction
remains **Unresolved**.

### Complete qualified-column crosswalk

This crosswalk accounts for every physical `combined_anon` occurrence. It is a
same-name, same-type structural routing map. Q013 verified key/index
relationships and selected linked-accession/date representations only; it did
not compare every non-key value. Therefore “canonical owner” does not assert
that every wide value is an authoritative copy.

For all 100 routed, non-index occurrences below, `combined_anon`-specific
missing, sentinel, and value-domain behavior is **not documented; not
value-probed**. Canonical links transfer feature context only, not source-table
counts or value equality.

#### Patient-owned occurrences — 7

| Qualified combined occurrences | Type | Canonical owner |
| --- | --- | --- |
| `combined_anon.empi_anon` | `int64` | [Patient features](patient-exam-side-risk.md#patient-features) |
| `combined_anon.GENDER_DESC`, `combined_anon.race`, `combined_anon.ethnicity`, `combined_anon.patient_language` | `string` | [Patient features](patient-exam-side-risk.md#patient-features) |
| `combined_anon.PATIENT_BIRTH_DT_anon` | `timestamp[ns]` | [Patient features](patient-exam-side-risk.md#patient-features) |
| `combined_anon.cohort_num` | `int8` | [Patient features](patient-exam-side-risk.md#patient-features) |

#### Exam-owned occurrences — 17

| Qualified combined occurrences | Type | Canonical owner |
| --- | --- | --- |
| `combined_anon.studydate_anon` | `timestamp[ns]` | [Exam features](patient-exam-side-risk.md#exam-features) |
| `combined_anon.acc_anon` | `int64` | [Exam features](patient-exam-side-risk.md#exam-features); also the finding/report relationship key |
| `combined_anon.desc`, `combined_anon.modality_desc`, `combined_anon.loc_num_anon`, `combined_anon.mg_exam_type`, `combined_anon.ASHKENAZI`, `combined_anon.proc_flag`, `combined_anon.biopsy_flag`, `combined_anon.extract_flag`, `combined_anon.vtype` | `string` | [Exam features](patient-exam-side-risk.md#exam-features) |
| `combined_anon.tissueden`, `combined_anon.version` | `int8` | [Exam features](patient-exam-side-risk.md#exam-features) |
| `combined_anon.age_at_study_anon`, `combined_anon.menopauseage_anon`, `combined_anon.pregnancyage_anon`, `combined_anon.menarcheage_anon` | `int16` | [Exam features](patient-exam-side-risk.md#exam-features) |

The five suffixed exam-level aggregate fields in `exam_level_anon` are not
present in combined.

#### Side-owned occurrences — 3

| Qualified combined occurrences | Type | Canonical owner |
| --- | --- | --- |
| `combined_anon.side` | `string` | [Side features](patient-exam-side-risk.md#side-features); also part of both finding-table keys |
| `combined_anon.total_L_find`, `combined_anon.total_R_find` | `int8` | [Side features](patient-exam-side-risk.md#side-features) |

The five suffixed side-level aggregate fields in `side_level_anon` are not
present in combined.

#### Imaging-owned occurrences — 51

| Qualified combined occurrences | Type | Canonical owner |
| --- | --- | --- |
| `combined_anon.linkedaccession_anon` | `int64` | [Imaging findings](imaging-findings.md) |
| `combined_anon.linked_study_flag`, `combined_anon.asses`, `combined_anon.massshape`, `combined_anon.massmargin`, `combined_anon.massdens`, `combined_anon.calcfind`, `combined_anon.calcdistri`, `combined_anon.calcnumber`, `combined_anon.otherfind`, `combined_anon.implanfind`, `combined_anon.consistent`, `combined_anon.mdelayed.1`, `combined_anon.secondaryfindings`, `combined_anon.location`, `combined_anon.depth`, `combined_anon.changed`, `combined_anon.USFinding`, `combined_anon.shape`, `combined_anon.orientation`, `combined_anon.margins`, `combined_anon.modifers`, `combined_anon.echotexture`, `combined_anon.posteriorfeatures`, `combined_anon.vascularity`, `combined_anon.surroundingtissue`, `combined_anon.mfocus`, `combined_anon.mshape`, `combined_anon.mmargin`, `combined_anon.menhance`, `combined_anon.mdist`, `combined_anon.mpattern`, `combined_anon.msym`, `combined_anon.massoc`, `combined_anon.mother`, `combined_anon.minitial`, `combined_anon.mdelayed`, `combined_anon.mbpe_level`, `combined_anon.MBPE_SYM`, `combined_anon.addendum_flag`, `combined_anon.recc` | `string` | [Imaging findings](imaging-findings.md) |
| `combined_anon.numfind`, `combined_anon.mass`, `combined_anon.asymmetry`, `combined_anon.arch_distortion`, `combined_anon.calc`, `combined_anon.stable`, `combined_anon.new`, `combined_anon.msize` | `int8` | [Imaging findings](imaging-findings.md); `numfind` is also the pathology relationship field |
| `combined_anon.size`, `combined_anon.distance` | `int16` | [Imaging findings](imaging-findings.md) |

`addendum_flag` belongs to the imaging-finding schema despite its report-like
name. It is not evidence that report text or report sequence rows were joined
into combined.

#### Pathology-owned occurrences — 22

| Qualified combined occurrences | Type | Canonical owner |
| --- | --- | --- |
| `combined_anon.path_severity` | `int8` | [Pathology findings](#pathology-findings) |
| `combined_anon.procdate_anon`, `combined_anon.pdate_anon` | `timestamp[ns]` | [Pathology findings](#pathology-findings) |
| `combined_anon.type`, `combined_anon.technique`, `combined_anon.bside`, `combined_anon.bcomp`, `combined_anon.surgery`, `combined_anon.lymphsurg`, `combined_anon.path1`, `combined_anon.path2`, `combined_anon.path3`, `combined_anon.path4`, `combined_anon.path5`, `combined_anon.path6`, `combined_anon.path7`, `combined_anon.path8`, `combined_anon.path9`, `combined_anon.path10`, `combined_anon.loc`, `combined_anon.bdepth` | `string` | [Pathology findings](#pathology-findings) |
| `combined_anon.bdistance` | `double` | [Pathology findings](#pathology-findings) |

These columns carry the same sentinel, legend-coverage, composition, and
temporal-leakage caveats described for the level-specific pathology table.

#### Wide-table-local occurrence — 1

| Qualified combined occurrence | Type | Handling |
| --- | --- | --- |
| `combined_anon.__index_level_0__` | `int64` | Unique retained wide-row index. It overlaps both finding-table index sets, includes 83 values in neither, and is never row position. Preserve only for release-specific provenance; do not give it clinical meaning. **Cross-table check** |

No `reports_anon`-specific occurrence—neither `rseq` nor `report_anon`—appears
in combined. Shared identifiers and `studydate_anon` are routed to their
patient/exam canonical definitions rather than treated as report-derived.
Risk outputs and the exam/side suffixed aggregate fields are also absent.

## Safe interpretation

- Use `pathology_findings_anon` for pathology feature definitions and
  `reports_anon` for report rows. Use combined only when its unresolved row
  construction is acceptable for the task.
- Do not treat `path_severity`, pathology codes, procedure/surgery fields,
  pathology dates, or report-derived information as available at imaging time
  without an explicit temporal anchor.
- Do not decode `-9`, zero-heavy `bdistance`, undocumented pathology codes, or
  comma-delimited `loc` by guesswork.
- Do not use any `__index_level_0__` as a clinical identifier. It is useful for
  release-specific traceability, and its stability across releases is
  unverified.
- Do not assume anonymized timestamps preserve cross-patient ordering,
  absolute intervals, or real calendar meaning.

## Maintainer questions

1. What exact operation produces `combined_anon`, what are its 83
   finding-table-independent rows, and which level-specific table is
   authoritative when same-named values disagree?
2. What is the provenance and intended stability of each
   `__index_level_0__`? Is it safe only within this release?
3. What row identifier distinguishes repeated pathology records when
   accession, side, finding number, procedure date, and pathology date are
   duplicated?
4. What do `path_severity` values 0–5 mean, and is the field ordinal?
5. How should `numfind = -9` and the exceptional `numfind = 0` be interpreted?
6. Are the 16 observed but unlisted pathology codes valid additions, legacy
   codes, or data errors? Is `path (1-10)` exhaustive, and what determines slot
   order?
7. Is `loc` formally comma-compositional, and what do trailing commas mean?
8. What do `bdistance = -2` and the large concentration of zero values mean?
9. What anonymization properties are preserved for procedure, pathology-report,
   study, and birth dates?
10. What constitutes a unique report, what does `rseq = 0` mean, why do six
    patient/accession/date/sequence tuples duplicate, and are report patient
    identifiers expected to extend beyond `patients_anon`?
