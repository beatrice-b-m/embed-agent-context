# Pathology vocabularies

[Bundle entry point](README.md) ·
[Pathology, reports, and the wide table](pathology-reports-and-wide-table.md)

This appendix transcribes the released legend's complete code-to-meaning maps
for the coded pathology fields. The wording, capitalization, and apparent
misspellings in the meanings are retained from the legend after trimming
surrounding whitespace. These are **Release legend** claims: they are not
maintainer-confirmed definitions, are not guaranteed to be exhaustive, and do
not assign a meaning to null.

## Header evidence and interpretation boundary

| Legend header | Physical pathology column(s) | Mapping evidence |
| --- | --- | --- |
| `type` | `type` | Exact header match |
| `technique` | `technique` | Exact header match |
| `bside` | `bside` | Exact header match |
| `bcomp` | `bcomp` | Exact header match |
| `surgery` | `surgery` | Exact header match |
| `lymphsurg` | `lymphsurg` | Exact header match |
| `loc` | `loc` | Exact header match |
| `bdepth` | `bdepth` | Exact header match |
| `path (1-10)` | `path1` through `path10` | Derived shared-header match; there is no exact legend header for an individual physical slot |

The exact mappings above establish which legend rows apply to a same-named
physical column; they do not establish that a list is closed. The derived
`path (1-10)` mapping is only a candidate shared dictionary for all ten slots,
not evidence that the slots are interchangeable or ordered in a particular
way.

Existing aggregate investigation results report 131 distinct observed codes
across `path1` through `path9`; `path10` is entirely null. Of the 182
legend-listed `path (1-10)` codes, 115 are observed and 67 are unobserved.
Sixteen additional observed codes are not listed:

`AC`, `ACG`, `ADT`, `CCA`, `FAT`, `FMC`, `HF`, `IVC`, `LNR`, `LPI`, `MCA`,
`MCI`, `MF`, `MLL`, `PAC`, and `PAP`.

Do not silently assign meanings to those 16 codes. The disagreement is direct
evidence that the shared legend list is not a guaranteed exhaustive V2
contract. Null semantics are undocumented for every vocabulary on this page.
For `loc`, the legend defines atoms, while observed values include
comma-delimited compositions and trailing empty components; delimiter,
ordering, repetition, and trailing-component semantics are unresolved. For
`path1`–`path10`, slot order, code repetition across slots, and whether later
slots denote secondary findings are also unresolved.

## Biopsy and procedure maps

### `type`

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `B` | Needle biopsy pathology | `S` | Surgical pathology |

### `technique`

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `CA` | Cyst aspiration | `CB` | Core biopsy |
| `EB` | Excisional biopsy | `FNA` | FNA |
| `MA` | Mammographic non-stereotactic cyst aspiration | `MR` | MRI guided biopsy |
| `MRX` | MRI guided core biopsy | `SA` | Stereotactic guided cyst aspiration |
| `SB` | Stereotactic core biopsy | `TB` | Tomo guided biopsy |
| `UA` | Ultrasound guided cyst aspiration | `UB` | Ultrasound guided core biopsy |

### `bside`

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `L` | Left | `R` | Right |
| `B` | Both |  |  |

### `bcomp`

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `H` | Hematoma requiring surgery | `I` | Infection requiring antibiotics |
| `L` | Lymphoedema | `N` | Numbness |
| `P` | Pain | `X` | Pneumothorax |

### `surgery`

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `A` | Axillary dissection | `BM` | Subcutaneous Mastectomy |
| `E` | Excisional Breast Biopsy | `I` | Incisional Breast Biopsy |
| `IR` | Implant Replacement | `L` | Lumpectomy |
| `M` | Mastectomy-all types | `MRM` | Modified Radical Mastectomy |
| `O` | Other | `Q` | Quadrantectomy |
| `RE` | Re-excision | `RM` | Radical Mastectomy |
| `SE` | Surgical Excision | `SM` | Simple Mastectomy |

### `lymphsurg`

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `AN` | Axillary Lymph Node Dissection | `HAN` | High Axillary Lymph Node Dissection |
| `IMN` | Internal Mammary Lymph Node Dissection | `LAN` | Low Axillary Lymph Node Dissection |
| `NS` | Lymph Nodes Not Sampled | `O` | Other |
| `S` | Sentinel node biopsy |  |  |

## Location maps

### `loc`

