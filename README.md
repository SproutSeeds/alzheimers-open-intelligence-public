# Alzheimer's Open Intelligence Public

Research stewardship: Fractal Research Group LLC ([frg.earth](https://frg.earth)).

This repository is the public scientific release surface for Alzheimer's Open
Intelligence. It publishes bounded, citeable, versioned releases derived from
the private upstream research workspace.

## Current Release

- [Public Evidence Seed v0](docs/releases/public-evidence-seed-v0.md)
- [How to use the release](docs/how-to-use-public-evidence-seed-v0.md)
- [Citation metadata](CITATION.cff)
- [Hugging Face dataset card draft](docs/releases/hugging-face-dataset-card-public-evidence-seed-v0.md)

## What This Repo Contains

The current release includes:

- `105` validated public-record seed rows
- `5` official public source systems
- `4` exact-anchor intervention review records
- `2` watchlist review records

The release is built from official public sources including:

- ClinicalTrials.gov
- PubMed
- PMC Open Access
- NIH RePORTER
- openFDA

## Why This Exists

This repo is meant to give researchers a public Alzheimer's evidence substrate
they can inspect, cite, reuse, and extend without needing access to controlled
participant-level cohorts.

## Reproducibility

Selected scripts and schemas used to build and validate the current release are
included under:

- `scripts/`
- `schemas/`

## Upstream Model

The working model is:

- private upstream research workspace
- public downstream scientific release repo

This repository is the downstream public side of that model.

## Licensing

- Code, scripts, and schemas: Apache-2.0
- Public-facing release materials: CC BY 4.0

See:

- `LICENSE`
- `LICENSE-docs.md`

## Distribution

The recommended multi-channel distribution stack for each release is:

- GitHub release
- Zenodo archival DOI
- frg.earth release page
- Hugging Face dataset mirror

## Repository

Public repository URL:

- https://github.com/SproutSeeds/alzheimers-open-intelligence-public
