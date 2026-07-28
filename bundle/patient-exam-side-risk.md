# Patient, exam, side, and risk features

[Back to the bundle entry point](README.md).

This reference covers every physical column in `patients_anon`,
`exam_level_anon`, `side_level_anon`, and `risk_anon`. Claims are labeled
**Release schema**, **Release legend**, **Observed V2 values**, **Inference**,
or **Unresolved**. An observed domain describes this release; it is not proof
that a code list is exhaustive in future releases.

## Table grain

| Table | Rows | Grain evidence and safe interpretation |
| --- | ---: | --- |
| `patients_anon` | 22,936 | `patients_anon.empi_anon` is complete and unique. Treat the table as one row per patient in this release. **Observed V2 values.** |
| `exam_level_anon` | 131,052 | The filename and feature construction indicate exam-level content, but Q001–Q006 did not test an exam key. Do not assume `exam_level_anon.acc_anon` is complete or unique until a key probe confirms it. **Release schema; Inference; Unresolved.** |
| `side_level_anon` | 159,939 | `(side_level_anon.acc_anon, side_level_anon.side)`, retaining null as a distinct side state, is complete on accession and unique across all rows. There are 7,466 null-side rows; none of those accessions also has a non-null-side row. **Observed V2 values.** |
| `risk_anon` | 77,499 | `risk_anon.acc_anon` is complete and unique, so the release has one risk row per accession. It contains 17,816 distinct patients. **Observed V2 values.** |

`patients_anon.__index_level_0__` and
`risk_anon.__index_level_0__` are explicitly named as pandas index columns in
the Parquet metadata. They are export artifacts, not clinical features.
**Release schema.**

## Patient features

| Feature and representation | Meaning or observed domain | Missing and sentinel evidence | Evidence and caveats |
| --- | --- | --- | --- |
| `patients_anon.empi_anon` — `int64`, identifier | Unique patient identifier. | No nulls; 22,936 distinct values in 22,936 rows. | Meaning: **Release legend.** Completeness and uniqueness: **Observed V2 values.** Never present values in agent output. |
| `patients_anon.GENDER_DESC` — string, nominal | Only `Female` is observed (22,936). | No null or blank values. | **Observed V2 values.** The field is absent from the legend; the provenance and intended sex/gender construct are **Unresolved**. |
| `patients_anon.race` — string, nominal | Asian 1,557; Black 9,516; Other 470; Unknown 2,437; White 8,956. | No null or blank values. `Unknown` is an explicit value. | “Patient race”: **Release legend.** Domain and counts: **Observed V2 values.** Collection method and whether the categories are exhaustive are **Unresolved**. |
| `patients_anon.ethnicity` — string, nominal | Hispanic or Latino 1,243; Not Hispanic or Latino 17,739; Unknown 3,954. | No null or blank values. `Unknown` is explicit. | “Patient ethnicity”: **Release legend.** Domain and counts: **Observed V2 values.** Collection method is **Unresolved**. |
| `patients_anon.patient_language` — string, nominal | Patient's spoken language. The 49 observed non-null labels are Amharic, Arabic, Bahasa, Bengali, Bulgarian, Burmese, Cambodian, Cantonese, Chinese, Chuukese, Croatian, Dutch, English, French, Greek, Gujarati, Haitian, Hebrew, Hindi, Italian, Japanese, Kareni, Kinyarwanda, Korean, Lao, Mandarin, Nepali, Norwegian Nynorsk, Oromo, Other, Persian, Polish, Portuguese, Romanian, Russian, Serbian, Sign Language, Somali, Spanish, Tagalog, Taiwanese Hokkien, Telugu, Thai, Tigrinya, Turkish, Ukrainian, Unknown, Urdu, and Vietnamese. | 4,868 nulls; no blanks. `Unknown` and `Other` are also explicit labels. | Meaning: **Release legend.** Domain/null count: **Observed V2 values.** The legend supplies no code list or distinction between null and `Unknown`. |
| `patients_anon.PATIENT_BIRTH_DT_anon` — `timestamp[ns]`, anonymized date-like value | Name suggests an anonymized patient birth date. | Null count, shifting method, precision, and preserved interval/order properties were not tested. | Representation: **Release schema.** Meaning from name: **Inference.** The field is absent from the legend; date behavior is **Unresolved**. Never emit values. |
| `patients_anon.cohort_num` — `int8`, nominal | Patient cohort number: `1` 11,441; `2` 11,495. | No nulls. | Meaning: **Release legend.** Domain/counts: **Observed V2 values.** The cohort construction is **Unresolved**. |
| `patients_anon.__index_level_0__` — `int64`, technical index | Preserved unnamed pandas index; all 22,936 values are distinct. It does not equal current zero-based row position. | No nulls. | Index role: **Release schema.** Cardinality/position comparison: **Observed V2 values.** Exclude from clinical feature sets. |

