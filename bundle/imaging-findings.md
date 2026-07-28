# Imaging-finding features

[Back to the bundle entry point](README.md)

This page describes every physical column in the `imaging_findings_anon`
Parquet table.
It preserves the released spelling and case of each name, including
`imaging_findings_anon.modifers`, `imaging_findings_anon.USFinding`,
`imaging_findings_anon.MBPE_SYM`, and `imaging_findings_anon.mdelayed.1`.

Evidence tags qualify individual claims:

- **Schema** — release Parquet schema.
- **Legend** — released V2 clinical legend.
- **Observed Q007/Q008** — projected, aggregate-only V2 value checks.
- **Cross-table Q009** — projected key-only or anti-join check.
- **Inference** — plausible interpretation not established by release evidence.
- **Unresolved** — the available evidence is insufficient or conflicts.

Null counts below use the 171,378 released imaging-finding rows. A zero in a
numeric field is an observed value, not automatically a clinical zero. No
whole-field blank or whitespace-only strings occurred in the 47 categorical
columns inspected by Q007. Some fields contain comma-bearing strings. Q007 used
a provisional comma split only to compare nonempty pieces with legend codes;
delimiter, ordering, and composition semantics remain unverified. Preserve the
raw value and label token-level interpretation as inference.

## Grain, identity, and links

`imaging_findings_anon` is intended to describe imaging findings, but the
candidate key `(acc_anon, side, numfind)` is neither complete nor unique.
There are 158,566 rows with all three components present, 158,497 distinct
complete tuples, 69 duplicate tuples, and 12,812 rows missing at least one
component. Therefore, do not use that tuple as a primary key without an
explicit duplicate and sentinel policy. **Cross-table Q009**

The exam table's accession is complete and unique, but four distinct non-null
linked accessions in four imaging rows do not resolve to it. Treat linked-study
navigation as a mostly resolving, non-total relationship, not a foreign-key
constraint. **Cross-table Q009**

| Physical column | Representation | Meaning and observed state | Evidence and caveats |
| --- | --- | --- | --- |
| `imaging_findings_anon.acc_anon` | Optional `int64`; identifier | Anonymized accession identifier by name. It has 0 nulls and 131,052 distinct values across 171,378 rows. | **Schema; Cross-table Q009; Inference.** No exact legend header. Repetition is expected at finding grain; no imaging-to-exam anti-join was registered for this field. |
| `imaging_findings_anon.linkedaccession_anon` | Optional `int64`; identifier/reference | An anonymized accession reference for a linked study by name. It has 149,964 nulls, 21,414 non-null rows, and 16,171 distinct non-null values. Of those, 16,167 distinct values resolve to the exam table and 4 do not. | **Schema; Cross-table Q009; Inference.** No exact legend header. A non-null value is not guaranteed to resolve. |
| `imaging_findings_anon.linked_study_flag` | Optional string; binary code | Flag identifying a linked exam. Observed `N` 149,892 and `Y` 21,486; 0 nulls. | **Schema; Legend; Observed Q007.** The legend supplies no code meanings; N/Y interpretation is **Inference**. There are 72 more Y flags than non-null linked-accession rows, and no row-wise alignment check was registered, so this is not a proven presence indicator. |
| `imaging_findings_anon.side` | Optional string; nominal code | Breast side: `L` left, `R` right, `B` both. Observed `B` 71,945, `L` 45,540, `R` 44,669; 9,224 nulls. | **Schema; Legend; Observed Q007.** This is part of the non-unique candidate key. |
| `imaging_findings_anon.numfind` | Optional `int8`; finding-number/key component | Legend label: “Finding Number.” It has 12,810 nulls; finite range -9 to 9. Of 158,568 non-null values, 21,407 are negative, 1 is zero, and 137,160 are positive. Quantiles p1/p25/p50/p75/p95/p99 are -9/1/1/1/2/3. | **Schema; Legend; Observed Q008. Unresolved:** negative values, especially -9, behave like possible sentinels but no meaning is documented. Do not assume all values are ordinal finding numbers. |
| `imaging_findings_anon.__index_level_0__` | Optional `int64`; serialized pandas index | Parquet pandas metadata declares this field as an index and footer metadata reports no nulls. Q013 found 171,378 distinct imaging index values and verified every indexed imaging projection occurs in `combined_anon`. | **Schema; Cross-table Q013.** Treat the export index as non-clinical and not as a portable natural key. Equality with current imaging row position was not tested. |

