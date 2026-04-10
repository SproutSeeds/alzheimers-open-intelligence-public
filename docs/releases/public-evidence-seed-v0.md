# Alzheimer's Open Intelligence: Public Evidence Seed v0

## Summary

Alzheimer's Open Intelligence is releasing `Public Evidence Seed v0`, a
public-record-derived Alzheimer's evidence substrate built from official public
sources for reproducible basic research work.

This release is designed to help researchers inspect, compare, and reuse a
clean Alzheimer's evidence surface without waiting on controlled cohort access.

## Release Claim

This release provides a validated, multi-source public Alzheimer's evidence
layer with:

- a normalized seed dataset
- explicit linkage artifacts
- exact-vs-candidate separation
- exact-anchor intervention review records
- watchlist review records for unresolved candidates

## Source Systems

This release draws from:

- ClinicalTrials.gov
- PubMed
- PMC Open Access
- NIH RePORTER
- openFDA

## Included Artifacts

Core release artifacts:

- [Seed dataset CSV](../../datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.csv)
- [Seed dataset JSON](../../datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json)
- [Exact linkage snapshot](../../datasets/public-record-derived/linked/alzheimers-public-record-linkage-snapshot-v0.json)
- [Candidate linkage snapshot](../../datasets/public-record-derived/linked/alzheimers-public-record-candidate-linkage-snapshot-v0.json)
- [Candidate review report](../../datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-report-v0.md)
- [Exact-anchor review index](../../interventions/hypothesis-ledger/exact-anchor-reviews/exact-anchor-review-index-v0.md)
- [Watchlist review index](../../interventions/hypothesis-ledger/watchlist-reviews/watchlist-review-index-v0.md)

Archival record:

- DOI: [10.5281/zenodo.19502035](https://doi.org/10.5281/zenodo.19502035)
- Zenodo record: <https://zenodo.org/records/19502035>

Reproducibility artifacts:

- [Seed dataset builder](../../scripts/build_public_record_seed_dataset.py)
- [Linkage snapshot renderer](../../scripts/render_public_record_linkage_snapshot.py)
- [Candidate linkage renderer](../../scripts/render_public_record_candidate_linkage_snapshot.py)
- [Candidate review renderer](../../scripts/render_public_record_candidate_review_snapshot.py)
- [Exact-anchor review packet renderer](../../scripts/render_public_record_exact_anchor_review_packets.py)
- [Repo validator](../../scripts/validate_repo_artifacts.py)

## Current Snapshot

At the validated release state, this release contains:

- `105` validated public-record seed rows
- `5` official public source systems
- `4` exact-anchor review records
- `2` watchlist review records

## Exact-Anchor Interventions

The current exact-anchor intervention surfaces are:

- `EVP-6124`
- `Music Therapy`
- `Transcranial Direct Current Stimulation`
- `Transcranial Electromagnetic Treatment`

These were promoted through explicit exact-anchor review rather than silent
score escalation.

## Watchlist Interventions

The current watchlist is:

- `Cortical Brain Stimulation`
- `Improvisational Movement`

These remain visible precisely because they have not yet earned the same level
of support as the exact-anchor set.

## Why This Release Is Useful

This release gives researchers a compact public layer for:

- intervention discovery
- grant-publication-trial linkage
- public evidence review
- machine-readable reuse
- replication and extension of the extraction pipeline

## Methodological Boundary

This release is built from official public records. It is not a patient-level
cohort release, not a clinical decision system, and not medical advice.

Its value is evidence organization, provenance, and disciplined review.

## Citation

Please cite this release using the metadata in [CITATION.cff](../../CITATION.cff).

Suggested short citation text:

Alzheimer's Open Intelligence: Public Evidence Seed v0. Cody Mitchell, Fractal
Research Group LLC, 2026. <https://doi.org/10.5281/zenodo.19502035>

## Next Direction

The next major public layer after this release is biomarker-family evaluation,
so the repository can grow from intervention-centered review toward a broader
Alzheimer's intelligence surface.
