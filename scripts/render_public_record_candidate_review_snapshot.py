#!/usr/bin/env python3
"""Render a review-oriented snapshot for ranked public-record candidate links."""

from __future__ import annotations

import argparse
import json
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
CANDIDATE_LINKAGE_SNAPSHOT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-linkage-snapshot-v0.json"
)
QUERY_MANIFEST_PATH = (
    REPO_ROOT / "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml"
)
DEFAULT_OUTPUT_JSON_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-snapshot-v0.json"
)
DEFAULT_OUTPUT_REPORT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-report-v0.md"
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


def support_status(candidate_link_count: int, source_systems: list[str]) -> str:
    if candidate_link_count <= 1 and len(source_systems) <= 1:
        return "single_record_single_source"
    if len(source_systems) <= 1:
        return "multi_record_single_source"
    return "multi_source"


def exact_scope_support(cluster: dict) -> dict:
    exact_links = [
        item for item in cluster["candidate_links"] if item["disease_scope"] == cluster["disease_scope"]
    ]
    return {
        "exact_scope_link_count": len(exact_links),
        "exact_scope_source_systems": sorted({item["source_system"] for item in exact_links}),
        "exact_scope_evidence_roles": sorted({item["evidence_role"] for item in exact_links}),
    }


def derive_review_flags(cluster: dict) -> list[str]:
    candidate_links = cluster["candidate_links"]
    flags: list[str] = []
    score_component_union = {
        component for item in candidate_links for component in item["score_components"]
    }
    evidence_roles = {item["evidence_role"] for item in candidate_links}
    source_systems = set(cluster["source_systems"])

    if cluster["candidate_link_count"] == 1:
        flags.append("single_record_only")
    if len(source_systems) == 1:
        flags.append("single_source_only")
    if len(evidence_roles) == 1:
        flags.append("single_evidence_role_only")
    if "disease_scope_adjacent" in score_component_union:
        flags.append("adjacent_scope_match_present")
    if (
        "canonical_alias_partial" in score_component_union
        and "canonical_alias_exact" not in score_component_union
        and "title_alias" not in score_component_union
    ):
        flags.append("alias_is_partial_only")
    if (
        "disease_scope_exact" not in score_component_union
        and "disease_scope_adjacent" not in score_component_union
    ):
        flags.append("disease_scope_not_explicit_in_linked_records")
    if "preferred_source_system" not in score_component_union:
        flags.append("outside_preferred_source_systems")

    return flags


def review_priority(top_score: float, flags: list[str]) -> str:
    if top_score >= 0.90 and any(
        flag in flags
        for flag in [
            "single_record_only",
            "single_source_only",
            "adjacent_scope_match_present",
            "alias_is_partial_only",
        ]
    ):
        return "high"
    if top_score >= 0.75:
        return "medium"
    return "low"


def promotion_readiness(cluster: dict, flags: list[str], top_score: float) -> str:
    exact_support = exact_scope_support(cluster)
    if (
        len(exact_support["exact_scope_source_systems"]) >= 2
        and exact_support["exact_scope_link_count"] >= 2
        and "alias_is_partial_only" not in flags
        and "disease_scope_not_explicit_in_linked_records" not in flags
        and "publication_record" in exact_support["exact_scope_evidence_roles"]
        and "trial_registration" in exact_support["exact_scope_evidence_roles"]
    ):
        return "ready_for_exact_anchor_review"
    if top_score >= 0.90:
        return "watch_for_second_source"
    return "hold_as_candidate"


def recommended_next_step(flags: list[str], readiness: str) -> str:
    if readiness == "ready_for_exact_anchor_review":
        return "Review whether the candidate has earned promotion into the exact-anchor layer."
    if "adjacent_scope_match_present" in flags:
        return "Check whether the intervention should remain adjacent-scope only or can earn a direct Alzheimer's claim."
    if "disease_scope_not_explicit_in_linked_records" in flags:
        return "Check whether the linked records actually support an Alzheimer's-specific claim before promotion."
    if "single_source_only" in flags:
        return "Find a second independent public source before considering promotion."
    if "alias_is_partial_only" in flags:
        return "Add a cleaner intervention alias or an exact-match record before promotion."
    return "Keep the candidate live and monitor for a second public surface."


def build_review_items(candidate_snapshot: dict) -> list[dict]:
    items = []
    for cluster in candidate_snapshot["candidate_clusters"]:
        candidate_links = cluster["candidate_links"]
        exemplar = candidate_links[0]
        exact_support = exact_scope_support(cluster)
        score_component_union = sorted(
            {component for item in candidate_links for component in item["score_components"]}
        )
        flags = derive_review_flags(cluster)
        priority = review_priority(exemplar["candidate_score"], flags)
        readiness = promotion_readiness(
            cluster,
            flags,
            exemplar["candidate_score"],
        )
        items.append(
            {
                "canonical_entity_name": cluster["canonical_entity_name"],
                "intervention_family": cluster["intervention_family"],
                "disease_scope": cluster["disease_scope"],
                "off_patent_status": cluster["off_patent_status"],
                "source_mode": cluster["source_mode"],
                "exact_anchor_present": cluster["exact_anchor_present"],
                "candidate_link_count": cluster["candidate_link_count"],
                "source_systems": cluster["source_systems"],
                "evidence_roles": sorted({item["evidence_role"] for item in candidate_links}),
                "support_status": support_status(
                    cluster["candidate_link_count"], cluster["source_systems"]
                ),
                "exact_scope_link_count": exact_support["exact_scope_link_count"],
                "exact_scope_source_systems": exact_support["exact_scope_source_systems"],
                "exact_scope_evidence_roles": exact_support["exact_scope_evidence_roles"],
                "top_candidate_score": exemplar["candidate_score"],
                "top_candidate_tier": exemplar["candidate_tier"],
                "exemplar_record_id": exemplar["record_id"],
                "exemplar_record_title": exemplar["record_title"],
                "score_component_union": score_component_union,
                "review_flags": flags,
                "review_priority": priority,
                "promotion_readiness": readiness,
                "recommended_next_step": recommended_next_step(flags, readiness),
            }
        )

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    readiness_rank = {
        "ready_for_exact_anchor_review": 0,
        "watch_for_second_source": 1,
        "hold_as_candidate": 2,
    }
    items.sort(
        key=lambda item: (
            priority_rank[item["review_priority"]],
            readiness_rank[item["promotion_readiness"]],
            -item["top_candidate_score"],
            item["canonical_entity_name"].lower(),
        )
    )
    return items


