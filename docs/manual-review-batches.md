# Maintainer clarification record

This is a historical evidence record, not an onboarding guide or executable
workflow specification.

## Purpose

This records the completed maintainer review of catalog questions that could
not be settled mechanically on July 29, 2026. The detailed responses are
preserved in Git commit `359cc43`; the resulting catalog implementation is
commit `e77da91`.

The catalog and this record distinguish:

- confirmed semantics that can now be presented as verified;
- tentative guidance that must remain unresolved;
- questions that cannot currently be clarified; and
- system-specific investigations for which no single owner or dictionary
  exists.

Table manifests, physical types, schema nullability, reference closure, query
behavior, and other mechanical checks were not part of maintainer review.

## Confirmed semantics

### Mammography aggregates

- Exam-level and breast-side-level mass, calcification, asymmetry, and
  architectural-distortion fields are Boolean summaries of finding-level
  presence flags.
- They aggregate only mammography findings, including full-field digital
  mammography (FFDM), synthetic 2D, and digital breast tomosynthesis (DBT), not
  ultrasound or magnetic resonance imaging (MRI) findings.
- Left and right finding totals count distinct findings recorded on the
  respective breast during an exam. They are stored on side-level rows, but
  that storage does not give them a different row-specific meaning.

### Pathology-severity aggregation

- Exam-level and breast-side-level pathology severity select the minimum value
  among procedure-associated pathology records in the applicable group.
- Because pathology-severity codes use inverse ordering, the minimum is the
  most severe value.

### Finding number

- Ordinary finding numbers are ordinal within an accession.
- Finding number `-9` identifies a derived synthetic contralateral negative
  finding. It represents a negative assessment implied by a non-negative
  finding on the other breast when the negative finding was not explicitly
  entered in MagView.
- Synthetic contralateral negatives are derived records, not manually entered
  findings.

### Age and demographic fields

- Age fields are measured in years. Values such as zero are data-quality
  errors, not documented sentinel codes.
- Age at exam is calculated from birth date and study date after both receive
  the same within-patient shift. It is otherwise unchanged, except that ages
  greater than or equal to 90 are top-coded to 89.
- The Ashkenazi indicator represents self-identified Ashkenazi Jewish heritage
  recorded as a known breast-cancer risk factor. Its completeness and
  reliability are not established.
- Gender description represents patient legal sex at the time of the exam; it
  does not represent gender identity.
- The EMBED data-version field records the first EMBED release in which the
  element was included.

### Laterality

- A null side attached to a clinical finding represents a bilateral finding.
- Outside the finding-side context, null generally represents unknown
  laterality.
- In particular, a null biopsy or procedure side must not be interpreted as a
  bilateral biopsy or procedure.

### Field-specific parsing and nulls

- There is no catalog-wide delimiter, ordering, repetition, composition, or
  null convention for loosely structured coded fields.
- Without field-specific evidence, preserve the source string, treat ordering
  as non-informative, and treat null as unknown or missing.
- The addendum flag is processing-derived rather than directly extracted from
  MagView. Its nulls reflect processing behavior and are not inherently
  informative.

## Tentative guidance retained as unresolved

### Risk outputs

- Ordinary National Cancer Institute (NCI) and International Breast Cancer
  Intervention Study (IBIS) risk-model values are tentatively believed to use
  percentage points, but the risk table has not been validated in depth.
- Meanings of `-35`, `-2`, and `100` remain unknown.
- NCI and IBIS model versions remain unknown.
- Definitions of `IBISPOP10`, `IBISPOPL`, and `IBIS_TD1` through `IBIS_TD4`
  remain unknown.

### Report revisions and addendums

- Reports with a sequence greater than the accession minimum are expected to be
  later versions and generally addendums.
- Real-world exceptions may exist where a later version is not an addendum in
  the strict clinical sense.
- The overlap between report sequence and the processing-derived addendum flag
  has not been directly validated.

### Remaining sentinels and measurements

- Semantics of zero or other nonpositive finding numbers remain unresolved.
- Zero and negative meanings for distance, size, calcification number, and
  biopsy distance remain unresolved.
- Units for distance and size remain unresolved.
- Flag encodings and null meanings remain field-specific unless separately
  documented.

## Currently unresolvable

The following should retain their existing caveats rather than prompting
another general maintainer review:

- equivalence or distinction of the secondary MRI delayed-kinetics field;
- the meaning and vocabulary of MRI other finding;
- the meaning and units of MRI size;
- whether case-insensitive header matching is a general MRI legend rule;
- the specific pregnancy event represented by pregnancy age; and
- completeness, reliability, encoding, and null behavior of the Ashkenazi
  indicator.

The prior question about inferred `loc_num` and accession legend associations
was not concrete enough for maintainer review. Those associations remain
explicitly inferred from header similarity and should be settled from a
specific release artifact or a narrowly framed field-level investigation, not
another general question.

## Unknown code mappings

There is no single authoritative owner, export, versioned dictionary, or
MagView configuration artifact covering recommendation and pathology codes
absent from the released legend. EMBED touches many clinical systems, so
resolving an unknown code requires system-specific investigation and data
processing.

Repository behavior remains:

- flag unknown mappings explicitly;
- retain raw codes without interpretation;
- do not guess or silently normalize them; and
- do not imply that one person or team can provide a universal mapping.

## Closed review status

This broad maintainer review is complete. Future maintainer questions should be
narrow, field-specific, and asked only after available release artifacts and
safe mechanical checks have been exhausted.
