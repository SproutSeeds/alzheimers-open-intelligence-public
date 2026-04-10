# Alzheimer's Public Record Dataset Brief v0

## Working Title

Alzheimer's Public Record Intervention and Biomarker Dataset

## Purpose

Create a structured, reproducible dataset from official public records that
captures how Alzheimer's interventions and biomarker programs appear across
trial registries, publications, open-access full text, grant metadata, and
regulatory records.

## Why This Exists

The repository needs a first real data object that:

- is compatible with a Codex-first workflow
- does not depend on controlled participant-level access
- is immediately useful for evidence organization
- can grow into benchmark and triage artifacts later

## Unit Of Record

The initial unit of record is one public evidence record tied to one canonical
entity.

A row may represent:

- a trial registration for an intervention
- a publication record for a biomarker finding
- a grant record relevant to an intervention or biomarker program
- a regulatory label or adverse-event signal tied to an intervention

## Canonical Row Shape

Each row should be able to answer:

- what entity is this about
- what kind of evidence is this
- where did it come from
- what Alzheimer's scope does it touch
- what biomarker family or intervention family does it map to
- what outcome direction or result status is visible
- what provenance and extraction method produced the row

## First Source Stack

- ClinicalTrials.gov API
- PubMed E-utilities
- PMC Open Access Subset
- NIH RePORTER API
- openFDA

## First Questions

- Which interventions show up across trials, papers, grants, and regulatory
  records?
- Which biomarker families recur most often in Alzheimer's public records?
- Which off-patent interventions deserve a clearer evidence ledger?
- Which areas are overrepresented in hype but underrepresented in public record
  depth?

## Out Of Scope For v0

- participant-level raw clinical data
- disease-risk prediction from individual subjects
- uncontrolled web scraping
- therapeutic claims inferred from weak public traces

## Immediate Next Artifact

After the v0 source and query contracts, the next meaningful artifact is a
small derived seed table populated from one or two official public sources and
validated against the row schema.
