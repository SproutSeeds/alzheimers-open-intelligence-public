# Alzheimer's Public Record Source Map v0

## Source Set

### ClinicalTrials.gov

- official surface:
  - `https://clinicaltrials.gov/data-api/about-api`
- role in dataset:
  - trial registrations, sponsors, phases, intervention names, outcome
    measures, recruiting status
- why it matters:
  - best public starting point for intervention and biomarker program tracking

### PubMed via NCBI E-utilities

- official surface:
  - `https://www.ncbi.nlm.nih.gov/books/NBK25501/`
- role in dataset:
  - publication metadata, abstracts, linked identifiers, disease and biomarker
    search surfaces
- why it matters:
  - fastest broad public literature index for Alzheimer's trial and biomarker
    evidence mapping

### PMC Open Access Subset

- official surface:
  - `https://pmc.ncbi.nlm.nih.gov/tools/openftlist/`
- role in dataset:
  - reusable full text and richer article-level evidence extraction where
    license terms allow
- why it matters:
  - gives a path beyond abstract-only evidence
- caution:
  - automated retrieval must use PMC-approved services, and license terms vary
    by article

### NIH RePORTER API

- official surface:
  - `https://api.reporter.nih.gov/?urls.primaryName=V2.0`
- role in dataset:
  - grant metadata, project abstracts, organization and investigator context,
    linked publication search
- why it matters:
  - helps connect public funding flows to intervention and biomarker programs
- caution:
  - NIH recommends modest request rates and off-peak large jobs

### openFDA

- official surfaces:
  - `https://www.fda.gov/science-research/health-informatics-fda/openfda`
  - `https://open.fda.gov/apis/`
- role in dataset:
  - drug labeling, adverse-event reports, enforcement context, identifier
    harmonization
- why it matters:
  - adds public regulatory and safety texture to intervention evidence
- caution:
  - openFDA is public and useful, but not a clinical decision system

## Retrieval Principle

Use official APIs, bulk services, and published programmatic surfaces first.
Avoid ad hoc scraping when an official machine-readable path exists.

## v0 Recommendation

Start with:

1. ClinicalTrials.gov
2. PubMed
3. NIH RePORTER

Then add:

4. PMC Open Access Subset
5. openFDA

That order gives the fastest useful public substrate with the least workflow
friction.
