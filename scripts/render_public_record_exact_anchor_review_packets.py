#!/usr/bin/env python3
"""Render exact-anchor review packets for promotion candidates."""

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
CANDIDATE_LINKAGE_SNAPSHOT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-linkage-snapshot-v0.json"
)
CANDIDATE_REVIEW_SNAPSHOT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-snapshot-v0.json"
)
PROMOTION_SNAPSHOT_PATH = (
    REPO_ROOT
    / "datasets/public-record-derived/linked/alzheimers-public-record-exact-anchor-promotion-snapshot-v0.json"
)
DEFAULT_REVIEWS_DIR = REPO_ROOT / "interventions/hypothesis-ledger/exact-anchor-reviews"


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


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def classify_link(candidate: dict, row: dict) -> tuple[bool, str | None]:
    if row["evidence_role"] not in {"trial_registration", "publication_record"}:
        return False, "evidence_role_not_eligible_for_exact_anchor_review"
    if row["disease_scope"] != candidate["disease_scope"]:
        return False, "disease_scope_not_exact_alzheimers_match"
    if (
        row["evidence_role"] == "publication_record"
        and row["intervention_or_assay_type"] != candidate["intervention_family"]
    ):
        return False, "publication_surface_not_family_aligned"
    return True, None


def caution_flags(review_item: dict, nonqualifying_records: list[dict], outcome: str) -> list[str]:
    flags = []
    if nonqualifying_records:
        flags.append("mixed_candidate_surface")
    if any(
        item["exclusion_reason"] == "disease_scope_not_exact_alzheimers_match"
        for item in nonqualifying_records
    ):
        flags.append("non_alzheimers_or_adjacent_records_present")
    if outcome == "defer_from_exact_anchor":
        flags.append("retain_candidate_only_status")
    if outcome == "promote_to_exact_anchor":
        flags.append("promotion_requires_manifest_and_exact-linkage_update")
    if "alias_is_partial_only" in review_item["review_flags"]:
        flags.append("alias_surface_still_partial_in_some_records")
    return flags


def decision_for_candidate(
    promotion_candidate: dict,
    review_item: dict,
    candidate_cluster: dict,
    rows_by_id: dict[str, dict],
) -> dict:
    qualifying_records = []
    nonqualifying_records = []
    for candidate_link in candidate_cluster["candidate_links"]:
        row = rows_by_id[candidate_link["record_id"]]
        qualifies, reason = classify_link(promotion_candidate, row)
        if qualifies:
            qualifying_records.append(candidate_link)
        else:
            nonqualifying_records.append(
                {
                    "record_id": candidate_link["record_id"],
                    "source_system": candidate_link["source_system"],
                    "evidence_role": candidate_link["evidence_role"],
                    "exclusion_reason": reason,
                }
            )

    qualifying_source_count = len({item["source_system"] for item in qualifying_records})
    qualifying_roles = {item["evidence_role"] for item in qualifying_records}
    if (
        qualifying_source_count >= 2
        and "publication_record" in qualifying_roles
        and "trial_registration" in qualifying_roles
    ):
        review_outcome = "promote_to_exact_anchor"
        decision_confidence = "medium"
        decision_summary = (
            "Promote into exact-anchor review pass. The qualifying support surface is "
            "multi-source and includes both AD-specific trial registration and AD-specific publication evidence."
        )
        rationale_points = [
            "The qualifying support surface spans both ClinicalTrials.gov and PubMed.",
            "The qualifying support includes at least one AD-specific trial-registration record and one AD-specific publication record.",
            "The candidate review layer has already cleared this intervention for exact-anchor review, and the detailed packet confirms that judgment on exact-scope records.",
        ]
        next_actions = [
            "Add this intervention to the exact-anchor review pass list in the tracked intervention manifest.",
            "Update the exact linkage layer so only the qualifying records are treated as exact-anchor support.",
            "Keep excluded or adjacent records visible in review notes, but do not let them silently widen the exact-anchor claim.",
        ]
    elif qualifying_source_count >= 1:
        review_outcome = "defer_from_exact_anchor"
        decision_confidence = "medium"
        decision_summary = (
            "Defer exact-anchor promotion. The current surface contains AD-relevant support, "
            "but the qualifying evidence is not yet strong enough across independent exact-scope sources."
        )
        rationale_points = [
            "The intervention has a meaningful candidate surface, but the exact-scope qualifying support is narrower than the broader candidate cluster suggests.",
            "Non-qualifying related records are present and should not be allowed to inflate the exact-anchor claim.",
            "The intervention should remain candidate-only until it earns stronger AD-specific publication or cross-source exact support.",
        ]
        next_actions = [
            "Keep the intervention in the candidate-only layer.",
            "Prioritize harvesting additional AD-specific publication or trial-result records before reopening promotion review.",
            "Use the non-qualifying record list to avoid accidentally counting adjacent or non-AD evidence as exact-anchor support.",
        ]
    else:
        review_outcome = "reject_from_exact_anchor"
        decision_confidence = "medium"
        decision_summary = (
            "Reject exact-anchor promotion for now. The promotion candidate does not have enough qualifying exact-scope support."
        )
        rationale_points = [
            "The current candidate surface does not contain enough qualifying exact-scope support records.",
            "Promotion would overstate the evidence surface relative to the actual public records in the seed.",
        ]
        next_actions = [
            "Leave the intervention out of the exact-anchor layer.",
            "Return to broader candidate harvesting only if a new high-quality public source appears.",
        ]

    return {
        "review_status": "completed",
        "review_outcome": review_outcome,
        "decision_confidence": decision_confidence,
        "decision_summary": decision_summary,
        "qualifying_records": qualifying_records,
        "nonqualifying_records": nonqualifying_records,
        "caution_flags": caution_flags(review_item, nonqualifying_records, review_outcome),
        "rationale_points": rationale_points,
        "next_actions": next_actions,
    }


