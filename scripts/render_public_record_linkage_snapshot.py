#!/usr/bin/env python3
"""Render a linkage snapshot over the public-record seed dataset."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_JSON_PATH = (
    REPO_ROOT / "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json"
)
QUERY_MANIFEST_PATH = (
    REPO_ROOT / "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-linkage-snapshot-v0.json"
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at {path}")
    return data


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at {path}")
    return data


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "alzheimers-open-intelligence/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "alzheimers-open-intelligence/0.1",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_text(value).lower()).strip("_")


def pubmed_esummary_url(ids: list[str]) -> str:
    encoded_ids = urllib.parse.quote(",".join(ids))
    return (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pubmed&retmode=json&id={encoded_ids}"
    )


def fetch_pubmed_summaries(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    summary = fetch_json(pubmed_esummary_url(ids))
    results = summary.get("result", {})
    return {str(uid): results.get(uid, {}) for uid in results.get("uids", [])}


def extract_pmid_from_provenance(note: str) -> str:
    match = re.search(r"\bpmid=(\d+)\b", str(note or ""))
    return match.group(1) if match else ""


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


def collect_intervention_aliases(seed_data: dict, manifest: dict) -> list[dict]:
    tracked_interventions = [
        item for item in manifest["tracked_interventions"] if item["source_mode"] == "exact_anchor"
    ]
    label_rows = [
        row
        for row in seed_data["rows"]
        if row["source_system"] == "openfda" and row["evidence_role"] == "drug_label"
    ]
    label_aliases_by_canonical: dict[str, set[str]] = {}
    for row in label_rows:
        canonical = normalize_text(row["canonical_entity_name"])
        label_title = normalize_text(row["record_title"])
        alias = normalize_text(re.sub(r"\s+label$", "", label_title, flags=re.IGNORECASE))
        if alias:
            label_aliases_by_canonical.setdefault(canonical, set()).add(alias)

    clusters = []
    for spec in tracked_interventions:
        canonical = normalize_text(spec["canonical_entity_name"])
        aliases = {
            canonical,
            *[normalize_text(alias) for alias in spec.get("alias_terms", [])],
            *label_aliases_by_canonical.get(canonical, set()),
        }
        aliases = {alias for alias in aliases if alias}
        clusters.append(
            {
                "canonical_entity_name": canonical,
                "alias_terms": sorted(aliases),
            }
        )
    return clusters


def match_row_to_aliases(row: dict, aliases: list[str]) -> str | None:
    canonical = normalize_text(row["canonical_entity_name"]).lower()
    title = normalize_text(row["record_title"]).lower()
    alias_patterns = [rf"\b{re.escape(alias.lower())}\b" for alias in aliases]

    for alias in aliases:
        lowered = alias.lower()
        if canonical == lowered:
            return "exact_canonical"
    for pattern in alias_patterns:
        if re.search(pattern, title):
            return "title_alias"
    for pattern in alias_patterns:
        if re.search(pattern, canonical):
            return "canonical_alias"
    return None


def build_exact_pubmed_pmc_links(seed_data: dict) -> list[dict]:
    pubmed_rows_by_pmid = {
        str(row["source_record_id"]): row
        for row in seed_data["rows"]
        if row["source_system"] == "pubmed"
    }
    links = []
    for row in seed_data["rows"]:
        if row["source_system"] != "pmc_open_access_subset":
            continue
        pmid = extract_pmid_from_provenance(row["provenance_note"])
        pubmed_row = pubmed_rows_by_pmid.get(pmid)
        if not pmid:
            continue
        links.append(
            {
                "pmid": pmid,
                "pmcid": str(row["source_record_id"]),
                "pubmed_record_id": pubmed_row["record_id"] if pubmed_row else f"pubmed:{pmid}",
                "pubmed_row_present_in_seed": pubmed_row is not None,
                "pmc_record_id": row["record_id"],
                "title": pubmed_row["record_title"] if pubmed_row else row["record_title"],
            }
        )
    links.sort(key=lambda item: item["pmcid"])
    return links


def build_intervention_clusters(seed_data: dict, manifest: dict) -> list[dict]:
    clusters = []
    alias_specs = collect_intervention_aliases(seed_data, manifest)
    rows = seed_data["rows"]
    for spec in alias_specs:
        matched_records = []
        seen_record_ids: set[str] = set()
        for row in rows:
            match_type = match_row_to_aliases(row, spec["alias_terms"])
            if match_type is None or row["record_id"] in seen_record_ids:
                continue
            matched_records.append(
                {
                    "record_id": row["record_id"],
                    "source_system": row["source_system"],
                    "evidence_role": row["evidence_role"],
                    "record_title": row["record_title"],
                    "match_type": match_type,
                }
            )
            seen_record_ids.add(row["record_id"])

        matched_records.sort(key=lambda item: (item["source_system"], item["record_id"]))
        if not matched_records:
            continue
        clusters.append(
            {
                "canonical_entity_name": spec["canonical_entity_name"],
                "alias_terms": spec["alias_terms"],
                "linked_record_count": len(matched_records),
                "source_systems": sorted({item["source_system"] for item in matched_records}),
                "evidence_roles": sorted({item["evidence_role"] for item in matched_records}),
                "matched_records": matched_records,
            }
        )
    clusters.sort(key=lambda item: (-item["linked_record_count"], item["canonical_entity_name"].lower()))
    return clusters


def build_grant_publication_bridges(seed_data: dict, manifest: dict) -> tuple[list[dict], int]:
    sample_limit = int(
        manifest["source_queries"]["nih_reporter"].get(
            "publication_link_sample_limit_per_core_project", 3
        )
    )
    pubmed_rows_by_pmid = {
        str(row["source_record_id"]): row
        for row in seed_data["rows"]
        if row["source_system"] == "pubmed"
    }
    grant_rows = [
        row for row in seed_data["rows"] if row["source_system"] == "nih_reporter"
    ]

    publication_search_results = []
    pmids_to_fetch: set[str] = set()
    for grant_row in grant_rows:
        core_project_num = derive_core_project_num(grant_row["source_record_id"])
        response = nih_publications_search(core_project_num, sample_limit)
        sampled_links = response.get("results", []) or []
        publication_search_results.append(
            {
                "grant_row": grant_row,
                "core_project_num": core_project_num,
                "linked_publication_count": int(response.get("meta", {}).get("total", 0)),
                "sampled_links": sampled_links,
            }
        )
        for item in sampled_links:
            pmid = normalize_text(item.get("pmid", ""))
            if pmid:
                pmids_to_fetch.add(pmid)

    pubmed_summaries = fetch_pubmed_summaries(sorted(pmids_to_fetch))
    bridges = []
    sampled_link_total = 0
    for result in publication_search_results:
        sampled_publication_links = []
        for item in result["sampled_links"]:
            pmid = normalize_text(item.get("pmid", ""))
            if not pmid:
                continue
            summary = pubmed_summaries.get(pmid, {})
            pubmed_row = pubmed_rows_by_pmid.get(pmid)
            sampled_publication_links.append(
                {
                    "pmid": pmid,
                    "latest_application_id": item.get("applid", ""),
                    "pubmed_record_id": pubmed_row["record_id"] if pubmed_row else f"pubmed:{pmid}",
                    "pubmed_row_present_in_seed": pubmed_row is not None,
                    "publication_title": normalize_text(summary.get("title", "")) or f"PMID {pmid}",
                    "publication_year": int(
                        re.search(r"(19|20)\d{2}", normalize_text(summary.get("pubdate", "")) or "0").group(0)
                    )
                    if re.search(r"(19|20)\d{2}", normalize_text(summary.get("pubdate", "")) or "")
                    else 1900,
                }
            )
        sampled_link_total += len(sampled_publication_links)
        bridges.append(
            {
                "grant_record_id": result["grant_row"]["record_id"],
                "core_project_num": result["core_project_num"],
                "linked_publication_count": result["linked_publication_count"],
                "sampled_link_count": len(sampled_publication_links),
                "sampled_publication_links": sampled_publication_links,
            }
        )
    bridges.sort(key=lambda item: (-item["linked_publication_count"], item["core_project_num"]))
    return bridges, sampled_link_total


def build_multi_source_entity_groups(seed_data: dict) -> list[dict]:
    groups = []
    for group in seed_data.get("entity_groups", []):
        source_systems = list(group.get("source_systems", []))
        if len(source_systems) < 2:
            continue
        groups.append(
            {
                "display_name": group["display_name"],
                "record_count": int(group["record_count"]),
                "source_systems": source_systems,
                "evidence_roles": list(group.get("evidence_roles", [])),
            }
        )
    groups.sort(key=lambda item: (-item["record_count"], item["display_name"].lower()))
    return groups


def build_snapshot() -> dict:
    seed_data = load_json(SEED_JSON_PATH)
    manifest = load_yaml(QUERY_MANIFEST_PATH)
    exact_pubmed_pmc_links = build_exact_pubmed_pmc_links(seed_data)
    grant_publication_bridges, sampled_grant_publication_link_count = (
        build_grant_publication_bridges(seed_data, manifest)
    )
    grants_with_linked_publications_count = sum(
        1 for item in grant_publication_bridges if item["linked_publication_count"] > 0
    )
    intervention_clusters = build_intervention_clusters(seed_data, manifest)
    cross_source_intervention_cluster_count = sum(
        1 for cluster in intervention_clusters if len(cluster["source_systems"]) >= 2
    )
    multi_source_entity_groups = build_multi_source_entity_groups(seed_data)
    return {
        "snapshot_id": "alzheimers_public_record_linkage_snapshot_v0",
        "generated_from_dataset_id": seed_data["dataset_id"],
        "row_count": int(seed_data["row_count"]),
        "entity_group_count": int(seed_data.get("entity_group_count", 0)),
        "exact_pubmed_pmc_link_count": len(exact_pubmed_pmc_links),
        "exact_pubmed_pmc_links": exact_pubmed_pmc_links,
        "grant_publication_bridge_count": len(grant_publication_bridges),
        "grants_with_linked_publications_count": grants_with_linked_publications_count,
        "sampled_grant_publication_link_count": sampled_grant_publication_link_count,
        "grant_publication_bridges": grant_publication_bridges,
        "intervention_cluster_count": len(intervention_clusters),
        "cross_source_intervention_cluster_count": cross_source_intervention_cluster_count,
        "intervention_clusters": intervention_clusters,
        "multi_source_entity_group_count": len(multi_source_entity_groups),
        "multi_source_entity_groups": multi_source_entity_groups,
        "repo_paths": {
            "seed_json": "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json",
            "query_manifest": "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml",
            "linkage_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-linkage-snapshot-v0.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    snapshot = build_snapshot()
    text = json.dumps(snapshot, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text + "\n", encoding="utf-8")
    print(f"WROTE {args.output.relative_to(REPO_ROOT)}")
    print(f"- exact_pubmed_pmc_link_count: {snapshot['exact_pubmed_pmc_link_count']}")
    print(f"- grant_publication_bridge_count: {snapshot['grant_publication_bridge_count']}")
    print(
        f"- grants_with_linked_publications_count: "
        f"{snapshot['grants_with_linked_publications_count']}"
    )
    print(
        f"- sampled_grant_publication_link_count: "
        f"{snapshot['sampled_grant_publication_link_count']}"
    )
    print(f"- intervention_cluster_count: {snapshot['intervention_cluster_count']}")
    print(
        f"- cross_source_intervention_cluster_count: "
        f"{snapshot['cross_source_intervention_cluster_count']}"
    )
    print(f"- multi_source_entity_group_count: {snapshot['multi_source_entity_group_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