def build_snapshot() -> dict:
    seed_data = load_json(SEED_JSON_PATH)
    exact_snapshot = load_json(EXACT_LINKAGE_SNAPSHOT_PATH)
    candidate_snapshot = load_json(CANDIDATE_LINKAGE_SNAPSHOT_PATH)
    manifest = load_yaml(QUERY_MANIFEST_PATH)
    tracked_interventions = [
        item for item in manifest["tracked_interventions"] if item["source_mode"] == "candidate_only"
    ]
    review_items = build_review_items(candidate_snapshot)
    return {
        "snapshot_id": "alzheimers_public_record_candidate_review_snapshot_v0",
        "generated_from_dataset_id": seed_data["dataset_id"],
        "exact_linkage_snapshot_id": exact_snapshot["snapshot_id"],
        "candidate_linkage_snapshot_id": candidate_snapshot["snapshot_id"],
        "tracked_intervention_count": len(tracked_interventions),
        "review_item_count": len(review_items),
        "high_priority_review_count": sum(
            1 for item in review_items if item["review_priority"] == "high"
        ),
        "promotion_watchlist_count": sum(
            1
            for item in review_items
            if item["promotion_readiness"] == "watch_for_second_source"
        ),
        "ready_for_exact_anchor_review_count": sum(
            1
            for item in review_items
            if item["promotion_readiness"] == "ready_for_exact_anchor_review"
        ),
        "review_items": review_items,
        "repo_paths": {
            "seed_json": "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json",
            "exact_linkage_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-linkage-snapshot-v0.json",
            "candidate_linkage_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-candidate-linkage-snapshot-v0.json",
            "query_manifest": "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml",
            "candidate_review_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-snapshot-v0.json",
            "candidate_review_report": "datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-report-v0.md",
        },
    }


def render_markdown(snapshot: dict) -> str:
    lines = [
        "# Candidate Linkage Review Report v0",
        "",
        "This report keeps ranked candidate links clearly separate from exact bridges.",
        "The goal is to show which candidate intervention clusters look promising,",
        "what still makes them brittle, and what the next review move should be.",
        "",
        "## Current Surface",
        "",
        f"- Review items: {snapshot['review_item_count']}",
        f"- High-priority review items: {snapshot['high_priority_review_count']}",
        f"- Promotion watchlist items: {snapshot['promotion_watchlist_count']}",
        f"- Ready for exact-anchor review: {snapshot['ready_for_exact_anchor_review_count']}",
        "",
        "## Review Queue",
        "",
    ]

    for item in snapshot["review_items"]:
        flags = ", ".join(item["review_flags"]) or "none"
        score_components = ", ".join(item["score_component_union"]) or "none"
        lines.extend(
            [
                f"### {item['canonical_entity_name']}",
                "",
                f"- Exemplar record: `{item['exemplar_record_id']}`",
                f"- Exemplar title: {item['exemplar_record_title']}",
                f"- Support status: `{item['support_status']}`",
                f"- Exact-scope support count: `{item['exact_scope_link_count']}`",
                f"- Exact-scope source systems: {', '.join(item['exact_scope_source_systems']) or 'none'}",
                f"- Exact-scope evidence roles: {', '.join(item['exact_scope_evidence_roles']) or 'none'}",
                f"- Top candidate score: `{item['top_candidate_score']}` (`{item['top_candidate_tier']}` tier)",
                f"- Review priority: `{item['review_priority']}`",
                f"- Promotion readiness: `{item['promotion_readiness']}`",
                f"- Source systems: {', '.join(item['source_systems'])}",
                f"- Evidence roles: {', '.join(item['evidence_roles'])}",
                f"- Score components: {score_components}",
                f"- Review flags: {flags}",
                f"- Recommended next step: {item['recommended_next_step']}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON_PATH)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    args = parser.parse_args()

    snapshot = build_snapshot()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_report.write_text(render_markdown(snapshot), encoding="utf-8")

    print(f"WROTE {args.output_json.relative_to(REPO_ROOT)}")
    print(f"WROTE {args.output_report.relative_to(REPO_ROOT)}")
    print(f"- review_item_count: {snapshot['review_item_count']}")
    print(f"- high_priority_review_count: {snapshot['high_priority_review_count']}")
    print(f"- promotion_watchlist_count: {snapshot['promotion_watchlist_count']}")
    print(
        f"- ready_for_exact_anchor_review_count: {snapshot['ready_for_exact_anchor_review_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