def review_record_path(reviews_dir: Path, canonical_name: str) -> Path:
    return reviews_dir / "records" / f"{slugify(canonical_name)}-exact-anchor-review-v0.yaml"


def review_report_path(reviews_dir: Path, canonical_name: str) -> Path:
    return reviews_dir / "reports" / f"{slugify(canonical_name)}-exact-anchor-review-v0.md"


def build_review_record(
    reviews_dir: Path,
    promotion_candidate: dict,
    review_item: dict,
    candidate_cluster: dict,
    rows_by_id: dict[str, dict],
    promotion_snapshot: dict,
    candidate_review_snapshot: dict,
) -> dict:
    decision = decision_for_candidate(
        promotion_candidate, review_item, candidate_cluster, rows_by_id
    )
    record_path = review_record_path(reviews_dir, promotion_candidate["canonical_entity_name"])
    report_path = review_report_path(reviews_dir, promotion_candidate["canonical_entity_name"])
    return {
        "review_id": f"{slugify(promotion_candidate['canonical_entity_name'])}_exact_anchor_review_v0",
        "generated_from_dataset_id": promotion_snapshot["generated_from_dataset_id"],
        "promotion_snapshot_id": promotion_snapshot["snapshot_id"],
        "candidate_review_snapshot_id": candidate_review_snapshot["snapshot_id"],
        "canonical_entity_name": promotion_candidate["canonical_entity_name"],
        "review_status": decision["review_status"],
        "review_outcome": decision["review_outcome"],
        "decision_confidence": decision["decision_confidence"],
        "decision_summary": decision["decision_summary"],
        "intervention_family": promotion_candidate["intervention_family"],
        "disease_scope": promotion_candidate["disease_scope"],
        "off_patent_status": promotion_candidate["off_patent_status"],
        "source_systems": promotion_candidate["source_systems"],
        "evidence_roles": promotion_candidate["evidence_roles"],
        "support_status": promotion_candidate["support_status"],
        "exemplar_record_id": promotion_candidate["exemplar_record_id"],
        "exemplar_record_title": promotion_candidate["exemplar_record_title"],
        "qualifying_support_record_count": len(decision["qualifying_records"]),
        "qualifying_support_source_count": len(
            {item["source_system"] for item in decision["qualifying_records"]}
        ),
        "qualifying_support_record_ids": [
            item["record_id"] for item in decision["qualifying_records"]
        ],
        "nonqualifying_related_record_count": len(decision["nonqualifying_records"]),
        "nonqualifying_related_records": decision["nonqualifying_records"],
        "caution_flags": decision["caution_flags"],
        "rationale_points": decision["rationale_points"],
        "next_actions": decision["next_actions"],
        "repo_paths": {
            "review_record": str(record_path.relative_to(REPO_ROOT)),
            "review_report": str(report_path.relative_to(REPO_ROOT)),
            "promotion_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-exact-anchor-promotion-snapshot-v0.json",
            "candidate_review_snapshot": "datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-snapshot-v0.json",
        },
    }