## Shared assessment, location, and state

| Physical column | Representation | Meaning and observed state | Evidence and caveats |
| --- | --- | --- | --- |
| `imaging_findings_anon.asses` | Optional string; nominal code | BI-RADS assessment: `N` negative, `B` benign, `P` probably benign, `A` additional evaluation, `S` suspicious, `M` highly suggestive of malignancy, `K` known biopsy-proven malignancy, `X` no assessment. All eight codes occur; 12,810 nulls. | **Schema; Legend; Observed Q007.** Do not impose an ordinal scale across `A`, `K`, or `X`. |
| `imaging_findings_anon.location` | Optional string; comma-bearing nominal code | Serialized clock/quadrant/location values; 117,742 nulls and 273 distinct forms. Every nonempty piece from the provisional comma split is legend-listed. | **Schema; Legend; Observed Q007; Inference for splitting.** Some values have a trailing delimiter. Preserve the raw string; see the candidate atomic vocabulary below. |
| `imaging_findings_anon.depth` | Optional string; nominal code | Depth: `A` anterior, `M` middle, `P` posterior; grid codes `1`=1A, `2`=1B, `3`=1C, `4`=2A, `5`=2B, `6`=2C, `7`=3A, `8`=3B, `9`=3C. Observed: `2` 6, `5` 4, `6` 2, `8` 8, `9` 2, `A` 3,636, `M` 8,865, `P` 10,628; 148,227 nulls. | **Schema; Legend; Observed Q007.** Letter and grid representations coexist. |
| `imaging_findings_anon.stable` | Optional `int8`; binary flag | Whether the finding is stable. Observed `0` 123,081 and `1` 14,080; 34,217 nulls. | **Schema; Legend; Observed Q007.** The legend gives no explicit 0/1 mapping; boolean interpretation is **Inference**. |
| `imaging_findings_anon.new` | Optional `int8`; binary flag | Whether the finding is new. Observed `0` 134,922 and `1` 2,239; 34,217 nulls. | **Schema; Legend; Observed Q007.** The legend gives no explicit 0/1 mapping; boolean interpretation is **Inference**. |
| `imaging_findings_anon.changed` | Optional string; comma-bearing nominal code | Change codes; 149,231 nulls and 27 serialized forms. Every piece from the provisional comma split is legend-listed. | **Schema; Legend; Observed Q007; Inference for splitting.** Preserve the raw string; candidate atomic meanings appear below. |
| `imaging_findings_anon.secondaryfindings` | Optional string; comma-bearing nominal code | Ultrasound secondary findings; 171,349 nulls and 7 serialized forms using apparent pieces `D,E,L,M,S`. | **Schema; Legend; Observed Q007; Inference for splitting.** `I` and `P` exist in the legend but were not observed. Preserve the raw string. |
| `imaging_findings_anon.addendum_flag` | Optional string; binary/one-sided code | Flag identifying an addended exam. Only `Y` was observed: 4,159 rows; 167,219 nulls. | **Schema; Legend; Observed Q007.** The legend supplies no code meanings. Null is not proven equivalent to “no.” |
| `imaging_findings_anon.recc` | Optional string; comma-bearing recommendation code | Recommendation codes; 35,632 nulls and 229 serialized forms. Most apparent pieces are legend-listed. | **Schema; Legend; Observed Q007; Inference for splitting.** Non-legend pieces under the provisional split are `?` in 2 rows, `G` 32, `MC` 588, `MS` 5, and `MT` 59. Do not silently map them. Recommendations may encode follow-up or intervention after assessment and require a temporal-leakage policy for prediction use. |

