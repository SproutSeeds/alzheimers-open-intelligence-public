# How To Use Public Evidence Seed v0

## Purpose

This guide helps researchers quickly understand what `Public Evidence Seed v0`
contains, what it is good for, and how to start using it.

## Start Here

If you want the main release object, start with:

- [Release note](releases/public-evidence-seed-v0.md)
- [Seed dataset CSV](../datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.csv)
- [Seed dataset JSON](../datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json)

If you want the review/governance layer, then read:

- [Exact-anchor review index](../interventions/hypothesis-ledger/exact-anchor-reviews/exact-anchor-review-index-v0.md)
- [Candidate review report](../datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-report-v0.md)
- [Watchlist review index](../interventions/hypothesis-ledger/watchlist-reviews/watchlist-review-index-v0.md)

## What The Dataset Contains

The release combines official public records from:

- ClinicalTrials.gov
- PubMed
- PMC Open Access
- NIH RePORTER
- openFDA

Each row follows the machine-readable row contract in
[alzheimers-public-record-row-v0.yaml](../schemas/alzheimers-public-record-row-v0.yaml).

## What It Is Good For

This release is useful for:

- tracing public evidence around Alzheimer’s interventions
- finding cross-source support for public Alzheimer’s records
- identifying candidate grant-publication-trial bridges
- reusing the extraction and review logic as a base for downstream work

## What It Is Not

This release is not:

- a patient-level cohort dataset
- a benchmark leaderboard
- a treatment recommendation engine
- a complete representation of all Alzheimer's evidence

## How To Rebuild The Release

The current public-record release surface can be regenerated from repo-local
scripts.

Useful entry points:

- [build_public_record_seed_dataset.py](../scripts/build_public_record_seed_dataset.py)
- [render_public_record_linkage_snapshot.py](../scripts/render_public_record_linkage_snapshot.py)
- [render_public_record_candidate_linkage_snapshot.py](../scripts/render_public_record_candidate_linkage_snapshot.py)
- [render_public_record_candidate_review_snapshot.py](../scripts/render_public_record_candidate_review_snapshot.py)
- [render_public_record_exact_anchor_review_packets.py](../scripts/render_public_record_exact_anchor_review_packets.py)
- [validate_repo_artifacts.py](../scripts/validate_repo_artifacts.py)

## How To Cite

Use the metadata in [CITATION.cff](../CITATION.cff).

## Best Next Step For A New Reader

Read the release note first, then inspect the seed JSON and the exact-anchor
review index. That gives the clearest fast picture of what the release already
knows and how it governs uncertainty.
