# EVP-6124 Exact Anchor Review v0

- Outcome: `promote_to_exact_anchor`
- Confidence: `medium`
- Summary: Promote into exact-anchor review pass. The qualifying support surface is multi-source and includes both AD-specific trial registration and AD-specific publication evidence.
- Exemplar record: `clinicaltrials_gov:NCT01073228`
- Exemplar title: Safety and Cognitive Function Study of EVP-6124 in Patients With Mild to Moderate Alzheimer's Disease

## Support Surface

- Source systems: clinicaltrials_gov, pubmed
- Evidence roles: publication_record, trial_registration
- Support status: `multi_source`
- Qualifying support record count: 3
- Qualifying support source count: 2
- Qualifying support record ids: clinicaltrials_gov:NCT01073228, clinicaltrials_gov:NCT02246075, pubmed:25495510
- Non-qualifying related record count: 0

## Rationale

- The qualifying support surface spans both ClinicalTrials.gov and PubMed.
- The qualifying support includes at least one AD-specific trial-registration record and one AD-specific publication record.
- The candidate review layer has already cleared this intervention for exact-anchor review, and the detailed packet confirms that judgment on exact-scope records.

## Caution Flags

- promotion_requires_manifest_and_exact-linkage_update

## Next Actions

- Add this intervention to the exact-anchor review pass list in the tracked intervention manifest.
- Update the exact linkage layer so only the qualifying records are treated as exact-anchor support.
- Keep excluded or adjacent records visible in review notes, but do not let them silently widen the exact-anchor claim.
