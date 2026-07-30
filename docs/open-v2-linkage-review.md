# Open-v2 linkage review record

This is a historical evidence record, not an onboarding guide or executable
join specification. `open-v2` is the registered profile ID for the open EMBED
V2 physical layout; it is not catalog schema version 2.

## Purpose and evidence boundary

This document preserves the qualitative conclusions from the open-v2 linkage
review that originally informed the schema-v3 physical table, key, projection,
and relationship declarations. It is retained as a versioned source so catalog
claims do not cite the catalog that currently contains those claims.

The review combined release-schema evidence with safe cross-table checks. It
did not establish database constraints, complete longitudinal capture,
clinical attribution, or contemporaneous availability. The portable catalog
therefore uses these conclusions only as profile-specific implementation
evidence. It does not carry empirical counts or distributions.

The original evolution is recoverable in repository history, principally from
the Phase 2 linkage commits beginning at `42677b2` and the populated open-v2
linkage catalog at `7670c51`, with later validation corrections in `011681a`,
`d21b2f8`, and `5e433ef`.

## Reconciled implementation conclusions

- A non-null linked accession is an optional same-episode reference. It is not
  an enforced foreign key, can fail to resolve to the registered exam surface,
  and can be repeated by multiple source rows.
- A linked-study flag and linked-accession presence are intended to describe
  the same linkage role, but row-level equivalence is not guaranteed.
- The pathology-to-imaging relationship uses accession, finding side, and
  finding number. Components can be absent, and complete tuples can match more
  than one row in either direction.
- Pathology descriptor slots are procedure-associated. Slot position,
  within-severity-group order, and duplicate occurrence do not add diagnostic
  weight.
- Wide-table exam, patient, side, imaging-index, and pathology-index fields are
  projections or references. Co-location does not prove attribute authority,
  clinical attribution, or same-time availability.
- Report and finding joins by accession can multiply both sides. No reviewed
  natural report tuple was established as unique for every represented row.
- Risk-to-exam linkage is optional and does not imply that every exam has a
  risk assessment.

## Conclusions that remain unresolved

- Later report sequence values generally represent later versions and often
  addendums, but real-world exceptions and equivalence with the derived
  addendum flag were not established.
- Several risk-output definitions, exceptional values, units, and generating
  model versions remain unconfirmed.
- Physical resolution checks do not establish complete clinical follow-up,
  outside-system outcome capture, or the causal relationship between an
  imaging finding and a later procedure or diagnosis.

## Use in schema version 5

Schema version 5 keeps these conclusions beneath the portable clinical model.
They support open-v2 object bindings, physical relationship bindings,
profile-specific context claims, and coverage records. They must not be used
to infer that another release or storage representation has the same columns,
keys, joins, completeness, attribution, or availability behavior.