## Exam features

| Feature and representation | Meaning or observed domain | Missing and sentinel evidence | Evidence and caveats |
| --- | --- | --- | --- |
| `exam_level_anon.empi_anon` — `int64`, identifier | Unique patient identifier. | Table-specific completeness and cardinality were not tested. | Meaning: **Release legend.** Never emit values. |
| `exam_level_anon.studydate_anon` — `timestamp[ns]`, anonymized date | Exam date. | Table-specific null count and anonymization behavior were not tested. | Meaning: **Release legend.** Representation: **Release schema.** Preserved ordering/interval properties are **Unresolved**; never emit values. |
| `exam_level_anon.acc_anon` — `int64`, identifier | Anonymized exam record identifier. | Completeness and uniqueness were not tested in this table. | The legend describes `acc` and `accession`, not this exact header, as a unique site record identifier for an exam. Mapping to `acc_anon`: **Inference.** Never emit values. |
| `exam_level_anon.desc` — string, nominal/free description | Procedure description; 232 exact values occur. | No nulls or blanks. Values were deliberately not exposed. | Meaning: **Release legend.** Counts: **Observed V2 values.** Treat as potentially sensitive text-like data rather than a safe display field. |
| `exam_level_anon.modality_desc` — string, nominal | `MG` mammogram 112,335; `US` ultrasound 16,325; `MRI` magnetic resonance imaging 2,392. | No nulls or blanks. | Code meanings: **Release legend.** Counts and complete observed domain: **Observed V2 values.** |
| `exam_level_anon.loc_num_anon` — string, nominal | Name suggests anonymized exam location. The base legend header `loc_num` lists `LOC001`–`LOC003` and `LOC005`–`LOC014` as Sites 1–3 and 5–14; `LOC004` is not listed. | Observed values and nulls were not read. | Base meaning/codes: **Release legend.** Applicability to the suffixed V2 field: **Inference; Unresolved.** |
| `exam_level_anon.mg_exam_type` — string, nominal | `screening` 81,775; `diagnostic` 26,091; `screening and diagnostic` 4. Derived from exam description. | 23,182 nulls; no blanks. | Codes and meanings: **Release legend.** Counts/nulls: **Observed V2 values.** Null semantics are not stated. |
| `exam_level_anon.tissueden` — `int8`, ordinal code | Observed: `1` almost entirely fat 9,183; `2` scattered fibroglandular densities 42,094; `3` heterogeneously dense 43,623; `4` extremely dense 5,600. The legend also lists unobserved `5`, “Normal male.” | 30,552 nulls. | Meanings: **Release legend.** Counts: **Observed V2 values.** Code 5 shows that the legend is broader than this observed cohort; do not silently collapse null with a code. |
| `exam_level_anon.ASHKENAZI` — string, nominal flag | `N` 75,654; `Y` 1,046. The name suggests an Ashkenazi ancestry flag. | 54,352 nulls. | Domain/counts: **Observed V2 values.** Meaning from header: **Inference.** Definition, provenance, and null semantics are **Unresolved**. |
| `exam_level_anon.age_at_study_anon` — `int16`, numeric | Observed finite range 18–89. The name suggests age at exam. | 16,337 nulls; no nonpositive or nonfinite values. | Range: **Observed V2 values.** Meaning/unit from name: **Inference.** Years and anonymization behavior are not confirmed. |
| `exam_level_anon.menopauseage_anon` — `int16`, numeric/sentinel-coded | Observed range 0–76; name suggests age at menopause. | No nulls; zero occurs 79,792 times and is the only nonpositive value. | Range/counts: **Observed V2 values.** Unit and whether zero means unknown, not applicable, or not yet menopausal are **Unresolved**. |
| `exam_level_anon.pregnancyage_anon` — `int16`, numeric/sentinel-coded | Observed range 0–57; the precise pregnancy event represented by the name is not defined. | No nulls; zero occurs 59,543 times and is the only nonpositive value. | Range/counts: **Observed V2 values.** Meaning, unit, and zero semantics are **Unresolved**. |
| `exam_level_anon.menarcheage_anon` — `int16`, numeric/sentinel-coded | Observed range 0–55; name suggests age at menarche. | No nulls; zero occurs 34,415 times and is the only nonpositive value. | Range/counts: **Observed V2 values.** Unit and zero semantics are **Unresolved**. |
| `exam_level_anon.proc_flag` — string, one-sided flag | `Y` occurs 7,470 times. The flag identifies exams related to any procedure and is derived from exam description. | 123,582 nulls; no explicit `N` values. | Meaning: **Release legend.** Domain/counts: **Observed V2 values.** Do not interpret null as “No” without confirmation. |
| `exam_level_anon.biopsy_flag` — string, one-sided flag | `Y` occurs 4,170 times. The flag identifies exams related to a biopsy procedure and is derived from exam description. | 126,882 nulls; no explicit `N` values. | Meaning: **Release legend.** Domain/counts: **Observed V2 values.** Do not interpret null as “No” without confirmation. |
| `exam_level_anon.extract_flag` — string, binary flag | Qualification for imaging extraction from PACS: `N` 5,146; `Y` 125,906. | No nulls or blanks. | Meaning: **Release legend.** Domain/counts: **Observed V2 values.** This is an extraction/workflow flag, not a clinical finding. |
| `exam_level_anon.path_severity_exam_level` — `int8`, coded aggregate | Observed codes/counts: 0=1,262; 1=466; 2=727; 3=50; 4=2,868; 5=67. | 125,612 nulls. | **Observed V2 values.** No exact or base legend definition exists. Code meanings and aggregation rule are **Unresolved**. |
| `exam_level_anon.mass_exam_level` — `int8`, count-like aggregate | 0=124,511; 1=5,799; 2=591; 3=107; 4=33; 5=7; 6=2; 7=1; 12=1. | No nulls. | **Observed V2 values.** The absent suffixed header must not inherit the base legend's binary “presence” wording: values above 1 conflict with that interpretation. Construction is **Unresolved**. |
| `exam_level_anon.asymmetry_exam_level` — `int8`, count-like aggregate | 0=119,826; 1=9,998; 2=1,075; 3=130; 4=18; 5=1; 6=4. | No nulls. | **Observed V2 values.** Values above 1 conflict with transferring the base “presence” definition. Construction is **Unresolved**. |
| `exam_level_anon.arch_distortion_exam_level` — `int8`, count-like aggregate | 0=129,857; 1=1,103; 2=81; 3=6; 4=5. | No nulls. | **Observed V2 values.** Values above 1 conflict with transferring the base “presence” definition. Construction is **Unresolved**. |
| `exam_level_anon.calc_exam_level` — `int8`, count-like aggregate | 0=123,499; 1=6,667; 2=760; 3=99; 4=17; 5=4; 6=5; 11=1. | No nulls. | **Observed V2 values.** Values above 1 conflict with transferring the base “presence” definition. Construction is **Unresolved**. |
| `exam_level_anon.vtype` — string, nominal code | Visit type. All 27 legend codes occur; see the code map below. | 6,215 nulls; no blanks. | Meaning/codes: **Release legend.** Domain/counts: **Observed V2 values.** Null semantics are not defined. |
| `exam_level_anon.version` — `int8`, nominal code | `1`, “part of EMBED v1,” 75,597; `2`, “part of EMBED v2,” 55,455. | No nulls. | Meanings: **Release legend.** Counts: **Observed V2 values.** Whether this denotes source membership, processing lineage, or schema version needs clarification. |