### Shared vocabularies

The vocabularies below are legend-defined atomic codes. Applying one to a
piece of a comma-bearing string is a provisional parsing inference, not a
release-documented decoding rule.

`imaging_findings_anon.location` uses `1`–`12` for the corresponding clock
positions; `W` upper outer, `X` upper inner, `Y` lower outer, `Z` lower inner,
`C` central, `D` medial, `I` inferior, `L` lateral, `S` sub-areolar, `U`
superior, `T` or `A` axillary tail, `MD` middle, `AN` anterior, `UP` upper,
`LO` lower, `IN` inner, and `OU` outer. **Legend**

`imaging_findings_anon.changed` uses `+` increase in size, `-` decrease in
size, `C` coarser calcifications consistent with a benign process, `D`
decrease in calcification count, `G` finding does not persist on additional
diagnostic evaluation, `I` increase in calcification count, `M` more
prominent, `N` no significant change, `O` more defined, `P` partially removed,
`R` completely removed without recurrence, `S` not seen, `U` less prominent,
and `X` less defined. **Legend**

`imaging_findings_anon.secondaryfindings` uses `D` distortion of surrounding
parenchyma, `E` edema, `I` infiltration of subcutaneous fat, `L` abnormal
appearing axillary nodes, `M` marked skin thickening, `P` apparent pectoral
muscle involvement, and `S` skin thickening. **Legend**

`imaging_findings_anon.recc` uses:

| Codes | Legend meanings |
| --- | --- |
| `1`; `&`; `>` | 1-year follow-up; not specified; return to screening |
| `A`; `AS`; `B`; `FN` | Cyst aspiration; aspiration; biopsy; fine-needle aspiration |
| `BF`; `F`; `FL`; `FR` | Bilateral, bilateral short-term, left short-term, or right short-term follow-up |
| `BM`; `BU`; `GB`; `GL`; `GR` | Bilateral mammogram; bilateral ultrasound; bilateral, left, or right diagnostic mammogram |
| `C`; `CM`; `CMR`; `D`; `E` | Clinical correlation; clinical management; clinical management with recall; biopsy decision based on clinical assessment; biopsy based on clinical assessment |
| `HRR`; `MR`; `MR6`; `MRA`; `MRB`; `MRC`; `MRI`; `MRN` | High-risk screening MRI; breast MRI; six-month MRI follow-up; MRI abnormal; MR-guided biopsy; consider routine after MRI; immediate MRI follow-up; MRI strongly recommended |
| `ICU`; `IFM`; `T` | Independent clinical follow-up; independent clinical follow-up; appropriate action |
| `L`; `SB`; `SE`; `UB`; `Y`; `Z` | Needle localization/excision; stereotactic biopsy; surgical excision; ultrasound biopsy; cytologic analysis; biopsy already performed |
| `M`; `P`; `PU`; `S`; `TM`; `TR`; `U` | Magnification mammography; additional projections; possible ultrasound after mammography; spot compression; tomosynthesis views; technical repeat; ultrasound exam |
| `N`; `RL`; `RR`; `UM`; `UU` | Bilateral, left, right, or unilateral mammogram; unilateral ultrasound |
| `O`; `OF`; `USC` | Old films for comparison; outside films/additional evaluation; negative outside films |

The table above is the legend vocabulary, not an exhaustive list of observed
serialized combinations. **Legend; Observed Q007**

## Mammography features