These are legend-listed location atoms, not a documented parser for composite
physical values.

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `1` | 1 o'clock | `2` | 2 o'clock |
| `3` | 3 o'clock | `4` | 4 o'clock |
| `5` | 5 o'clock | `6` | 6 o'clock |
| `7` | 7 o'clock | `8` | 8 o'clock |
| `9` | 9 o'clock | `10` | 10 o'clock |
| `11` | 11 o'clock | `12` | 12 o'clock |
| `W` | Upper outer | `X` | Upper inner |
| `Y` | Lower outer | `Z` | Lower inner |
| `C` | Central | `D` | Medial |
| `I` | Inferior | `L` | Lateral |
| `S` | Sub-areolar | `U` | Superior |
| `T` | Axillary Tail | `A` | Axillary Tail |
| `MD` | Middle | `AN` | Anterior |
| `UP` | Upper | `LO` | Lower |
| `IN` | Inner | `OU` | Outer |

### `bdepth`

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `A` | Anterior | `M` | Middle |
| `P` | Posterior | `1` | 1A |
| `2` | 1B | `3` | 1C |
| `4` | 2A | `5` | 2B |
| `6` | 2C | `7` | 3A |
| `8` | 3B | `9` | 3C |

## Shared `path (1-10)` map

The following table contains all 182 unique code rows under the legend's
shared `path (1-10)` header. It must be used with the derived-mapping and
coverage caveats above.