def render_review_markdown(record: dict) -> str:
    lines = [
        f"# {record['canonical_entity_name']} Exact Anchor Review v0",
        "",
        f"- Outcome: `{record['review_outcome']}`",
        f"- Confidence: `{record['decision_confidence']}`",
        f"- Summary: {record['decision_summary']}",
        f"- Exemplar record: `{record['exemplar_record_id']}`",
        f"- Exemplar title: {record['exemplar_record_title']}",
        "",
        "## Support Surface",
        "",
        f"- Source systems: {', '.join(record['source_systems'])}",
        f"- Evidence roles: {', '.join(record['evidence_roles'])}",
        f"- Support status: `{record['support_status']}`",
        f"- Qualifying support record count: {record['qualifying_support_record_count']}",
        f"- Qualifying support source count: {record['qualifying_support_source_count']}",
        f"- Qualifying support record ids: {', '.join(record['qualifying_support_record_ids']) or 'none'}",
        f"- Non-qualifying related record count: {record['nonqualifying_related_record_count']}",
        "",
        "## Rationale",
        "",
    ]
    for point in record["rationale_points"]:
        lines.append(f"- {point}")
    lines.extend(["", "## Caution Flags", ""])
    for flag in record["caution_flags"] or ["none"]:
        lines.append(f"- {flag}")
    lines.extend(["", "## Next Actions", ""])
    for action in record["next_actions"]:
        lines.append(f"- {action}")
    if record["nonqualifying_related_records"]:
        lines.extend(["", "## Non-Qualifying Related Records", ""])
        for item in record["nonqualifying_related_records"]:
            lines.append(
                f"- `{item['record_id']}`: {item['exclusion_reason']}"
            )
    return "\n".join(lines).rstrip() + "\n"


def render_index_markdown(records: list[dict]) -> str:
    outcome_counts = {}
    for record in records:
        outcome_counts[record["review_outcome"]] = outcome_counts.get(record["review_outcome"], 0) + 1
    lines = [
        "# Exact Anchor Review Index v0",
        "",
        "This index tracks the completed exact-anchor review packets for public-record promotion candidates.",
        "",
        f"- Review records: {len(records)}",
    ]
    for outcome in sorted(outcome_counts):
        lines.append(f"- {outcome}: {outcome_counts[outcome]}")
    lines.extend(["", "## Records", ""])
    for record in records:
        record_link = Path(record["repo_paths"]["review_record"]).name
        report_link = Path(record["repo_paths"]["review_report"]).name
        lines.append(
            f"- {record['canonical_entity_name']}: `{record['review_outcome']}` "
            f"([record](records/{record_link}), "
            f"[report](reports/{report_link}))"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews-dir", type=Path, default=DEFAULT_REVIEWS_DIR)
    args = parser.parse_args()

    seed = load_json(SEED_JSON_PATH)
    candidate_snapshot = load_json(CANDIDATE_LINKAGE_SNAPSHOT_PATH)
    candidate_review_snapshot = load_json(CANDIDATE_REVIEW_SNAPSHOT_PATH)
    promotion_snapshot = load_json(PROMOTION_SNAPSHOT_PATH)

    rows_by_id = {row["record_id"]: row for row in seed["rows"]}
    candidate_clusters = {
        item["canonical_entity_name"]: item for item in candidate_snapshot["candidate_clusters"]
    }
    review_items = {
        item["canonical_entity_name"]: item for item in candidate_review_snapshot["review_items"]
    }

    records_dir = args.reviews_dir / "records"
    reports_dir = args.reviews_dir / "reports"
    records_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    updated_records_by_name = {}
    for promotion_candidate in promotion_snapshot["promotion_candidates"]:
        name = promotion_candidate["canonical_entity_name"]
        candidate_cluster = candidate_clusters[name]
        review_item = review_items[name]
        record = build_review_record(
            args.reviews_dir,
            promotion_candidate,
            review_item,
            candidate_cluster,
            rows_by_id,
            promotion_snapshot,
            candidate_review_snapshot,
        )
        record_path = review_record_path(args.reviews_dir, name)
        report_path = review_report_path(args.reviews_dir, name)
        record_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
        report_path.write_text(render_review_markdown(record), encoding="utf-8")
        updated_records_by_name[name] = record

    records = []
    for existing_path in sorted(records_dir.glob("*-exact-anchor-review-v0.yaml")):
        record = load_yaml(existing_path)
        if record["canonical_entity_name"] in updated_records_by_name:
            records.append(updated_records_by_name[record["canonical_entity_name"]])
        else:
            records.append(record)

    missing_new_names = set(updated_records_by_name) - {record["canonical_entity_name"] for record in records}
    for name in sorted(missing_new_names):
        records.append(updated_records_by_name[name])

    records.sort(key=lambda item: item["canonical_entity_name"].lower())

    index_path = args.reviews_dir / "exact-anchor-review-index-v0.md"
    index_path.write_text(render_index_markdown(records), encoding="utf-8")

    print(f"WROTE {index_path.relative_to(REPO_ROOT)}")
    for record in records:
        print(f"WROTE {record['repo_paths']['review_record']}")
        print(f"WROTE {record['repo_paths']['review_report']}")
    print(f"- review_record_count: {len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
