# Seed Outputs

This directory holds small, non-secret seed artifacts generated from official
public record sources.

The current seeded build combines:

- ClinicalTrials.gov registration metadata
- PubMed publication metadata
- PMC Open Access linked publication metadata
- NIH RePORTER grant metadata
- openFDA drug label metadata
- openFDA aggregated adverse-event signal summaries

These artifacts are intentionally modest. Their job is to prove that the
public-record-derived lane is executable, schema-aligned, and useful enough to
extend.

The default seeded build is still bounded, but it is now wide enough to surface
additional trial registrations, biomarker-oriented records, behavioral
interventions, and a larger linked publication layer without leaving the realm
of a tractable tracked artifact.

The openFDA rows add regulatory label context and aggregated spontaneous-report
signal summaries; they are useful for safety and label surface mapping, not for
causal inference on their own.

The JSON artifact also includes source-count metadata and an entity-group
summary so the seed can be inspected as an evidence surface rather than only as
flat rows.

The PubMed slice is not only a keyword-query seed. It is also backfilled with
exact linked PMIDs discovered through PMC Open Access matching and NIH grant
publication bridges, so the tracked seed carries more of its own exact
cross-source structure.

The default seed also now includes targeted follow-on queries for tracked
interventions where the public surface is already strong enough to justify
deeper harvesting. That keeps the seed compact while letting the review layers
distinguish between single-source ideas, promotion-ready candidates, and
interventions that have already earned exact-anchor support.

Expected artifacts:

- `alzheimers-public-record-seed-v0.csv`
- `alzheimers-public-record-seed-v0.json`