| Physical column | Representation | Meaning and observed state | Evidence and caveats |
| --- | --- | --- | --- |
| `imaging_findings_anon.mass` | Optional `int8`; binary flag | Presence of mass. Observed `0` 164,101 and `1` 7,277; 0 nulls. | **Schema; Legend; Observed Q007.** The legend describes the flag but does not define 0/1 explicitly. |
| `imaging_findings_anon.asymmetry` | Optional `int8`; binary flag | Presence of asymmetry. Observed `0` 158,942 and `1` 12,436; 0 nulls. | **Schema; Legend; Observed Q007.** Explicit 0/1 meanings are **Inference**. |
| `imaging_findings_anon.arch_distortion` | Optional `int8`; binary flag | Presence of architectural distortion. Observed `0` 170,157 and `1` 1,221; 0 nulls. | **Schema; Legend; Observed Q007.** Explicit 0/1 meanings are **Inference**. |
| `imaging_findings_anon.calc` | Optional `int8`; binary flag | Presence of calcification. Observed `0` 163,133 and `1` 8,245; 0 nulls. | **Schema; Legend; Observed Q007.** Explicit 0/1 meanings are **Inference**. |
| `imaging_findings_anon.massshape` | Optional string; nominal code | Mammographic mass shape; 151,208 nulls and 17 observed codes. | **Schema; Legend; Observed Q007.** Non-legend codes are `9` 1, `D` 1, `L` 60, and `M` 1. |
| `imaging_findings_anon.massmargin` | Optional string; nominal code | `D` circumscribed, `U` obscured, `M` microlobulated, `I` indistinct, `S` spiculated. Observed counts 2,715/688/43/448/232 respectively; 167,252 nulls. | **Schema; Legend; Observed Q007.** Exact domain agreement. |
| `imaging_findings_anon.massdens` | Optional string; nominal code | Mass density: `+` high, `=` isodense, `-` low, `0` fat-containing. Observed 332/2,043/346/261 respectively; 168,396 nulls. | **Schema; Legend; Observed Q007.** Exact domain agreement. |
| `imaging_findings_anon.calcfind` | Optional string; comma-bearing nominal code | Calcification morphology/finding; 163,136 nulls and 166 serialized forms. | **Schema; Legend; Observed Q007; Inference for splitting.** Every piece from the provisional split is legend-listed except `N`, occurring alone in 8 rows. Preserve the raw string. |
| `imaging_findings_anon.calcdistri` | Optional string; nominal code | Distribution: `G` grouped, `S` segmental, `R` regional, `D` diffuse/scattered, `L` linear, `C` clustered. Observed `G` 2,313, `S` 136, `R` 280, `D` 522, `L` 164, `C` 506; 167,457 nulls. | **Schema; Legend; Observed Q007.** Exact domain agreement. |
| `imaging_findings_anon.calcnumber` | Optional string; numeric-looking categorical value | Legend label: number of calcifications. Observed values are `-6.0` 16, `-5.0` 54, `-3.0` 48, `-2.0` 15, `0.0` 121,449, `1.0` 18, `2.0` 6, `3.0` 12, `4.0` 6, `5.0` 2, `6.0` 1, `7.0` 1; 49,750 nulls. | **Schema; Legend; Observed Q007. Unresolved:** physical type is string and negative-value meanings are undocumented. Do not coerce without a sentinel policy. |
| `imaging_findings_anon.otherfind` | Optional string; comma-bearing nominal code | Other mammographic finding; 158,244 nulls and 77 serialized forms. Every piece from the provisional split is legend-listed. | **Schema; Legend; Observed Q007; Inference for splitting.** Preserve the raw string. |
| `imaging_findings_anon.implanfind` | Optional string; comma-bearing nominal code | Implant finding; 171,258 nulls and 11 serialized forms. Every piece from the provisional split is legend-listed. | **Schema; Legend; Observed Q007; Inference for splitting.** Preserve the raw string. |
| `imaging_findings_anon.consistent` | Optional string; comma-bearing nominal code | “Consistent with” interpretation; 170,142 nulls and 25 serialized forms. | **Schema; Legend; Observed Q007; Inference for splitting.** Apparent non-legend piece `B` occurs in 838 rows; do not equate it with legend code `N` (“benign asymmetry”). |
| `imaging_findings_anon.size` | Optional `int16`; numeric measurement | Finding size in millimetres. It has 34,217 nulls; finite range -99 to 83. Negative 1,107, zero 131,460, positive 4,594; p95 0 and p99 11. | **Schema; Legend; Observed Q008. Unresolved:** -99 and other negatives are undocumented probable sentinels; zero may also encode absence/not measured. |
| `imaging_findings_anon.distance` | Optional `int16`; numeric measurement | Distance in centimetres. It has 34,217 nulls; finite range -2 to 54. Negative 78, zero 123,736, positive 13,347; p95 5 and p99 10. | **Schema; Legend; Observed Q008. Unresolved:** negative and zero semantics are not documented. |