### `exam_level_anon.vtype` legend map

| Codes | Legend meanings |
| --- | --- |
| `1`, `2`, `3`, `6` | Procedure; Loc; Response to treatment; Short-term follow-up of prior MR finding |
| `A`, `B`, `C`, `D`, `E` | Additional evaluation requested from recent study; Post biopsy; Technical Callback; Outside films not available; Evaluate finding on outside films |
| `F`, `G`, `H`, `I`, `K` | Short-interval follow-up; Extent of disease; High-risk screening; Evaluate finding on MRI; Abnormal finding on prior study |
| `L`, `M`, `N`, `O`, `P` | Post lumpectomy; Post mastectomy follow-up; Specimen; Review of outside study; Problem indicated |
| `Q`, `R`, `S`, `T`, `U`, `V`, `X`, `Z` | Reflector Placement; Pre-reduction mammoplasty; Screening; Pre-radiation therapy; Implant Evaluation; Additional evaluation requested at current screening; Abnormal finding on other modality; Post chemo |

## Side features

| Feature and representation | Meaning or observed domain | Missing and sentinel evidence | Evidence and caveats |
| --- | --- | --- | --- |
| `side_level_anon.acc_anon` — `int64`, identifier | Anonymized exam record identifier; 131,052 distinct values. | No nulls. | Cardinality: **Observed V2 values.** Meaning via legend `acc`/`accession`: **Inference.** Never emit values. |
| `side_level_anon.side` — string, nominal | `B` Both 71,624; `L` Left 40,685; `R` Right 40,164. | 7,466 nulls. Null-side accessions have no non-null-side row. | Code meanings: **Release legend.** Counts/key behavior: **Observed V2 values.** The conceptual meaning of the null-side state is **Unresolved**. |
| `side_level_anon.total_L_find` — `int8`, count-like | Observed `0`–`7` plus `9`; counts: 0=44,344; 1=107,289; 2=7,038; 3=1,057; 4=145; 5=44; 6=13; 7=6; 9=3. | No nulls. | **Observed V2 values.** Header suggests total left findings, but construction and why both left/right totals occur on every side row are **Unresolved**. |
| `side_level_anon.total_R_find` — `int8`, count-like | Observed `0`–`6`; counts: 0=45,348; 1=106,797; 2=6,669; 3=953; 4=123; 5=42; 6=7. | No nulls. | **Observed V2 values.** Header suggests total right findings; construction/repetition are **Unresolved**. |
| `side_level_anon.path_severity_side_level` — `int8`, coded aggregate | 0=1,293; 1=490; 2=768; 3=55; 4=3,036; 5=69. | 154,228 nulls. | **Observed V2 values.** No legend entry defines codes or aggregation. |
| `side_level_anon.mass_side_level` — `int8`, count-like aggregate | 0=145,603; 1=6,364; 2=416; 3=68; 4=17; 5=1; 6=2; 7=1; 8=1. | 7,466 nulls, exactly coincident with null `side`; no nulls when side is populated. | **Observed V2 values.** Values above 1 conflict with transferring the base “presence” definition. Construction is **Unresolved**. |
| `side_level_anon.asymmetry_side_level` — `int8`, count-like aggregate | 0=140,650; 1=11,070; 2=701; 3=42; 4=9; 5=1. | 7,466 nulls, exactly coincident with null `side`. | **Observed V2 values.** Values above 1 conflict with transferring the base “presence” definition. |
| `side_level_anon.arch_distortion_side_level` — `int8`, count-like aggregate | 0=151,262; 1=1,128; 2=76; 3=5; 4=2. | 7,466 nulls, exactly coincident with null `side`. | **Observed V2 values.** Values above 1 conflict with transferring the base “presence” definition. |
| `side_level_anon.calc_side_level` — `int8`, count-like aggregate | 0=144,557; 1=7,321; 2=519; 3=61; 4=11; 5=2; 6=1; 11=1. | 7,466 nulls, exactly coincident with null `side`. | **Observed V2 values.** Values above 1 conflict with transferring the base “presence” definition. |