| Code | Meaning | Code | Meaning |
| --- | --- | --- | --- |
| `AB` | Abscess | `AD` | Adenosis |
| `ADC` | Adenoid cystic carcinoma | `ADE` | Adenocarcinoma |
| `ADH` | Atypical ductal hyperplasia | `ADM` | Adenoma |
| `AL` | Adenolipoma | `ALH` | Atypical lobular hyperplasia |
| `AM` | Apocrine metaplasia | `AME` | Adenomyoepithelloma |
| `AMY` | Amyloid (tumor) | `AN` | Normal axillary node |
| `ANA` | Angiolipoma | `ANC` | Axillary node with calcifications |
| `ANG` | Angiomatosis | `ANH` | Axillary node hyperplasia |
| `ANL` | Axillary node with lymphoma | `ANM` | Axillary nodal metastases |
| `AP` | Apocrine carcinoma | `APA` | Atypical papilloma |
| `APC` | Apocrine cyst | `APH` | Atypical Lymphoid Hyperplasia |
| `AS` | Angiosarcoma | `ASI` | Asynchronous involution |
| `B` | Breast Cancer | `BBP` | Benign breast tissue |
| `BC` | Benign cyst | `BCB` | Benign cyst with blood |
| `BCL` | Benign calcifications | `BCN` | Basal cell carcinoma of the nipple |
| `BEN` | Benign | `BP` | Breast parenchyma |
| `BVI` | Blood vessel (vascular) Invasion | `BXC` | Biopsy site changes |
| `CC` | Colloid (mucinous) carcinoma | `CCC` | Columnar cell change |
| `CCH` | Carcinoma in children | `CDS` | Chondrosarcoma |
| `CEB` | Carcinoma in ectopic breast | `CED` | Carcinoma with endocrine differentiation |
| `CH` | Chondroma | `CI` | Comedocarcinoma (intraductal) |
| `CL` | Calcified lymph node | `CM` | Carcinoma in males |
| `CMT` | Carcinoma with metaplasia | `COT` | Cartilaginous and osseous change |
| `CP` | Intracystic papilloma | `CPL` | Carcinoma in pregnancy and lactation |
| `CS` | Carcinosarcoma | `CSL` | Complex sclerosing lesion |
| `DA` | Ductal adenoma | `DC` | DCIS |
| `DCC` | DCIS with comedonecrosis | `DCH` | DCIS, high grade |
| `DCL` | DCIS, low grade | `DE` | Ductal ectasia |
| `DF` | Diabetic fibrous mastopathy | `DHU` | Ductal hyperplasia, Usual |
| `DMP` | DCIS micro-papillary | `DS` | Ductal carcinoma in-situ (DCIS) |
| `EAD` | Extra abdominal desmoid | `EBT` | Ectopic (accessory) breast tissue |
| `EC` | Epidermal inclusion cyst | `ED` | Edema |
| `FA` | Fibroadenoma | `FAC` | Fibroademotoid change |
| `FAH` | Fibroadenomatoid hyperplasia | `FAL` | Fibroadenolipoma/hamartoma |
| `FB` | Foreign body (reaction) | `FBS` | Fibrosis |
| `FC` | Fibrocystic | `FEA` | Flat epithelial atypia |
| `FEL` | Fibroepithelial lesion | `FF` | Focal fibrosis |
| `FM` | Fibromatosis | `FN` | Fat necrosis |
| `FS` | Fibrosarcoma | `GA` | Galactocele |
| `GC` | Granular cell tumor | `GCR` | Giant cell reaction |
| `GF` | Giant fibroadenoma | `GM` | Granulomatous Mastitis |
| `GRC` | Glycogen-rich carcinoma | `GYN` | Gynecomastia |
| `HA` | Hamartoma | `HAP` | Hemanglopericytoma |
| `HE` | Hematoma | `HEM` | Hemorrhage |
| `HES` | Hemangioma - nonparenchymal, subcutaneous | `HEV` | Hemangioma - venous |
| `HL` | Hodgkin's Lymphoma | `HM` | Hemangioma |
| `HY` | Hyperplasia, usual | `I` | Invasive mammary carcinoma |
| `IC` | Intracystic carcinoma | `ICC` | Invasive cribriform carcinoma |
| `ICP` | Intracystic papillary carcinoma | `ID` | Invasive ductal carcinoma |
| `IDC` | Invasive ductal adenocarcinoma | `IF` | Inflammation |
| `II` | Invasive and in-situ carcinoma | `IL` | Invasive lobular carcinoma |
| `IMC` | Invasive Mucinous Carcinoma | `IMN` | Intramammary lymph node |
| `IN` | Infarct | `INC` | Inflammatory carcinoma |
| `IPC` | Invasive papillary carcinoma | `JF` | Juvenile fibroadenoma |
| `JP` | Juvenile papillomatosis | `LA` | Lactating adenoma |
| `LB` | Lipoma of the breast | `LC` | Lactational change |
| `LH` | Lobular hyperplasia | `LI` | Leukemic infiltration |
| `LM` | Leiomyoma | `LMS` | Leiomyosarcoma |
| `LN` | Lymph node | `LP` | Large duct papilloma |
| `LPS` | Liposarcoma | `LRC` | lipid-rich (lipid-secreting) carcinoma |
| `LS` | Lobular carcinoma in-situ (LCIS) | `LVI` | Lymphatic vessel invasion |
| `LY` | Lymphoma | `MAS` | Mastitis |
| `MB` | Metastatic cancer to the breast | `MBC` | Metastatic cancer to the breast from the colon |
| `MBL` | Metastatic cancer to the breast from the lung | `MBM` | Metastatic melanoma to the breast |
| `MBO` | Metastatic cancer to the breast from the ovary | `MBS` | Metastatic sarcoma to the breast |
| `MC` | Medullary carcinoma | `MD` | Mondor's disease (thrombophlebitis) |
| `MDC` | Multifocal intraductal carcinoma | `MDN` | Metastatic disease to axillary node |
| `MFB` | Myofibroblastoma | `MFH` | Malignant fibrous histiocytoma |
| `MGA` | Microglandular adenosls | `MH` | Malingnant fibrous hystiocytoma |
| `MIC` | Multifocal invaslve ductal carcinoma | `MIM` | Metastasis to an intramammary lymph node |
| `MIP` | Multiple intraductal papillomas | `MMN` | Malignant melanoma of the nipple |
| `MP` | Microscopic Papilloma | `NA` | No abnormality |
| `NBT` | Normal breast tissue | `ND` | Non-diagnostic |
| `NFA` | Neurofibroma | `NFS` | Neurofibromatosis |
| `NHL` | Non-Hodgkin lymphoma | `NMS` | Neoplasm of the mammary skin |
| `NOS` | Not otherwise specified | `NPA` | Nipple adenoma |
| `OC` | Oil cyst (fat necrosis cyst) | `OS` | Osteogenic sarcoma |
| `PA` | Papilloma | `PC` | Papillary carcinoma in-situ |
| `PD` | Paget's disease (of the nipple) | `PDP` | Peripheral duct papillomas |
| `PL` | Pleomorphic adenoma | `PLS` | Plasmacytoma |
| `PRM` | Post reduction mammoplasty | `PSH` | Pseudoangiomatous stromal hyperplasia |
| `PT` | Phylloides tumor | `PTM` | Phylloides tumor - malignant |
| `RM` | Recurrent malignancy | `RS` | Radial scar |
| `SA` | Sclerosing adenosis | `SBT` | Sclerotic breast tissue |
| `SC` | Signet cell carcinoma | `SCL` | Sclerosis |
| `SCN` | Squamous cell carcinoma of the nipple | `SCT` | Spindle cell tumor |
| `SE` | Seroma | `SF` | Stromal fibrosis |
| `SG` | Silicone granuloma | `SJC` | Secretory (juvenile) carcinoma |
| `SQ` | Squamous carcinoma | `ST` | Scar tissue |
| `TA` | Tubular adenoma | `TC` | Tubular carcinoma |
| `TR` | Treatment effect | `VGH` | Virginal hyperplasia |