### Mammography vocabularies

`imaging_findings_anon.massshape` legend codes are `G` generic, `R` round, `O`
oval, `X` irregular, `Q` questioned architectural distortion, `A`
architectural distortion, `T` asymmetric tubular structure/solitary dilated
duct, `N` intramammary lymph node, `B` global asymmetry, `F` focal asymmetry,
`S` asymmetry, `V` developing asymmetry, and `Y` lymph node. **Legend**

`imaging_findings_anon.calcfind` legend codes are `A` amorphous, `9` benign,
`H` coarse heterogeneous, `C` coarse/popcorn-like, `D` dystrophic, `E` rim,
`F` fine-linear, `B` fine linear-branching, `G` generic, `I` fine pleomorphic,
`L` large rod-like, `M` milk of calcium, `J` oil cyst, `K` pleomorphic, `P`
punctate, `R` round, `S` skin, `O` lucent-centered, `U` suture, `V` vascular,
and `Q` coarse. **Legend**

`imaging_findings_anon.otherfind` legend codes are:

| Codes | Legend meanings |
| --- | --- |
| `!`; `%`; `1`; `3`; `C`; `P`; `U`; `X` | Post-mastectomy flap change; calcified oil cyst; post-lumpectomy/radiation change; reduction mammoplasty change; post-reduction change; post-surgical change; post-lumpectomy change; post-mastectomy/implant change |
| `2`; `V`; `Z`; `A` | Prominent lymph node; normal lymph nodes; abnormal lymph nodes; axillary adenopathy |
| `4`; `5`; `I`; `Q`; `Y` | Asymmetry; density on MLO projection; focal asymmetry on CC projection; focal asymmetry; asymmetric breast tissue |
| `B`; `F`; `K`; `M`; `W` | Prior needle biopsy clip; prior stereotactic biopsy clip; prior ultrasound biopsy clip; prior MRI biopsy clips; biopsy clip |
| `D`; `E`; `O` | Architectural distortion; duct ectasia; dilated duct |
| `G`; `N` | Gynecomastia-consistent subareolar density; nipple retraction |
| `H`; `J`; `L`; `R`; `S`; `T` | Hematoma; diffuse skin thickening; skin lesion; skin retraction; skin thickening; trabecular thickening |

`imaging_findings_anon.implanfind` legend codes are `A` asymmetric, `N` normal
implants, `C` calcified, `D` distorted, `F` fibrosed, `H` herniated, `R`
ruptured, `S` free silicone, `T` capsular contraction, and `K` capsular
calcification. **Legend**

`imaging_findings_anon.consistent` legend codes are:

| Codes | Legend meanings |
| --- | --- |
| `A`; `ABT`; `AE`; `N` | Abscess; accessory breast tissue; augmentation then explantation; benign asymmetry |
| `CF`; `F`; `DFA`; `FV`; `I` | Calcified fibroadenoma; fibroadenoma; degenerating fibroadenoma; fibroadenoma or variant; hyalinized fibroadenoma |
| `C`; `D`; `SA`; `J` | Cyst; fibrocystic change; fibrocystic change or sclerosing adenosis; fibrosis |
| `DF`; `DE`; `G`; `T` | Diabetic fibrous mastopathy; ectatic duct; fat lobules; fat necrosis |
| `FB`; `FS`; `E`; `H` | Foreign body; free silicone; hematoma; hamartoma |
| `LA`; `L`; `Y`; `MG`; `M`; `O` | Lactating adenoma; lipoma; lymph node; male gynecomastia; milk of calcium; oil cyst |
| `PT`; `PM`; `>`; `PR`; `SP`; `S` | Phyllodes tumor; plasma-cell mastitis; postsurgical fluid collection; prior reduction mammoplasty; sclerotic papilloma; seroma |

## Ultrasound features

| Physical column | Representation | Meaning and observed state | Evidence and caveats |
| --- | --- | --- | --- |
| `imaging_findings_anon.USFinding` | Optional string; comma-bearing nominal code | Ultrasound finding; 147,210 nulls and 57 serialized forms. Every piece from the provisional split is legend-listed. | **Schema; Legend; Observed Q007; Inference for splitting.** Preserve the raw string. |
| `imaging_findings_anon.shape` | Optional string; comma-bearing nominal code | `I` irregular, `O` oval, `R` round. Observed `I` 2,244, `O` 6,680, `R` 425, `R,O` 2; 162,027 nulls. | **Schema; Legend; Observed Q007.** `R,O` shows a comma-bearing form, but composition semantics remain unverified. |
| `imaging_findings_anon.orientation` | Optional string; nominal code | `E` parallel, `T` taller-than-wide. Observed 4,787 and 825; 165,766 nulls. | **Schema; Legend; Observed Q007.** |
| `imaging_findings_anon.margins` | Optional string; comma-bearing nominal code | Ultrasound margin codes; 163,976 nulls and 22 serialized forms using apparent pieces `A,C,I,M,N,P,R,S`. | **Schema; Legend; Observed Q007; Inference for splitting.** Preserve the raw string. |
| `imaging_findings_anon.modifers` | Optional string; nominal code | Released misspelling of modifiers: `E` heterogeneous, `H` echogenic halo, `O` homogeneous. Observed 334/80/595; 170,369 nulls. | **Schema; Legend; Observed Q007.** Preserve the physical misspelling in references. |
| `imaging_findings_anon.echotexture` | Optional string; comma-bearing nominal code | `A` anechoic, `I` isoechoic, `M` mixed hyperechoic/hypoechoic, `P` hypoechoic, `R` hyperechoic. There are 164,270 nulls and 13 serialized forms. | **Schema; Legend; Observed Q007; Inference for splitting.** |
| `imaging_findings_anon.posteriorfeatures` | Optional string; comma-bearing nominal code | Posterior features; 169,644 nulls and 8 serialized forms using apparent pieces `C,E,G,N,P,T`. | **Schema; Legend; Observed Q007; Inference for splitting.** |
| `imaging_findings_anon.vascularity` | Optional string; comma-bearing nominal code | Vascularity; 168,687 nulls and 6 serialized forms using apparent pieces `A,H,L,M,R`. | **Schema; Legend; Observed Q007; Inference for splitting.** |
| `imaging_findings_anon.surroundingtissue` | Optional string; comma-bearing nominal code | Surrounding tissue; 170,731 nulls and 6 serialized forms using apparent pieces `D,E,F,U`. | **Schema; Legend; Observed Q007; Inference for splitting.** |

### Ultrasound vocabularies