## Risk features

The legend contains no risk headers, definitions, units, horizons, or sentinel
codes. Most finite observations exceed 1 and many outputs top out at 100, so a
percentage-point-like scale is strongly suggested, but it remains an
**Inference**, not a released unit definition. Quantiles below are linear
`q01 / q50 / q99`. No risk output contains a nonfinite value.

| Feature and representation | Observed distribution | Missing and sentinel evidence | Evidence and caveats |
| --- | --- | --- | --- |
| `risk_anon.empi_anon` — `int64`, identifier | Unique patient identifier; 17,816 distinct values. | No nulls; repeated across exams. | Meaning: **Release legend.** Cardinality: **Observed V2 values.** Never emit values. |
| `risk_anon.acc_anon` — `int64`, identifier/key | Anonymized exam identifier; 77,499 distinct values in 77,499 rows. | No nulls or duplicates. | Key behavior: **Observed V2 values.** Meaning via legend `acc`/`accession`: **Inference.** |
| `risk_anon.studydate_anon` — `timestamp[ns]`, anonymized date | Exam date; 3,932 distinct values. | No nulls. | Meaning: **Release legend.** Cardinality: **Observed V2 values.** Date shifting/order behavior is **Unresolved**; never emit values. |
| `risk_anon.NCILIFE` — `double`, model output | Range -35–100; q01/q50/q99 = -35/8.5/100. | Null 1,927. `-35` occurs 1,057 times, `-2` 1,673 times, and `100` 9,237 times. | Distribution: **Observed V2 values.** Output definition is **Unresolved**. Negative values are sentinel-like; meanings and whether 100 is a cap, sentinel, or valid value need confirmation. |
| `risk_anon.IBISLIFE` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.244/10.9/100. | Null 21,054; `100` occurs 7,460 times. | **Observed V2 values; Unresolved** definition and 100 semantics. |
| `risk_anon.IBISBRCA1` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.1/0.1/1.9. | Null 17,748; `100` occurs once. | **Observed V2 values.** The field name alone does not establish the modeled outcome or horizon; **Unresolved**. |
| `risk_anon.IBISBRCA2` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.1/0.1/2.1. | Null 17,748; `100` occurs 4 times. | **Observed V2 values; Unresolved** definition and extreme-value semantics. |
| `risk_anon.IBIS10` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.2/3.7/100. | Null 17,748; `100` occurs 8,128 times. | **Observed V2 values.** A ten-year horizon is suggested only by the name; definition and 100 semantics are **Unresolved**. |
| `risk_anon.IBISPOP10` — `double`, model output | Range 0.1–4.0; q01/q50/q99 = 0.1/3.4/4.0. | Null 17,748. | **Observed V2 values.** Population comparator and horizon are suggested only by the name; **Unresolved**. |
| `risk_anon.IBISPOPL` — `double`, model output | Range 0.1–13.4; q01/q50/q99 = 0.1/9.0/13.2. | Null 17,748. | **Observed V2 values.** Definition is **Unresolved**. |
| `risk_anon.NCI5` — `double`, model output | Range -35–100; q01/q50/q99 = -35/1.6/100. | Null 19,323. `-35` occurs 709 times, `-2` 1,673 times, and `100` 6,838 times. | **Observed V2 values.** A five-year horizon is suggested only by the name. Sentinel meanings and 100 semantics are **Unresolved**. |
| `risk_anon.IBIS_TD1` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.2/7.7/100. | Null 21,136; `100` occurs 7,446 times. | **Observed V2 values.** `TD1` meaning is **Unresolved**; do not assume equivalence to tissue-density code 1. |
| `risk_anon.IBIS_TD2` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.2/9.7/100. | Null 21,136; `100` occurs 7,446 times. | **Observed V2 values.** `TD2` meaning is **Unresolved**. |
| `risk_anon.IBIS_TD3` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.3/11.5/100. | Null 21,136; `100` occurs 7,446 times. | **Observed V2 values.** `TD3` meaning is **Unresolved**. |
| `risk_anon.IBIS_TD4` — `double`, model output | Range 0.1–100; q01/q50/q99 = 0.4/15.3/100. | Null 21,136; `100` occurs 7,446 times. | **Observed V2 values.** `TD4` meaning is **Unresolved**. |
| `risk_anon.__index_level_0__` — `int64`, technical index | Preserved unnamed pandas index; 77,499 distinct values. | No nulls. | Index role: **Release schema.** Cardinality: **Observed V2 values.** Exclude from clinical feature sets. |

