#!/usr/bin/env python3
"""Build a small Alzheimer's public-record-derived seed dataset."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import jsonschema
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "alzheimers-open-intelligence/0.1 (public-record-seed-builder)"
CURRENT_YEAR = dt.date.today().year
PMC_TOOL_NAME = "alzheimers-open-intelligence"
PMC_CONTACT_EMAIL = "cody@frg.earth"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at {path}")
    return data


def load_schema(path: Path) -> dict:
    return load_yaml(path)


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"\b{re.escape(alias.lower())}\b", text.lower()) is not None


def join_text_parts(parts: list[str]) -> str:
    return normalize_text(" ".join(part for part in parts if normalize_text(part)))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", normalize_text(value).lower()).strip("_")
    return slug or "unknown"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def infer_disease_scope(text: str) -> str:
    lower = text.lower()
    if "mild cognitive impairment" in lower or "mci" in lower:
        return "mild_cognitive_impairment"
    if "alzheimer" in lower:
        return "alzheimers_disease"
    if "dementia" in lower:
        return "dementia_general"
    return "related_neurodegeneration"


def infer_biomarker_family(text: str) -> str:
    lower = text.lower()
    if re.search(r"\bamyloid\b", lower):
        return "amyloid"
    if re.search(r"\bp-?tau217\b", lower) or re.search(r"\btau\b", lower):
        return "tau"
    if re.search(r"\bneurofilament light\b", lower) or re.search(r"\bnfl\b", lower):
        return "neurofilament_light"
    if re.search(r"\bgfap\b", lower):
        return "gfap"
    if re.search(r"\binflamm", lower):
        return "inflammation"
    if re.search(r"\b(pet|mri|eeg|plasma biomarker|csf)\b", lower):
        return "molecular_imaging"
    return "not_specified"


def infer_intervention_or_assay_type(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(antibody|monoclonal)\b", lower) or re.search(r"\b[a-z0-9-]*mab\b", lower):
        return "monoclonal_antibody"
    if re.search(r"\bvaccine\b", lower):
        return "vaccine"
    if re.search(
        r"\b(study drug|small molecule|capsule|tablet|memantine|rivastigmine|galantamine|donepezil|inhibitor|agonist|antagonist)\b",
        lower,
    ):
        return "small_molecule"
    if re.search(
        r"\b(diet|exercise|mindfulness|music therapy|singing|dance|movement|lifestyle|counseling|behavioral intervention|sleep)\b",
        lower,
    ):
        return "behavioral_or_lifestyle"
    if re.search(
        r"\b(biomarker|pet|plasma|csf|blood|eeg|mri|imaging|assay|genomic|genetics|sequencing)\b",
        lower,
    ):
        return "biomarker_or_assay"
    if re.search(r"\b(device|stimulation|electromagnetic|tdcs)\b", lower):
        return "device_or_stimulation"
    return "not_specified"


def infer_sponsor_type(class_name: str) -> str:
    normalized = normalize_text(class_name).upper()
    if normalized in {"INDUSTRY"}:
        return "industry"
    if normalized in {"NIH", "FED", "GOVERNMENT"}:
        return "government"
    if normalized in {"OTHER", "NETWORK"}:
        return "academic"
    return "unknown"


def infer_organization_sponsor_type(org_name: str, org_type: str) -> str:
    text = join_text_parts([org_name, org_type]).lower()
    if re.search(r"\b(university|college|school|hospital|medical center|institute)\b", text):
        return "academic"
    if re.search(r"\b(inc|corp|corporation|llc|ltd|pharma|biotech|therapeutics)\b", text):
        return "industry"
    if re.search(r"\b(nih|fda|cdc|va|government|department of)\b", text):
        return "government"
    if re.search(r"\b(foundat|nonprofit|not-for-profit)\b", text):
        return "nonprofit"
    return "unknown"


def extract_year(text: str, fallback: int = 2026) -> int:
    match = re.search(r"(19|20)\d{2}", str(text or ""))
    return int(match.group(0)) if match else fallback


def clinicaltrials_url_for_condition(condition: str, page_size: int) -> str:
    encoded_condition = urllib.parse.quote(condition)
    return (
        "https://clinicaltrials.gov/api/v2/studies"
        f"?query.cond={encoded_condition}&pageSize={page_size}&format=json"
    )


def clinicaltrials_url_for_term(term: str, page_size: int) -> str:
    encoded_term = urllib.parse.quote(term)
    return (
        "https://clinicaltrials.gov/api/v2/studies"
        f"?query.term={encoded_term}&pageSize={page_size}&format=json"
    )


def clinicaltrials_url_for_condition_and_term(condition: str, term: str, page_size: int) -> str:
    encoded_condition = urllib.parse.quote(condition)
    encoded_term = urllib.parse.quote(term)
    return (
        "https://clinicaltrials.gov/api/v2/studies"
        f"?query.cond={encoded_condition}&query.term={encoded_term}&pageSize={page_size}&format=json"
    )


def is_alzheimers_related_text(text: str) -> bool:
    lower = normalize_text(text).lower()
    return (
        "alzheimer" in lower
        or "mild cognitive impairment" in lower
        or "dementia" in lower
    )


def build_clinicaltrials_row(study: dict, provenance_note: str) -> dict | None:
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    arms_module = protocol.get("armsInterventionsModule", {})
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    design_module = protocol.get("designModule", {})
    status_module = protocol.get("statusModule", {})
    outcomes_module = protocol.get("outcomesModule", {})

    nct_id = normalize_text(identification.get("nctId", ""))
    if not nct_id:
        return None

    conditions = conditions_module.get("conditions", []) or []
    condition_text = join_text_parts([str(item) for item in conditions])
    title = normalize_text(identification.get("briefTitle", ""))
    if not is_alzheimers_related_text(join_text_parts([condition_text, title])):
        return None

    interventions = arms_module.get("interventions", []) or []
    first_intervention = interventions[0] if interventions else {}
    intervention_name = normalize_text(first_intervention.get("name", ""))
    intervention_type = normalize_text(first_intervention.get("type", ""))
    summary_text = join_text_parts(
        [
            title,
            condition_text,
            intervention_name,
            intervention_type,
            join_text_parts(
                [
                    normalize_text(item.get("measure", ""))
                    for item in outcomes_module.get("primaryOutcomes", [])[:3]
                ]
            ),
        ]
    )

    phase_values = design_module.get("phases", []) or []
    phase_or_design = normalize_text(" / ".join(phase_values)) or normalize_text(
        design_module.get("studyType", "")
    ) or "not_specified"

    return {
        "record_id": f"clinicaltrials_gov:{nct_id}",
        "entity_type": "trial",
        "canonical_entity_name": intervention_name or title,
        "disease_scope": infer_disease_scope(summary_text),
        "source_system": "clinicaltrials_gov",
        "source_record_id": nct_id,
        "source_url": f"https://clinicaltrials.gov/study/{nct_id}",
        "record_title": title,
        "evidence_role": "trial_registration",
        "intervention_or_assay_type": infer_intervention_or_assay_type(
            join_text_parts([intervention_type, intervention_name, title])
        ),
        "biomarker_family": infer_biomarker_family(summary_text),
        "model_system_or_population": condition_text or "alzheimers_related_human_population",
        "result_direction": "not_yet_known",
        "off_patent_status": "unknown",
        "sponsor_type": infer_sponsor_type(sponsor_module.get("leadSponsor", {}).get("class", "")),
        "phase_or_study_design": phase_or_design,
        "year": extract_year(
            status_module.get("studyFirstPostDateStruct", {}).get("date", "")
            or status_module.get("startDateStruct", {}).get("date", "")
        ),
        "extraction_method": "api_structured",
        "provenance_note": provenance_note,
    }


def fetch_clinicaltrials_rows(manifest: dict, max_records: int) -> list[dict]:
    condition_terms = manifest["disease_scope_terms"][:2]
    rows: list[dict] = []
    seen_ids: set[str] = set()
    per_condition = max(1, max_records)

    for condition in condition_terms:
        payload = fetch_json(clinicaltrials_url_for_condition(condition, per_condition))
        for study in payload.get("studies", []):
            row = build_clinicaltrials_row(
                study,
                provenance_note=(
                    f"ClinicalTrials.gov v2 study query using query.cond={condition}"
                ),
            )
            if row is None or row["record_id"] in seen_ids:
                continue
            rows.append(row)
            seen_ids.add(row["record_id"])
            if len(rows) >= max_records:
                return rows[:max_records]

    return rows[:max_records]


def openfda_url(endpoint: str, search: str, limit: int, count_field: str | None = None) -> str:
    encoded_search = urllib.parse.quote(search, safe=":+")
    base = f"https://api.fda.gov/{endpoint}.json?search={encoded_search}"
    if count_field:
        encoded_count = urllib.parse.quote(count_field, safe=".")
        return f"{base}&count={encoded_count}&limit={limit}"
    return f"{base}&limit={limit}"


def pubmed_esearch_url(seed_query: str, retmax: int) -> str:
    encoded_query = urllib.parse.quote(seed_query)
    return (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&retmode=json&retmax={retmax}&term={encoded_query}"
    )


def pubmed_esummary_url(ids: list[str]) -> str:
    encoded_ids = urllib.parse.quote(",".join(ids))
    return (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pubmed&retmode=json&id={encoded_ids}"
    )


def pmc_id_converter_url(ids: list[str], idtype: str) -> str:
    params = {
        "ids": ",".join(ids),
        "idtype": idtype,
        "format": "json",
        "tool": PMC_TOOL_NAME,
        "email": PMC_CONTACT_EMAIL,
    }
    return "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?" + urllib.parse.urlencode(params)


def derive_core_project_num(project_num: str) -> str:
    first_segment = normalize_text(project_num).split("-")[0]
    return re.sub(r"^\d+", "", first_segment)


def nih_publications_search(core_project_num: str, limit: int) -> dict:
    return post_json(
        "https://api.reporter.nih.gov/v2/publications/search",
        {
            "criteria": {"core_project_nums": [core_project_num]},
            "limit": limit,
            "offset": 0,
        },
    )


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def fetch_pubmed_summaries(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    summary = fetch_json(pubmed_esummary_url(ids))
    results = summary.get("result", {})
    return {str(uid): results.get(uid, {}) for uid in results.get("uids", [])}


def fetch_pubmed_seed_ids(manifest: dict, max_records: int) -> list[str]:
    pubmed_config = manifest["source_queries"]["pubmed"]
    seed_query = str(pubmed_config["seed_query"])
    esearch = fetch_json(pubmed_esearch_url(seed_query, max_records))
    ids = [normalize_text(item) for item in esearch.get("esearchresult", {}).get("idlist", []) if normalize_text(item)]
    return dedupe_preserve_order(ids)


def candidate_pubmed_disease_clause(disease_scope: str) -> str:
    if disease_scope == "mild_cognitive_impairment":
        return (
            '"Mild Cognitive Impairment"[MeSH Terms] OR '
            '"Alzheimer Disease"[MeSH Terms] OR '
            '"mild cognitive impairment"[Title/Abstract] OR '
            'MCI[Title/Abstract] OR '
            'alzheimer*[Title/Abstract]'
        )
    if disease_scope == "dementia_general":
        return (
            '"Dementia"[MeSH Terms] OR '
            'dementia[Title/Abstract] OR '
            'alzheimer*[Title/Abstract]'
        )
    return (
        '"Alzheimer Disease"[MeSH Terms] OR '
        '"Mild Cognitive Impairment"[MeSH Terms] OR '
        'alzheimer*[Title/Abstract] OR '
        '"mild cognitive impairment"[Title/Abstract] OR '
        'dementia[Title/Abstract]'
    )


def candidate_pubmed_query(alias: str, disease_scope: str) -> str:
    alias_clause = f'"{normalize_text(alias)}"[Title/Abstract]'
    disease_clause = candidate_pubmed_disease_clause(disease_scope)
    return f"({alias_clause}) AND ({disease_clause})"

def score_candidate_pubmed_summary(tracked: dict, summary: dict) -> tuple[int, str]:
    title = normalize_text(summary.get("title", ""))
    title_lower = title.lower()
    aliases = [normalize_text(alias) for alias in tracked.get("alias_terms", []) if normalize_text(alias)]
    inferred_scope = infer_disease_scope(title)
    inferred_family = infer_intervention_or_assay_type(title)

    score = 0
    if any(contains_alias(title, alias) for alias in aliases):
        score += 6
    if inferred_scope == tracked["disease_scope"]:
        score += 6
    elif tracked["disease_scope"] == "alzheimers_disease" and inferred_scope == "mild_cognitive_impairment":
        score += 3
    elif inferred_scope == "dementia_general":
        score += 2

    if re.search(r"\b(patient|patients|subject|subjects|clinical|trial|study)\b", title_lower):
        score += 1
    if inferred_family == tracked["intervention_family"]:
        score += 1

    if re.search(r"\b(healthy|volunteer|scopolamine)\b", title_lower):
        score -= 3
    if re.search(r"\b(pig|mouse|mice|rat|rhesus|monkey|transgenic)\b", title_lower):
        score -= 4
    if re.search(r"\b(schizophrenia|attention-deficit|adhd)\b", title_lower):
        score -= 4

    return score, title_lower


def rank_candidate_pubmed_ids(tracked: dict, ids: list[str]) -> list[str]:
    summaries = fetch_pubmed_summaries(ids)
    scored: list[tuple[int, int, str, str]] = []
    for pmid in ids:
        summary = summaries.get(pmid, {})
        title = normalize_text(summary.get("title", ""))
        if not title:
            continue
        score, normalized_title = score_candidate_pubmed_summary(tracked, summary)
        inferred_scope = infer_disease_scope(title)
        scope_rank = 2 if inferred_scope == tracked["disease_scope"] else 1 if inferred_scope == "mild_cognitive_impairment" else 0
        scored.append((score, scope_rank, normalized_title, pmid))

    scored.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
    return [pmid for _, _, _, pmid in scored]


def score_targeted_clinicaltrials_study(tracked: dict, study: dict) -> tuple[int, str, str]:
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    arms_module = protocol.get("armsInterventionsModule", {})

    title = normalize_text(identification.get("briefTitle", ""))
    conditions = join_text_parts([str(item) for item in conditions_module.get("conditions", []) or []])
    intervention_names = join_text_parts(
        [normalize_text(item.get("name", "")) for item in arms_module.get("interventions", []) or []]
    )
    intervention_types = join_text_parts(
        [normalize_text(item.get("type", "")) for item in arms_module.get("interventions", []) or []]
    )
    combined_text = join_text_parts([title, conditions, intervention_names, intervention_types])
    aliases = [normalize_text(alias) for alias in tracked.get("alias_terms", []) if normalize_text(alias)]

    score = 0
    if any(contains_alias(title, alias) for alias in aliases):
        score += 5
    if any(contains_alias(intervention_names, alias) for alias in aliases):
        score += 4
    if any(contains_alias(combined_text, alias) for alias in aliases):
        score += 2

    inferred_scope = infer_disease_scope(combined_text)
    if inferred_scope == tracked["disease_scope"]:
        score += 5
    elif tracked["disease_scope"] == "alzheimers_disease" and inferred_scope == "mild_cognitive_impairment":
        score += 1

    inferred_family = infer_intervention_or_assay_type(combined_text)
    if inferred_family == tracked["intervention_family"]:
        score += 2

    combined_lower = combined_text.lower()
    if "alzheimer" in combined_lower:
        score += 1
    if re.search(r"\b(healthy|depression|aphasia|parkinson|stroke)\b", combined_lower):
        score -= 3

    nct_id = normalize_text(identification.get("nctId", ""))
    return score, title.lower(), nct_id


def targeted_clinicaltrials_conditions_for_scope(disease_scope: str) -> list[str]:
    if disease_scope == "mild_cognitive_impairment":
        return ["Mild Cognitive Impairment", "Alzheimer Disease"]
    if disease_scope == "dementia_general":
        return ["dementia", "Alzheimer Disease"]
    return ["Alzheimer Disease"]


def fetch_targeted_pubmed_ids(manifest: dict) -> list[str]:
    pubmed_config = manifest["source_queries"]["pubmed"]
    per_intervention_max = int(pubmed_config.get("candidate_follow_on_per_intervention_max", 0))
    if per_intervention_max <= 0:
        return []

    tracked = [
        item
        for item in manifest["tracked_interventions"]
        if "pubmed" in set(item.get("preferred_source_systems", []))
        and item.get("alias_terms")
    ]
    collected: list[str] = []
    for item in tracked:
        alias_terms = dedupe_preserve_order([normalize_text(alias) for alias in item["alias_terms"]])
        if not alias_terms:
            continue
        expansion_limit = max(per_intervention_max * 6, 12)
        candidate_ids: list[str] = []
        for alias in alias_terms:
            esearch = fetch_json(
                pubmed_esearch_url(
                    candidate_pubmed_query(alias, item["disease_scope"]),
                    expansion_limit,
                )
            )
            candidate_ids.extend(
                normalize_text(pmid)
                for pmid in esearch.get("esearchresult", {}).get("idlist", [])
                if normalize_text(pmid)
            )
        ranked_ids = rank_candidate_pubmed_ids(item, dedupe_preserve_order(candidate_ids))
        collected.extend(ranked_ids[:per_intervention_max])
    return dedupe_preserve_order(collected)


def fetch_pubmed_rows_from_ids(
    ids: list[str],
    *,
    base_query_ids: set[str],
    pmc_linked_ids: set[str],
    nih_linked_ids: set[str],
    targeted_linked_ids: set[str],
) -> list[dict]:
    if not ids:
        return []

    summary = fetch_json(pubmed_esummary_url(ids))
    rows: list[dict] = []
    for uid in summary.get("result", {}).get("uids", []):
        item = summary["result"].get(uid, {})
        title = normalize_text(item.get("title", ""))
        if not title:
            continue
        article_url = f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
        title_lower = title.lower()
        rows.append(
            {
                "record_id": f"pubmed:{uid}",
                "entity_type": "publication",
                "canonical_entity_name": title,
                "disease_scope": infer_disease_scope(title),
                "source_system": "pubmed",
                "source_record_id": str(uid),
                "source_url": article_url,
                "record_title": title,
                "evidence_role": "publication_record",
                "intervention_or_assay_type": infer_intervention_or_assay_type(title),
                "biomarker_family": infer_biomarker_family(title),
                "model_system_or_population": (
                    "human_publication_record"
                    if "mouse" not in title_lower and "mice" not in title_lower
                    else "preclinical_publication_record"
                ),
                "result_direction": "neutral_or_descriptive",
                "off_patent_status": "unknown",
                "sponsor_type": "unknown",
                "phase_or_study_design": "publication_metadata",
                "year": extract_year(item.get("pubdate", "")),
                "extraction_method": "api_structured",
                "provenance_note": (
                    "PubMed metadata record assembled from "
                    + ", ".join(
                        source_label
                        for source_label, condition in [
                            ("seed_query", uid in base_query_ids),
                            ("pmc_linked_pmid", uid in pmc_linked_ids),
                            ("nih_grant_publication_link", uid in nih_linked_ids),
                            ("targeted_intervention_query", uid in targeted_linked_ids),
                        ]
                        if condition
                    )
                    + f"; pubdate={normalize_text(item.get('pubdate', 'unknown'))}"
                ),
            }
        )
    return rows


def fetch_pubmed_rows(manifest: dict, max_records: int) -> list[dict]:
    base_ids = fetch_pubmed_seed_ids(manifest, max_records)
    return fetch_pubmed_rows_from_ids(
        base_ids,
        base_query_ids=set(base_ids),
        pmc_linked_ids=set(),
        nih_linked_ids=set(),
        targeted_linked_ids=set(),
    )


def fetch_pmc_open_access_rows(manifest: dict, max_records: int) -> tuple[list[dict], list[str]]:
    pmc_config = manifest["source_queries"]["pmc_open_access_subset"]
    seed_filter = str(pmc_config.get("seed_filter", "")).strip()
    if not seed_filter or max_records <= 0:
        return [], []

    disease_terms = manifest.get("disease_scope_terms", [])[:2]
    if disease_terms:
        quoted_terms = " OR ".join(f'"{term}"' for term in disease_terms)
        seed_query = f"({quoted_terms}) AND {seed_filter}"
    else:
        seed_query = seed_filter

    esearch = fetch_json(pubmed_esearch_url(seed_query, max_records))
    pmids = [normalize_text(item) for item in esearch.get("esearchresult", {}).get("idlist", []) if normalize_text(item)]
    if not pmids:
        return [], []

    summaries = fetch_pubmed_summaries(pmids)
    conversion = fetch_json(pmc_id_converter_url(pmids, "pmid"))
    rows: list[dict] = []
    seen_pmcids: set[str] = set()
    for record in conversion.get("records", []):
        if record.get("status") == "error":
            continue
        pmid = normalize_text(record.get("pmid", ""))
        pmcid = normalize_text(record.get("pmcid", ""))
        if not pmid or not pmcid or pmcid in seen_pmcids:
            continue
        summary = summaries.get(str(pmid), {})
        title = normalize_text(summary.get("title", "")) or pmcid
        title_lower = title.lower()
        rows.append(
            {
                "record_id": f"pmc_open_access_subset:{pmcid}",
                "entity_type": "publication",
                "canonical_entity_name": title,
                "disease_scope": infer_disease_scope(title),
                "source_system": "pmc_open_access_subset",
                "source_record_id": pmcid,
                "source_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                "record_title": title,
                "evidence_role": "publication_record",
                "intervention_or_assay_type": infer_intervention_or_assay_type(title),
                "biomarker_family": infer_biomarker_family(title),
                "model_system_or_population": (
                    "human_open_access_publication_record"
                    if "mouse" not in title_lower and "mice" not in title_lower
                    else "preclinical_open_access_publication_record"
                ),
                "result_direction": "neutral_or_descriptive",
                "off_patent_status": "unknown",
                "sponsor_type": "unknown",
                "phase_or_study_design": "open_access_full_text_record",
                "year": extract_year(summary.get("pubdate", ""), fallback=CURRENT_YEAR),
                "extraction_method": "api_structured",
                "provenance_note": (
                    f"PMC ID Converter + PubMed summary match; pmid={pmid}; "
                    f"seed_filter={seed_filter}"
                ),
            }
        )
        seen_pmcids.add(pmcid)
        if len(rows) >= max_records:
            break

    return rows, dedupe_preserve_order(pmids)


def fetch_nih_reporter_rows(manifest: dict, max_records: int) -> list[dict]:
    nih_config = manifest["source_queries"]["nih_reporter"]
    seed_terms = list(nih_config.get("seed_terms", []))
    if not seed_terms or max_records <= 0:
        return []

    rows: list[dict] = []
    seen_ids: set[str] = set()
    per_term_limit = max(1, max_records)
    url = "https://api.reporter.nih.gov/v2/projects/search"

    for term in seed_terms:
        payload = {
            "criteria": {
                "advanced_text_search": {
                    "operator": "and",
                    "search_field": "projecttitle,abstracttext",
                    "search_text": term,
                }
            },
            "limit": per_term_limit,
            "offset": 0,
            "include_fields": [
                "ProjectNum",
                "CoreProjectNum",
                "ProjectTitle",
                "AbstractText",
                "Organization",
                "OrganizationType",
                "PrincipalInvestigators",
                "FiscalYear",
                "ProjectDetailUrl",
                "AgencyIcFundings",
            ],
        }
        response = post_json(url, payload)
        for item in response.get("results", []):
            project_num = normalize_text(item.get("project_num", ""))
            fiscal_year = item.get("fiscal_year")
            record_id = f"nih_reporter:{project_num}:{fiscal_year}"
            if not project_num or record_id in seen_ids:
                continue

            title = normalize_text(item.get("project_title", ""))
            abstract_text = normalize_text(item.get("abstract_text", ""))
            combined_text = join_text_parts([title, abstract_text])
            project_url = normalize_text(item.get("project_detail_url", "")) or (
                "https://reporter.nih.gov/"
            )
            org = item.get("organization", {}) or {}
            org_name = normalize_text(org.get("org_name", ""))
            org_type = normalize_text((item.get("organization_type") or {}).get("name", ""))
            ic_fundings = item.get("agency_ic_fundings", []) or []
            agency_names = ", ".join(
                normalize_text(funding.get("name", "")) for funding in ic_fundings if normalize_text(funding.get("name", ""))
            )
            rows.append(
                {
                    "record_id": record_id,
                    "entity_type": "grant",
                    "canonical_entity_name": title or project_num,
                    "disease_scope": infer_disease_scope(combined_text),
                    "source_system": "nih_reporter",
                    "source_record_id": project_num,
                    "source_url": project_url,
                    "record_title": title or project_num,
                    "evidence_role": "grant_record",
                    "intervention_or_assay_type": infer_intervention_or_assay_type(combined_text),
                    "biomarker_family": infer_biomarker_family(combined_text),
                    "model_system_or_population": org_name or "funded_research_program",
                    "result_direction": "not_yet_known",
                    "off_patent_status": "not_applicable",
                    "sponsor_type": infer_organization_sponsor_type(org_name, org_type),
                    "phase_or_study_design": "grant_project",
                    "year": int(fiscal_year) if fiscal_year else 2026,
                    "extraction_method": "api_structured",
                    "provenance_note": (
                        f"NIH RePORTER project search term={term}; "
                        f"organization={org_name or 'unknown'}; "
                        f"agency_ic={agency_names or 'unknown'}"
                    ),
                }
            )
            seen_ids.add(record_id)
            if len(rows) >= max_records:
                return rows[:max_records]

    return rows[:max_records]


def fetch_nih_reporter_publication_pmids(manifest: dict, grant_rows: list[dict]) -> list[str]:
    nih_config = manifest["source_queries"]["nih_reporter"]
    sample_limit = int(nih_config.get("publication_link_sample_limit_per_core_project", 3))
    pmids: list[str] = []
    for grant_row in grant_rows:
        core_project_num = derive_core_project_num(grant_row["source_record_id"])
        response = nih_publications_search(core_project_num, sample_limit)
        for item in response.get("results", []) or []:
            pmid = normalize_text(item.get("pmid", ""))
            if pmid:
                pmids.append(pmid)
    return dedupe_preserve_order(pmids)


def fetch_openfda_label_rows(manifest: dict, max_records: int) -> list[dict]:
    openfda_config = manifest["source_queries"]["openfda"]
    interventions = list(openfda_config.get("seed_interventions", []))
    rows: list[dict] = []

    for spec in interventions:
        if len(rows) >= max_records:
            break

        search = str(spec["label_query"])
        url = openfda_url("drug/label", search, limit=1)
        response = fetch_json(url)
        results = response.get("results", []) or []
        if not results:
            continue

        item = results[0]
        openfda = item.get("openfda", {}) or {}
        brand_name = normalize_text((openfda.get("brand_name") or [""])[0])
        generic_name = normalize_text((openfda.get("generic_name") or [""])[0])
        manufacturer = normalize_text((openfda.get("manufacturer_name") or [""])[0])
        indications = normalize_text((item.get("indications_and_usage") or [""])[0])
        canonical_name = normalize_text(spec["canonical_entity_name"])
        combined_text = join_text_parts([canonical_name, brand_name, generic_name, indications])

        rows.append(
            {
                "record_id": f"openfda:label:{item['id']}",
                "entity_type": "intervention",
                "canonical_entity_name": canonical_name,
                "disease_scope": str(spec["disease_scope"]),
                "source_system": "openfda",
                "source_record_id": str(item["id"]),
                "source_url": url,
                "record_title": f"{brand_name or canonical_name} label",
                "evidence_role": "drug_label",
                "intervention_or_assay_type": infer_intervention_or_assay_type(combined_text),
                "biomarker_family": infer_biomarker_family(combined_text),
                "model_system_or_population": "fda_label_population",
                "result_direction": "neutral_or_descriptive",
                "off_patent_status": str(spec["off_patent_status"]),
                "sponsor_type": infer_organization_sponsor_type(manufacturer, "industry"),
                "phase_or_study_design": "regulatory_label",
                "year": extract_year(item.get("effective_time", ""), fallback=CURRENT_YEAR),
                "extraction_method": "api_structured",
                "provenance_note": (
                    f"openFDA drug/label query={search}; "
                    f"brand={brand_name or 'unknown'}; "
                    f"manufacturer={manufacturer or 'unknown'}"
                ),
            }
        )

    return rows


def fetch_openfda_event_rows(manifest: dict, max_records: int) -> list[dict]:
    openfda_config = manifest["source_queries"]["openfda"]
    interventions = list(openfda_config.get("seed_interventions", []))
    top_reaction_limit = int(openfda_config.get("top_reaction_limit", 2))
    rows: list[dict] = []

    for spec in interventions:
        if len(rows) >= max_records:
            break

        canonical_name = normalize_text(spec["canonical_entity_name"])
        event_search_term = str(spec["event_search_term"])
        search = f'patient.drug.medicinalproduct:"{event_search_term}"'
        url = openfda_url(
            "drug/event",
            search,
            limit=min(top_reaction_limit, max_records - len(rows)),
            count_field="patient.reaction.reactionmeddrapt.exact",
        )
        response = fetch_json(url)
        for result in response.get("results", []) or []:
            reaction_term = normalize_text(result.get("term", ""))
            reaction_count = int(result.get("count", 0))
            if not reaction_term:
                continue
            combined_text = join_text_parts([canonical_name, reaction_term])
            rows.append(
                {
                    "record_id": f"openfda:event:{slugify(canonical_name)}:{slugify(reaction_term)}",
                    "entity_type": "regulatory_signal",
                    "canonical_entity_name": canonical_name,
                    "disease_scope": str(spec["disease_scope"]),
                    "source_system": "openfda",
                    "source_record_id": f"{slugify(canonical_name)}:{slugify(reaction_term)}",
                    "source_url": url,
                    "record_title": f"{canonical_name} adverse-event signal: {reaction_term}",
                    "evidence_role": "adverse_event_signal",
                    "intervention_or_assay_type": infer_intervention_or_assay_type(combined_text),
                    "biomarker_family": infer_biomarker_family(combined_text),
                    "model_system_or_population": "postmarketing_spontaneous_reports",
                    "result_direction": "neutral_or_descriptive",
                    "off_patent_status": str(spec["off_patent_status"]),
                    "sponsor_type": "industry",
                    "phase_or_study_design": "aggregated_adverse_event_signal",
                    "year": CURRENT_YEAR,
                    "extraction_method": "api_structured",
                    "provenance_note": (
                        f"openFDA drug/event aggregate query={search}; "
                        f"top_reaction={reaction_term}; count={reaction_count}"
                    ),
                }
            )
            if len(rows) >= max_records:
                break

    return rows


def fetch_targeted_clinicaltrials_rows(manifest: dict) -> list[dict]:
    clinicaltrials_config = manifest["source_queries"]["clinicaltrials_gov"]
    per_intervention_max = int(
        clinicaltrials_config.get("candidate_follow_on_per_intervention_max", 0)
    )
    if per_intervention_max <= 0:
        return []

    tracked = [
        item
        for item in manifest["tracked_interventions"]
        if "clinicaltrials_gov" in set(item.get("preferred_source_systems", []))
        and item.get("alias_terms")
    ]
    rows: list[dict] = []
    for item in tracked:
        alias_terms = dedupe_preserve_order([normalize_text(alias) for alias in item["alias_terms"]])
        if not alias_terms:
            continue
        expansion_limit = max(10, per_intervention_max * 6)
        ranked_candidates: list[tuple[int, str, str, dict, str]] = []
        seen_nct_ids: set[str] = set()
        condition_terms = targeted_clinicaltrials_conditions_for_scope(item["disease_scope"])
        for alias in alias_terms:
            alias_found = False
            for condition in condition_terms:
                payload = fetch_json(
                    clinicaltrials_url_for_condition_and_term(
                        condition, alias, expansion_limit
                    )
                )
                provenance_note = (
                    f"ClinicalTrials.gov v2 targeted intervention query using query.cond={condition}; query.term={alias}"
                )
                for study in payload.get("studies", []):
                    nct_id = normalize_text(
                        study.get("protocolSection", {})
                        .get("identificationModule", {})
                        .get("nctId", "")
                    )
                    if not nct_id or nct_id in seen_nct_ids:
                        continue
                    row = build_clinicaltrials_row(
                        study,
                        provenance_note=provenance_note,
                    )
                    if row is None:
                        continue
                    alias_found = True
                    score, title_lower, _ = score_targeted_clinicaltrials_study(item, study)
                    ranked_candidates.append((score, title_lower, nct_id, study, provenance_note))
                    seen_nct_ids.add(nct_id)
            if alias_found:
                continue

            payload = fetch_json(clinicaltrials_url_for_term(alias, expansion_limit))
            provenance_note = (
                f"ClinicalTrials.gov v2 targeted intervention query using query.term={alias}"
            )
            for study in payload.get("studies", []):
                nct_id = normalize_text(
                    study.get("protocolSection", {})
                    .get("identificationModule", {})
                    .get("nctId", "")
                )
                if not nct_id or nct_id in seen_nct_ids:
                    continue
                row = build_clinicaltrials_row(
                    study,
                    provenance_note=provenance_note,
                )
                if row is None:
                    continue
                score, title_lower, _ = score_targeted_clinicaltrials_study(item, study)
                ranked_candidates.append((score, title_lower, nct_id, study, provenance_note))
                seen_nct_ids.add(nct_id)

        ranked_candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        item_rows = 0
        for _, _, _, study, provenance_note in ranked_candidates:
            row = build_clinicaltrials_row(
                study,
                provenance_note=provenance_note,
            )
            if row is None:
                continue
            rows.append(row)
            item_rows += 1
            if item_rows >= per_intervention_max:
                break
    return rows


def dedupe_rows_by_record_id(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        record_id = row["record_id"]
        if record_id in seen:
            continue
        seen.add(record_id)
        deduped.append(row)
    return deduped


def validate_rows(rows: list[dict], row_schema: dict) -> None:
    for row in rows:
        jsonschema.validate(instance=row, schema=row_schema)


def build_entity_groups(rows: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for row in rows:
        entity_key = slugify(row["canonical_entity_name"])
        group = groups.setdefault(
            entity_key,
            {
                "entity_key": entity_key,
                "display_name": row["canonical_entity_name"],
                "record_ids": [],
                "source_systems": set(),
                "evidence_roles": set(),
                "disease_scopes": set(),
                "intervention_or_assay_types": set(),
            },
        )
        group["record_ids"].append(row["record_id"])
        group["source_systems"].add(row["source_system"])
        group["evidence_roles"].add(row["evidence_role"])
        group["disease_scopes"].add(row["disease_scope"])
        group["intervention_or_assay_types"].add(row["intervention_or_assay_type"])

    entity_groups = []
    for group in groups.values():
        entity_groups.append(
            {
                "entity_key": group["entity_key"],
                "display_name": group["display_name"],
                "record_count": len(group["record_ids"]),
                "record_ids": sorted(group["record_ids"]),
                "source_systems": sorted(group["source_systems"]),
                "evidence_roles": sorted(group["evidence_roles"]),
                "disease_scopes": sorted(group["disease_scopes"]),
                "intervention_or_assay_types": sorted(group["intervention_or_assay_types"]),
            }
        )
    entity_groups.sort(key=lambda item: (-item["record_count"], item["display_name"].lower()))
    return entity_groups


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Cannot write empty seed dataset.")
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    source_counts = dict(sorted(Counter(row["source_system"] for row in rows).items()))
    entity_groups = build_entity_groups(rows)
    payload = {
        "dataset_id": "alzheimers_public_record_seed_v0",
        "row_count": len(rows),
        "sources_present": sorted({row["source_system"] for row in rows}),
        "source_counts": source_counts,
        "entity_group_count": len(entity_groups),
        "entity_groups": entity_groups,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_rows(
    manifest: dict,
    clinicaltrials_max: int,
    pubmed_max: int,
    pmc_open_access_max: int,
    nih_reporter_max: int,
    openfda_label_max: int,
    openfda_event_max: int,
) -> list[dict]:
    rows = []
    rows.extend(fetch_clinicaltrials_rows(manifest, clinicaltrials_max))
    rows.extend(fetch_targeted_clinicaltrials_rows(manifest))
    pmc_rows, pmc_linked_pmids = fetch_pmc_open_access_rows(manifest, pmc_open_access_max)
    grant_rows = fetch_nih_reporter_rows(manifest, nih_reporter_max)
    nih_linked_pmids = fetch_nih_reporter_publication_pmids(manifest, grant_rows)
    base_pubmed_ids = fetch_pubmed_seed_ids(manifest, pubmed_max)
    targeted_pubmed_ids = fetch_targeted_pubmed_ids(manifest)
    all_pubmed_ids = dedupe_preserve_order(
        base_pubmed_ids + pmc_linked_pmids + nih_linked_pmids + targeted_pubmed_ids
    )
    rows.extend(
        fetch_pubmed_rows_from_ids(
            all_pubmed_ids,
            base_query_ids=set(base_pubmed_ids),
            pmc_linked_ids=set(pmc_linked_pmids),
            nih_linked_ids=set(nih_linked_pmids),
            targeted_linked_ids=set(targeted_pubmed_ids),
        )
    )
    rows.extend(pmc_rows)
    rows.extend(grant_rows)
    rows.extend(fetch_openfda_label_rows(manifest, openfda_label_max))
    rows.extend(fetch_openfda_event_rows(manifest, openfda_event_max))
    rows = dedupe_rows_by_record_id(rows)
    rows.sort(key=lambda row: (row["source_system"], row["record_id"]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clinicaltrials-max",
        type=int,
        default=12,
        help="Maximum number of ClinicalTrials.gov rows to include.",
    )
    parser.add_argument(
        "--pubmed-max",
        type=int,
        default=12,
        help="Maximum number of PubMed rows to include.",
    )
    parser.add_argument(
        "--pmc-open-access-max",
        type=int,
        default=8,
        help="Maximum number of PMC Open Access rows to include.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=REPO_ROOT / "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.csv",
        help="Path for the normalized CSV output.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=REPO_ROOT / "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json",
        help="Path for the JSON output.",
    )
    parser.add_argument(
        "--nih-reporter-max",
        type=int,
        default=8,
        help="Maximum number of NIH RePORTER grant rows to include.",
    )
    parser.add_argument(
        "--openfda-label-max",
        type=int,
        default=7,
        help="Maximum number of openFDA label rows to include.",
    )
    parser.add_argument(
        "--openfda-event-max",
        type=int,
        default=14,
        help="Maximum number of openFDA adverse-event signal rows to include.",
    )
    args = parser.parse_args()

    manifest = load_yaml(
        REPO_ROOT / "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml"
    )
    row_schema = load_schema(REPO_ROOT / "schemas/alzheimers-public-record-row-v0.yaml")
    rows = build_rows(
        manifest,
        args.clinicaltrials_max,
        args.pubmed_max,
        args.pmc_open_access_max,
        args.nih_reporter_max,
        args.openfda_label_max,
        args.openfda_event_max,
    )
    validate_rows(rows, row_schema)
    write_csv(rows, args.output_csv)
    write_json(rows, args.output_json)

    print("PUBLIC RECORD SEED DATASET BUILT")
    print(f"- rows: {len(rows)}")
    print(f"- clinicaltrials_gov rows: {sum(1 for row in rows if row['source_system'] == 'clinicaltrials_gov')}")
    print(f"- pubmed rows: {sum(1 for row in rows if row['source_system'] == 'pubmed')}")
    print(f"- pmc_open_access_subset rows: {sum(1 for row in rows if row['source_system'] == 'pmc_open_access_subset')}")
    print(f"- nih_reporter rows: {sum(1 for row in rows if row['source_system'] == 'nih_reporter')}")
    print(f"- openfda rows: {sum(1 for row in rows if row['source_system'] == 'openfda')}")
    print(f"- csv: {display_path(args.output_csv)}")
    print(f"- json: {display_path(args.output_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
