#!/usr/bin/env python3
"""Render a ranked candidate-linkage snapshot over the public-record seed dataset."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_JSON_PATH = (
    REPO_ROOT / "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json"
)
EXACT_LINKAGE_SNAPSHOT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-linkage-snapshot-v0.json"
)
QUERY_MANIFEST_PATH = (
    REPO_ROOT / "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-linkage-snapshot-v0.json"
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


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"\b{re.escape(alias.lower())}\b", text.lower()) is not None


def disease_alignment_score(expected_scope: str, row_scope: str) -> tuple[float, str | None]:
    if expected_scope == row_scope:
        return 0.10, "disease_scope_exact"
    pair = {expected_scope, row_scope}
    if pair == {"alzheimers_disease", "mild_cognitive_impairment"}:
        return 0.05, "disease_scope_adjacent"
    return 0.0, None


def candidate_tier(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


def build_exact_record_lookup(exact_snapshot: dict) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = {}
    for cluster in exact_snapshot.get("intervention_clusters", []):
        lookup[cluster["canonical_entity_name"]] = {
            item["record_id"] for item in cluster.get("matched_records", [])
        }
    return lookup


def score_candidate(tracked: dict, row: dict) -> tuple[float, list[str]]:
    aliases = [normalize_text(alias) for alias in tracked["alias_terms"]]
    canonical = normalize_text(row["canonical_entity_name"])
    title = normalize_text(row["record_title"])
    provenance = normalize_text(row["provenance_note"])

    score = 0.0
    components: list[str] = []

    if any(canonical.lower() == alias.lower() for alias in aliases):
        score += 0.55
        components.append("canonical_alias_exact")
    elif any(contains_alias(canonical, alias) for alias in aliases):
        score += 0.45
        components.append("canonical_alias_partial")

    if any(contains_alias(title, alias) for alias in aliases):
        score += 0.35
        components.append("title_alias")

    if any(contains_alias(provenance, alias) for alias in aliases):
        score += 0.15
        components.append("provenance_alias")

    if row["intervention_or_assay_type"] == tracked["intervention_family"]:
        score += 0.15
        components.append("intervention_family_alignment")

    disease_bonus, disease_tag = disease_alignment_score(
        tracked["disease_scope"], row["disease_scope"]
    )
    if disease_bonus:
        score += disease_bonus
        components.append(disease_tag)

    preferred_source_systems = set(tracked.get("preferred_source_systems", []))
    if row["source_system"] in preferred_source_systems:
        score += 0.05
        components.append("preferred_source_system")

    return min(score, 1.0), components


def build_candidate_clusters(seed_data: dict, exact_snapshot: dict, manifest: dict) -> list[dict]:
    exact_lookup = build_exact_record_lookup(exact_snapshot)
    tracked_interventions = [
        item for item in manifest["tracked_interventions"] if item["source_mode"] == "candidate_only"
    ]
    rows = seed_data["rows"]
    clusters = []

    for tracked in tracked_interventions:
        canonical_name = tracked["canonical_entity_name"]
        exact_linked_record_ids = exact_lookup.get(canonical_name, set())
        candidate_links = []
        for row in rows:
            if row["record_id"] in exact_linked_record_ids:
                continue
            score, components = score_candidate(tracked, row)
            if score < 0.55:
                continue
            candidate_links.append(
                {
                    "record_id": row["record_id"],
                    "source_system": row["source_system"],
                    "evidence_role": row["evidence_role"],
                    "record_title": row["record_title"],
                    "intervention_or_assay_type": row["intervention_or_assay_type"],
                    "disease_scope": row["disease_scope"],
                    "candidate_score": round(score, 3),
                    "candidate_tier": candidate_tier(score),
                    "score_components": components,
                }
            )

        candidate_links.sort(
            key=lambda item: (-item["candidate_score"], item["source_system"], item["record_id"])
        )
        if not candidate_links:
            continue
        clusters.append(
            {
                "canonical_entity_name": canonical_name,
                "intervention_family": tracked["intervention_family"],
                "disease_scope": tracked["disease_scope"],
                "off_patent_status": tracked["off_patent_status"],
                "source_mode": tracked["source_mode"],
                "alias_terms": tracked["alias_terms"],
                "exact_anchor_present": canonical_name in exact_lookup,
                "candidate_link_count": len(candidate_links),
                "source_systems": sorted({item["source_system"] for item in candidate_links}),
                "candidate_links": candidate_links[:10],
            }
        )

    clusters.sort(
        key=lambda item: (
            -item["candidate_link_count"],
            item["source_mode"] != "candidate_only",
            item["canonical_entity_name"].lower(),
        )
    )
    return clusters


def build_snapshot() -> dict:
    seed_data = load_json(SEED_JSON_PATH)
    exact_snapshot = load_json(EXACT_LINKAGE_SNAPSHOT_PATH)
    manifest = load_yaml(QUERY_MANIFEST_PATH)
    tracked_interventions = [
        item for item in manifest["tracked_interventions"] if item["source_mode"] == "candidate_only"
    ]
    candidate_clusters = build_candidate_clusters(seed_data, exact_snapshot, manifest)
    candidate_link_count = sum(item["candidate_link_count"] for item in candidate_clusters)
    return {
        "snapshot_id": "alzheimers_public_record_candidate_linkage_snapshot_v0",
        "generated_from_dataset_id": seed_data["dataset_id"],
        "exact_linkage_snapshot_id": exact_snapshot["snapshot_id"],
        "tracked_intervention_count": len(tracked_interventions),
        "candidate_cluster_count": len(candidate_clusters),
        "candidate_link_count": candidate_link_count,
        "candidate_clusters": candidate_clusters,
        "repo_paths": {
            "seed_json": "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json",
            "exact_linkage_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-linkage-snapshot-v0.json",
            "query_manifest": "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml",
            "candidate_linkage_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-candidate-linkage-snapshot-v0.json",
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
    print(f"- tracked_intervention_count: {snapshot['tracked_intervention_count']}")
    print(f"- candidate_cluster_count: {snapshot['candidate_cluster_count']}")
    print(f"- candidate_link_count: {snapshot['candidate_link_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