The registered probe described 13 NCI/IBIS outputs, but the physical schema
contains 12. The apparent thirteenth column is
`risk_anon.__index_level_0__`, which Parquet metadata identifies as the pandas
index. **Release schema.**

## Maintainer questions

1. What are the definitions, units, horizons, and intended uses of the 12 risk
   outputs? What do `-35`, `-2`, and `100` mean for each output, and what do
   `IBIS_TD1`–`IBIS_TD4` vary?
2. How are the exam- and side-level mass, asymmetry, architectural-distortion,
   and calcification fields aggregated? Are they counts, maxima, or another
   summary, and should the base legend's “presence” descriptions apply at all?
3. What do path-severity codes 0–5 mean, and how are
   `path_severity_exam_level` and `path_severity_side_level` derived?
4. What units and zero semantics apply to menopause, pregnancy, and menarche
   ages? Which pregnancy event does `pregnancyage_anon` represent?
5. Does null mean “No” for `proc_flag` and `biopsy_flag`, or does it mean
   missing/not assessed?
6. What does a null `side` row represent, and how should bilateral (`B`) rows
   relate to left/right rows? Are `total_L_find` and `total_R_find` repeated
   exam totals or side-row attributes?
7. Are the `acc`/`accession` and `loc_num` legend entries authoritative aliases
   for `acc_anon` and `loc_num_anon`? Is the location code list exhaustive, and
   is the absence of `LOC004` intentional?
8. Is `exam_level_anon.acc_anon` a complete unique exam key?
9. What anonymized-date properties are preserved within and across patients,
   particularly for birth and study dates?
10. What precisely does `version` encode when version-1 and version-2 rows
    coexist in this release?

[Back to the bundle entry point](README.md).