`imaging_findings_anon.USFinding` uses `#` free silicone, `&` intraductal
calcifications, `/` axillary adenopathy, `1` fat lobule, `4` fat necrosis, `5`
lobular mass, `9` seroma, `A` no abnormality, `B` sebaceous cyst, `C` simple
cyst, `D` duct ectasia, `E` probable epidermal-inclusion/sebaceous cyst, `F`
fluid collection, `G` dense tissue without lesion, `H` hematoma, `I`
intracystic lesion, `J` abscess, `K` skin lesion, `L` abnormal lymph node, `M`
intraductal mass, `N` not seen on ultrasound, `P` postsurgical change, `Q`
edematous change of unknown etiology, `R` normal lymph node, `S` solid mass,
`T` asymmetric tissue, `U` cluster of cysts, `V` complicated cyst versus solid
mass, `W` edematous change consistent with mastitis, `X` complex cystic and
solid mass, `Y` complicated cyst, and `Z` normal-appearing tissue. **Legend**

`imaging_findings_anon.margins` uses `A` angular, `C` circumscribed, `I`
indistinct, `M` microlobulated, `N` well-defined, `P` poorly defined, `R`
partially defined, and `S` spiculated. **Legend**

`imaging_findings_anon.posteriorfeatures` uses `C` central shadowing, `E`
posterior enhancement, `G` enhancement with edge shadowing, `N` no posterior
effect, `P` posterior shadowing, and `T` eccentric shadowing.
`imaging_findings_anon.vascularity` uses `A` avascular, `H` hypervascular, `L`
mildly vascular, `M` markedly hypervascular, and `R` rim vascularity.
`imaging_findings_anon.surroundingtissue` uses `D` distorted, `E` edematous,
`F` diffusely altered echogenicity, and `U` unaffected. **Legend**

## MRI features

The legend headers for most MRI fields are uppercase while the physical fields
are lowercase. These are case-only candidates, not exact header matches.

| Physical column | Representation | Meaning and observed state | Evidence and caveats |
| --- | --- | --- | --- |
| `imaging_findings_anon.mfocus` | Optional string; nominal code | `F` focus of enhancement, `I` multiple enhancing foci. Observed 144/52; 171,182 nulls. | **Schema; Legend case-only match; Observed Q007.** |
| `imaging_findings_anon.mshape` | Optional string; nominal code | `I` irregular, `L` lobulated, `O` oval, `R` round MRI mass. Observed 343/11/319/68; 170,637 nulls. | **Schema; Legend case-only match; Observed Q007.** |
| `imaging_findings_anon.mmargin` | Optional string; nominal code | `I` irregular, `M` circumscribed, `S` spiculated margin. Observed 174/212/64; 170,928 nulls. | **Schema; Legend case-only match; Observed Q007.** |
| `imaging_findings_anon.menhance` | Optional string; nominal code | Internal enhancement: `C` central, `D` non-enhancing septations, `E` enhancing septations, `M` homogeneous, `R` rim, `T` heterogeneous. Observed `D` 5, `M` 160, `R` 39, `T` 193; 170,981 nulls. | **Schema; Legend case-only match; Observed Q007.** Observed domain is a legend subset. |
| `imaging_findings_anon.mdist` | Optional string; nominal code | Distribution: `D` ductal, `F` focal area, `I` diffuse, `L` linear, `R` regional, `S` segmental. Observed `F` 226, `I` 10, `L` 112, `R` 52, `S` 68, plus non-legend `M` 1; 170,909 nulls. | **Schema; Legend case-only match; Observed Q007.** `M` is unresolved. |
| `imaging_findings_anon.mpattern` | Optional string; nominal code | `C` clumped, `M` homogeneous, `Q` clustered ring, `R` reticular, `S` stippled, `T` heterogeneous. Observed 87/29/2/2/1/59; 171,198 nulls. | **Schema; Legend case-only match; Observed Q007.** |
| `imaging_findings_anon.msym` | Optional string; nominal code | `A` asymmetric, `S` symmetric. Only `A` occurred, 10 rows; 171,368 nulls. | **Schema; Legend case-only match; Observed Q007.** |
| `imaging_findings_anon.massoc` | Optional string; comma-bearing nominal code | Associated MRI finding; 171,222 nulls and 20 serialized forms. Every piece from the provisional split is legend-listed. | **Schema; Legend case-only match; Observed Q007; Inference for splitting.** Preserve the raw string. |
| `imaging_findings_anon.mother` | Optional string; comma-bearing nominal code | No legend header. A provisional split finds pieces `B,C,G,H,I,L,M,N,O,P,R,Y` across 14 serialized forms; 170,438 nulls. | **Schema; Observed Q007; Unresolved.** Do not borrow meanings from another field solely because pieces overlap. |
| `imaging_findings_anon.minitial` | Optional string; nominal code | Initial enhancement: `M` medium, `R` fast, `S` slow. Observed 16/112/6; 171,244 nulls. | **Schema; Legend case-only match; Observed Q007.** |
| `imaging_findings_anon.mdelayed` | Optional string; nominal code | Delayed kinetics: `L` plateau, `P` persistent, `S` minimal washout, `W` washout. Observed 32/44/24/72; 171,206 nulls. | **Schema; Legend case-only match; Observed Q007.** |
| `imaging_findings_anon.mdelayed.1` | Optional string; nominal code | No exact or case-only legend header. Observed `L` 32, `P` 44, `S` 24, `W` 71; 171,207 nulls. | **Schema; Observed Q007; Unresolved.** Its aggregate distribution is nearly identical to `imaging_findings_anon.mdelayed`, but derivation or equivalence is not established. |
| `imaging_findings_anon.msize` | Optional `int8`; numeric-looking field | No legend header. All 121,628 non-null values are zero; 49,750 nulls. | **Schema; Observed Q008; Unresolved.** The name suggests MRI size, but neither meaning nor units are confirmed and the released column carries no positive measurement. |
| `imaging_findings_anon.mbpe_level` | Optional string; nominal code | Background parenchymal enhancement level: `A` marked, `I` mild, `M` minimal, `O` moderate. Observed 9/107/117/59; 171,086 nulls. | **Schema; Legend; Observed Q007.** Letter order is not an ordinal encoding. |
| `imaging_findings_anon.MBPE_SYM` | Optional string; nominal code | Background parenchymal enhancement symmetry: `A` asymmetrical, `S` symmetrical. Observed 28/175; 171,175 nulls. | **Schema; Legend case-only `mbpe_sym`; Observed Q007.** |

### MRI associated-finding vocabulary

`imaging_findings_anon.massoc` uses `#` fat necrosis, `A` architectural
distortion, `B` abnormal lymph node, `C` chest-wall invasion, `E` edema, `F`
fluid-filled dilated duct, `G` high ductal signal on pre-contrast scan, `H`
hematoma, `I` nipple retraction, `K` direct skin invasion, `L` axillary
adenopathy, `M` hamartoma, `N` nipple retraction, `O` postoperative changes,
`P` pectoralis invasion, `S` skin retraction, `T` skin thickening, `V`
abnormal signal void, `W` normal lymph node, `Y` cyst, and `Z` inflammatory
breast-cancer invasion. The legend assigns both `I` and `N` to nipple
retraction. **Legend**

## Interpretation constraints

- Missingness is field-specific. Null, zero, negative values, “no assessment,”
  and “not seen” are distinct representations and must not be collapsed.
- `size`, `distance`, `numfind`, `calcnumber`, and `msize` need explicit
  sentinel handling before numeric analysis. Only `size` and `distance` have
  legend units.
- Preserve comma-bearing fields as raw strings. A provisional split can flag
  apparent pieces absent from a field-specific vocabulary, but it is an
  inference and must not be presented as a documented decoding rule.
- Assessment, recommendation, linked-study, addendum, stability, change, and
  “consistent with” fields may reflect different points in the clinical
  timeline. The release evidence does not establish a prediction-time cutoff.
- Physical similarity between `mdelayed` and `mdelayed.1`, or token overlap
  between `mother` and other fields, is not proof of equivalence.

The aggregate probes and access limits underlying this page are recorded in
the source repository's maintainer investigation results. This bundle remains
standalone and does not depend on that work log for interpretation.
