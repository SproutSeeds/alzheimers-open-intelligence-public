#!/usr/bin/env python3
"""Validate the current benchmark packet for basic schema and consistency."""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import jsonschema
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_scalars(value):
    if isinstance(value, dict):
        return {key: normalize_scalars(subvalue) for key, subvalue in value.items()}
    if isinstance(value, list):
        return [normalize_scalars(item) for item in value]
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


def load_schema(path: Path) -> dict:
    schema = normalize_scalars(load_yaml(path))
    if not isinstance(schema, dict):
        raise ValueError(f"Invalid schema mapping: {path}")
    return schema


def validate_instance(instance_path: Path, schema_path: Path, errors: list[str]) -> None:
    if instance_path.suffix == ".json":
        instance = normalize_scalars(load_json(instance_path))
    else:
        instance = normalize_scalars(load_yaml(instance_path))
    schema = load_schema(schema_path)
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"{instance_path.relative_to(REPO_ROOT)}: schema validation failed: {exc.message}")


def load_dataset_ids() -> set[str]:
    path = REPO_ROOT / "datasets/public-dataset-catalog/alzheimers-public-dataset-catalog-v0.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["dataset_id"] for row in rows}


def validate_harmonized_table_rows(csv_path: Path, row_schema_path: Path, errors: list[str]) -> int:
    schema = load_schema(row_schema_path)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows, start=2):
        normalized = {
            "participant_id": row["participant_id"],
            "dataset_id": row["dataset_id"],
            "split_group": row["split_group"],
            "age_years_at_baseline": float(row["age_years_at_baseline"]),
            "recorded_sex_or_gender": row["recorded_sex_or_gender"],
            "education_years_or_binned_equivalent": float(row["education_years_or_binned_equivalent"]),
            "baseline_diagnosis_group": row["baseline_diagnosis_group"],
            "global_cognitive_screen_score": float(row["global_cognitive_screen_score"]),
            "cdr_global": float(row["cdr_global"]),
            "cdr_sum_of_boxes": float(row["cdr_sum_of_boxes"]),
            "tier_a_progression_label": int(row["tier_a_progression_label"]),
        }
        try:
            jsonschema.validate(instance=normalized, schema=schema)
        except jsonschema.ValidationError as exc:
            errors.append(
                f"{csv_path.relative_to(REPO_ROOT)}:{index}: harmonized row validation failed: {exc.message}"
            )
    return len(rows)


def validate_checklist_completion(checklist: dict, checklist_path: Path, errors: list[str]) -> None:
    if checklist["status"] != "audited":
        return
    unresolved = [
        check_name
        for check_name, status in checklist["checklist_results"].items()
        if status == "not_yet_audited"
    ]
    if unresolved:
        errors.append(
            f"{checklist_path.relative_to(REPO_ROOT)}: audited leakage checklist still has unresolved checks: "
            + ", ".join(unresolved)
        )


def validate_field_audit_record_content(record: dict, record_path: Path, errors: list[str]) -> None:
    if record["status"] != "audited":
        return
    for field_name, mapping in record["semantic_field_mappings"].items():
        if mapping["mapping_status"] == "not_yet_audited":
            errors.append(
                f"{record_path.relative_to(REPO_ROOT)}: audited field audit record still has unresolved mapping for {field_name}"
            )
        if "TBD" in mapping["source_table_or_view"] or "TBD" in mapping["source_field"]:
            errors.append(
                f"{record_path.relative_to(REPO_ROOT)}: audited field audit record still has placeholder source mapping for {field_name}"
            )


def validate_public_record_template_header(
    template_path: Path, row_schema_path: Path, errors: list[str]
) -> tuple[int, int]:
    schema = load_schema(row_schema_path)
    required_fields = list(schema["required"])
    with template_path.open("r", encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    header_set = set(header)
    required_set = set(required_fields)
    missing = sorted(required_set - header_set)
    extra = sorted(header_set - required_set)
    if missing:
        errors.append(
            f"{template_path.relative_to(REPO_ROOT)}: row template header missing required fields: {', '.join(missing)}"
        )
    if extra:
        errors.append(
            f"{template_path.relative_to(REPO_ROOT)}: row template header has unexpected fields: {', '.join(extra)}"
        )
    return len(header), len(required_fields)


def validate_public_record_registry_and_manifest(
    registry: dict, manifest: dict, errors: list[str]
) -> tuple[int, int]:
    registry_source_ids = [source["source_system"] for source in registry["sources"]]
    registry_source_set = set(registry_source_ids)
    if len(registry_source_ids) != len(registry_source_set):
        errors.append("Public record source registry has duplicate source_system entries.")

    manifest_source_ids = set(manifest["source_queries"].keys())
    missing_from_registry = sorted(manifest_source_ids - registry_source_set)
    if missing_from_registry:
        errors.append(
            "Public record query manifest references sources missing from registry: "
            + ", ".join(missing_from_registry)
        )

    enabled_count = 0
    for source_id, config in manifest["source_queries"].items():
        if config["enabled"]:
            enabled_count += 1
            if source_id not in registry_source_set:
                errors.append(
                    f"Enabled public record source query has no registry entry: {source_id}"
                )
    if enabled_count == 0:
        errors.append("Public record query manifest enables zero sources.")

    return len(registry_source_ids), enabled_count


def validate_public_record_seed_rows(
    csv_path: Path, row_schema_path: Path, errors: list[str]
) -> int:
    if not csv_path.exists():
        return 0
    schema = load_schema(row_schema_path)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows, start=2):
        normalized = dict(row)
        normalized["year"] = int(row["year"])
        try:
            jsonschema.validate(instance=normalized, schema=schema)
        except jsonschema.ValidationError as exc:
            errors.append(
                f"{csv_path.relative_to(REPO_ROOT)}:{index}: public-record row validation failed: {exc.message}"
            )
    return len(rows)


def validate_public_record_linkage_snapshot_content(
    snapshot: dict,
    seed_json: dict,
    errors: list[str],
) -> None:
    if snapshot["generated_from_dataset_id"] != seed_json["dataset_id"]:
        errors.append(
            "Public-record linkage snapshot dataset id does not match seed dataset id."
        )
    if snapshot["row_count"] != seed_json["row_count"]:
        errors.append("Public-record linkage snapshot row_count does not match seed row_count.")
    if snapshot["entity_group_count"] != seed_json.get("entity_group_count", 0):
        errors.append(
            "Public-record linkage snapshot entity_group_count does not match seed entity_group_count."
        )
    if snapshot["exact_pubmed_pmc_link_count"] != len(snapshot["exact_pubmed_pmc_links"]):
        errors.append(
            "Public-record linkage snapshot exact_pubmed_pmc_link_count does not match the number of exact_pubmed_pmc_links."
        )
    if snapshot["grant_publication_bridge_count"] != len(snapshot["grant_publication_bridges"]):
        errors.append(
            "Public-record linkage snapshot grant_publication_bridge_count does not match the number of grant_publication_bridges."
        )
    if snapshot["intervention_cluster_count"] != len(snapshot["intervention_clusters"]):
        errors.append(
            "Public-record linkage snapshot intervention_cluster_count does not match the number of intervention_clusters."
        )
    if snapshot["multi_source_entity_group_count"] != len(snapshot["multi_source_entity_groups"]):
        errors.append(
            "Public-record linkage snapshot multi_source_entity_group_count does not match the number of multi_source_entity_groups."
        )
    sampled_link_count = sum(
        len(item["sampled_publication_links"])
        for item in snapshot["grant_publication_bridges"]
    )
    if snapshot["sampled_grant_publication_link_count"] != sampled_link_count:
        errors.append(
            "Public-record linkage snapshot sampled_grant_publication_link_count does not match sampled publication link total."
        )
    grants_with_publications_count = sum(
        1
        for item in snapshot["grant_publication_bridges"]
        if item["linked_publication_count"] > 0
    )
    if snapshot["grants_with_linked_publications_count"] != grants_with_publications_count:
        errors.append(
            "Public-record linkage snapshot grants_with_linked_publications_count does not match derived total."
        )
    cross_source_cluster_count = sum(
        1
        for item in snapshot["intervention_clusters"]
        if len(item["source_systems"]) >= 2
    )
    if snapshot["cross_source_intervention_cluster_count"] != cross_source_cluster_count:
        errors.append(
            "Public-record linkage snapshot cross_source_intervention_cluster_count does not match derived total."
        )


def validate_public_record_candidate_snapshot_content(
    snapshot: dict,
    seed_json: dict,
    exact_snapshot: dict,
    manifest: dict,
    errors: list[str],
) -> None:
    if snapshot["generated_from_dataset_id"] != seed_json["dataset_id"]:
        errors.append(
            "Public-record candidate linkage snapshot dataset id does not match seed dataset id."
        )
    if snapshot["exact_linkage_snapshot_id"] != exact_snapshot["snapshot_id"]:
        errors.append(
            "Public-record candidate linkage snapshot exact_linkage_snapshot_id does not match exact linkage snapshot."
        )
    candidate_tracked_interventions = [
        item for item in manifest["tracked_interventions"] if item["source_mode"] == "candidate_only"
    ]
    if snapshot["tracked_intervention_count"] != len(candidate_tracked_interventions):
        errors.append(
            "Public-record candidate linkage snapshot tracked_intervention_count does not match candidate-only tracked interventions."
        )
    if snapshot["candidate_cluster_count"] != len(snapshot["candidate_clusters"]):
        errors.append(
            "Public-record candidate linkage snapshot candidate_cluster_count does not match number of candidate_clusters."
        )
    candidate_link_count = sum(
        item["candidate_link_count"] for item in snapshot["candidate_clusters"]
    )
    if snapshot["candidate_link_count"] != candidate_link_count:
        errors.append(
            "Public-record candidate linkage snapshot candidate_link_count does not match derived total."
        )


def validate_public_record_candidate_review_snapshot_content(
    snapshot: dict,
    seed_json: dict,
    exact_snapshot: dict,
    candidate_snapshot: dict,
    manifest: dict,
    errors: list[str],
) -> None:
    if snapshot["generated_from_dataset_id"] != seed_json["dataset_id"]:
        errors.append(
            "Public-record candidate review snapshot dataset id does not match seed dataset id."
        )
    if snapshot["exact_linkage_snapshot_id"] != exact_snapshot["snapshot_id"]:
        errors.append(
            "Public-record candidate review snapshot exact_linkage_snapshot_id does not match exact linkage snapshot."
        )
    if snapshot["candidate_linkage_snapshot_id"] != candidate_snapshot["snapshot_id"]:
        errors.append(
            "Public-record candidate review snapshot candidate_linkage_snapshot_id does not match candidate linkage snapshot."
        )
    candidate_tracked_interventions = [
        item for item in manifest["tracked_interventions"] if item["source_mode"] == "candidate_only"
    ]
    if snapshot["tracked_intervention_count"] != len(candidate_tracked_interventions):
        errors.append(
            "Public-record candidate review snapshot tracked_intervention_count does not match candidate-only tracked interventions."
        )
    if snapshot["review_item_count"] != len(snapshot["review_items"]):
        errors.append(
            "Public-record candidate review snapshot review_item_count does not match number of review_items."
        )
    candidate_names = {
        item["canonical_entity_name"] for item in candidate_snapshot["candidate_clusters"]
    }
    review_names = {item["canonical_entity_name"] for item in snapshot["review_items"]}
    if review_names != candidate_names:
        errors.append(
            "Public-record candidate review snapshot canonical_entity_name set does not match candidate linkage snapshot."
        )
    high_priority_count = sum(
        1 for item in snapshot["review_items"] if item["review_priority"] == "high"
    )
    if snapshot["high_priority_review_count"] != high_priority_count:
        errors.append(
            "Public-record candidate review snapshot high_priority_review_count does not match derived total."
        )
    watchlist_count = sum(
        1
        for item in snapshot["review_items"]
        if item["promotion_readiness"] == "watch_for_second_source"
    )
    if snapshot["promotion_watchlist_count"] != watchlist_count:
        errors.append(
            "Public-record candidate review snapshot promotion_watchlist_count does not match derived total."
        )
    ready_count = sum(
        1
        for item in snapshot["review_items"]
        if item["promotion_readiness"] == "ready_for_exact_anchor_review"
    )
    if snapshot["ready_for_exact_anchor_review_count"] != ready_count:
        errors.append(
            "Public-record candidate review snapshot ready_for_exact_anchor_review_count does not match derived total."
        )


def validate_public_record_exact_anchor_promotion_snapshot_content(
    snapshot: dict,
    candidate_review_snapshot: dict,
    errors: list[str],
) -> None:
    if snapshot["generated_from_dataset_id"] != candidate_review_snapshot["generated_from_dataset_id"]:
        errors.append(
            "Public-record exact-anchor promotion snapshot dataset id does not match candidate review snapshot."
        )
    if snapshot["candidate_review_snapshot_id"] != candidate_review_snapshot["snapshot_id"]:
        errors.append(
            "Public-record exact-anchor promotion snapshot candidate_review_snapshot_id does not match candidate review snapshot."
        )
    if snapshot["promotion_candidate_count"] != len(snapshot["promotion_candidates"]):
        errors.append(
            "Public-record exact-anchor promotion snapshot promotion_candidate_count does not match number of promotion_candidates."
        )
    expected_names = {
        item["canonical_entity_name"]
        for item in candidate_review_snapshot["review_items"]
        if item["promotion_readiness"] == "ready_for_exact_anchor_review"
    }
    actual_names = {item["canonical_entity_name"] for item in snapshot["promotion_candidates"]}
    if actual_names != expected_names:
        errors.append(
            "Public-record exact-anchor promotion snapshot canonical_entity_name set does not match ready-for-review items in the candidate review snapshot."
        )


def validate_public_record_exact_anchor_review_record_content(
    record: dict,
    promotion_snapshot: dict,
    candidate_review_snapshot: dict,
    record_path: Path,
    errors: list[str],
) -> None:
    if record["generated_from_dataset_id"] != promotion_snapshot["generated_from_dataset_id"]:
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: generated_from_dataset_id does not match promotion snapshot."
        )
    if record["promotion_snapshot_id"] != promotion_snapshot["snapshot_id"]:
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: promotion_snapshot_id does not match promotion snapshot."
        )
    if record["candidate_review_snapshot_id"] != candidate_review_snapshot["snapshot_id"]:
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: candidate_review_snapshot_id does not match candidate review snapshot."
        )
    if record["qualifying_support_record_count"] != len(record["qualifying_support_record_ids"]):
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: qualifying_support_record_count does not match qualifying_support_record_ids."
        )
    if record["nonqualifying_related_record_count"] != len(record["nonqualifying_related_records"]):
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: nonqualifying_related_record_count does not match nonqualifying_related_records."
        )


def validate_public_record_watchlist_review_record_content(
    record: dict,
    candidate_review_snapshot: dict,
    record_path: Path,
    errors: list[str],
) -> None:
    if record["generated_from_dataset_id"] != candidate_review_snapshot["generated_from_dataset_id"]:
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: generated_from_dataset_id does not match candidate review snapshot."
        )
    if record["candidate_review_snapshot_id"] != candidate_review_snapshot["snapshot_id"]:
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: candidate_review_snapshot_id does not match candidate review snapshot."
        )
    if record["current_candidate_record_count"] != len(record["current_candidate_record_ids"]):
        errors.append(
            f"{record_path.relative_to(REPO_ROOT)}: current_candidate_record_count does not match current_candidate_record_ids."
        )


def main() -> int:
    errors: list[str] = []

    benchmark_card_path = (
        REPO_ROOT / "benchmarks/baselines/alzheimers-longitudinal-progression-benchmark-card-v0.yaml"
    )
    benchmark_schema_path = (
        REPO_ROOT / "schemas/alzheimers-longitudinal-progression-benchmark-card-v0.yaml"
    )
    validate_instance(benchmark_card_path, benchmark_schema_path, errors)

    manifest_path = (
        REPO_ROOT / "benchmarks/baselines/alzheimers-longitudinal-progression-baseline-run-manifest-v0.yaml"
    )
    manifest_schema_path = (
        REPO_ROOT / "schemas/alzheimers-longitudinal-progression-baseline-run-manifest-v0.yaml"
    )
    validate_instance(manifest_path, manifest_schema_path, errors)

    checklist_result_path = (
        REPO_ROOT / "benchmarks/contracts/alzheimers-progression-leakage-checklist-result-v0.yaml"
    )
    checklist_schema_path = (
        REPO_ROOT / "schemas/alzheimers-progression-leakage-checklist-result-v0.yaml"
    )
    validate_instance(checklist_result_path, checklist_schema_path, errors)

    access_schema_path = REPO_ROOT / "schemas/alzheimers-cohort-access-record-v0.yaml"
    access_dir = REPO_ROOT / "datasets/access-status/records"
    access_records = {}
    for path in sorted(access_dir.glob("*.yaml")):
        validate_instance(path, access_schema_path, errors)
        record = normalize_scalars(load_yaml(path))
        access_records[record["dataset_id"]] = record

    benchmark_card = normalize_scalars(load_yaml(benchmark_card_path))
    manifest = normalize_scalars(load_yaml(manifest_path))
    checklist = normalize_scalars(load_yaml(checklist_result_path))
    validate_checklist_completion(checklist, checklist_result_path, errors)

    metrics_path = (
        REPO_ROOT
        / "benchmarks/baselines/synthetic-dry-run/alzheimers-longitudinal-progression-baseline-metrics-v0.json"
    )
    metrics_schema_path = (
        REPO_ROOT / "schemas/alzheimers-longitudinal-progression-baseline-metrics-v0.yaml"
    )
    if metrics_path.exists():
        validate_instance(metrics_path, metrics_schema_path, errors)

    receipt_path = (
        REPO_ROOT
        / "benchmarks/baselines/synthetic-dry-run/alzheimers-longitudinal-progression-baseline-receipt-v0.yaml"
    )
    receipt_schema_path = (
        REPO_ROOT / "schemas/alzheimers-longitudinal-progression-baseline-run-receipt-v0.yaml"
    )
    if receipt_path.exists():
        validate_instance(receipt_path, receipt_schema_path, errors)

    harmonized_metrics_path = (
        REPO_ROOT
        / "benchmarks/baselines/harmonized-dry-run/alzheimers-longitudinal-progression-baseline-metrics-v0.json"
    )
    if harmonized_metrics_path.exists():
        validate_instance(harmonized_metrics_path, metrics_schema_path, errors)

    harmonized_receipt_path = (
        REPO_ROOT
        / "benchmarks/baselines/harmonized-dry-run/alzheimers-longitudinal-progression-baseline-receipt-v0.yaml"
    )
    if harmonized_receipt_path.exists():
        validate_instance(harmonized_receipt_path, receipt_schema_path, errors)

    harmonized_template_path = (
        REPO_ROOT
        / "benchmarks/baselines/harmonized-input/alzheimers-longitudinal-progression-harmonized-baseline-table-template-v0.csv"
    )
    harmonized_row_schema_path = (
        REPO_ROOT / "schemas/alzheimers-longitudinal-progression-harmonized-baseline-row-v0.yaml"
    )
    harmonized_row_count = validate_harmonized_table_rows(
        harmonized_template_path, harmonized_row_schema_path, errors
    )

    field_audit_schema_path = REPO_ROOT / "schemas/alzheimers-progression-cohort-field-audit-record-v0.yaml"
    field_audit_record_paths = sorted(
        (REPO_ROOT / "benchmarks/contracts").glob("*-progression-cohort-field-audit-record-v0.yaml")
    )
    field_audit_records = {}
    for path in field_audit_record_paths:
        validate_instance(path, field_audit_schema_path, errors)
        record = normalize_scalars(load_yaml(path))
        validate_field_audit_record_content(record, path, errors)
        field_audit_records[record["dataset_id"]] = record

    slice_manifest_template_path = (
        REPO_ROOT
        / "datasets/access-approved/manifests/alzheimers-cohort-access-approved-slice-manifest-template-v0.yaml"
    )
    slice_manifest_schema_path = REPO_ROOT / "schemas/alzheimers-cohort-access-approved-slice-manifest-v0.yaml"
    validate_instance(slice_manifest_template_path, slice_manifest_schema_path, errors)

    real_run_bundle_template_path = (
        REPO_ROOT
        / "benchmarks/baselines/harmonized-input/alzheimers-longitudinal-progression-real-run-bundle-template-v0.yaml"
    )
    real_run_bundle_schema_path = (
        REPO_ROOT / "schemas/alzheimers-longitudinal-progression-real-run-bundle-v0.yaml"
    )
    validate_instance(real_run_bundle_template_path, real_run_bundle_schema_path, errors)

    harmonization_recipe_schema_path = (
        REPO_ROOT / "schemas/alzheimers-longitudinal-progression-cohort-harmonization-recipe-v0.yaml"
    )
    harmonization_recipe_template_path = (
        REPO_ROOT
        / "benchmarks/baselines/harmonized-input/recipes/alzheimers-longitudinal-progression-cohort-harmonization-recipe-template-v0.yaml"
    )
    validate_instance(harmonization_recipe_template_path, harmonization_recipe_schema_path, errors)

    harmonization_recipe_example_path = (
        REPO_ROOT
        / "benchmarks/baselines/harmonized-input/examples/synthetic-progression-cohort-harmonization-recipe-example-v0.yaml"
    )
    validate_instance(harmonization_recipe_example_path, harmonization_recipe_schema_path, errors)

    public_record_source_registry_path = (
        REPO_ROOT
        / "datasets/public-record-derived/alzheimers-public-record-source-registry-v0.yaml"
    )
    public_record_source_registry_schema_path = (
        REPO_ROOT / "schemas/alzheimers-public-record-source-registry-v0.yaml"
    )
    validate_instance(
        public_record_source_registry_path,
        public_record_source_registry_schema_path,
        errors,
    )

    public_record_query_manifest_path = (
        REPO_ROOT
        / "datasets/public-record-derived/alzheimers-public-record-query-manifest-v0.yaml"
    )
    public_record_query_manifest_schema_path = (
        REPO_ROOT / "schemas/alzheimers-public-record-query-manifest-v0.yaml"
    )
    validate_instance(
        public_record_query_manifest_path,
        public_record_query_manifest_schema_path,
        errors,
    )

    public_record_row_schema_path = REPO_ROOT / "schemas/alzheimers-public-record-row-v0.yaml"
    public_record_template_path = (
        REPO_ROOT
        / "datasets/public-record-derived/templates/alzheimers-public-record-row-template-v0.csv"
    )
    public_record_registry = normalize_scalars(load_yaml(public_record_source_registry_path))
    public_record_manifest = normalize_scalars(load_yaml(public_record_query_manifest_path))
    public_record_source_count, public_record_enabled_source_count = (
        validate_public_record_registry_and_manifest(public_record_registry, public_record_manifest, errors)
    )
    public_record_template_column_count, public_record_schema_required_count = (
        validate_public_record_template_header(
            public_record_template_path, public_record_row_schema_path, errors
        )
    )
    public_record_seed_csv_path = (
        REPO_ROOT / "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.csv"
    )
    public_record_seed_row_count = validate_public_record_seed_rows(
        public_record_seed_csv_path, public_record_row_schema_path, errors
    )
    public_record_seed_json_path = (
        REPO_ROOT / "datasets/public-record-derived/seed/alzheimers-public-record-seed-v0.json"
    )
    public_record_seed_json = normalize_scalars(load_json(public_record_seed_json_path))

    public_record_linkage_snapshot_path = (
        REPO_ROOT
        / "datasets/public-record-derived/linked/alzheimers-public-record-linkage-snapshot-v0.json"
    )
    public_record_linkage_snapshot_schema_path = (
        REPO_ROOT / "schemas/alzheimers-public-record-linkage-snapshot-v0.yaml"
    )
    if public_record_linkage_snapshot_path.exists():
        validate_instance(
            public_record_linkage_snapshot_path,
            public_record_linkage_snapshot_schema_path,
            errors,
        )
        public_record_linkage_snapshot = normalize_scalars(
            load_json(public_record_linkage_snapshot_path)
        )
        validate_public_record_linkage_snapshot_content(
            public_record_linkage_snapshot,
            public_record_seed_json,
            errors,
        )
    else:
        public_record_linkage_snapshot = None

    public_record_candidate_snapshot_path = (
        REPO_ROOT
        / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-linkage-snapshot-v0.json"
    )
    public_record_candidate_snapshot_schema_path = (
        REPO_ROOT / "schemas/alzheimers-public-record-candidate-linkage-snapshot-v0.yaml"
    )
    public_record_candidate_snapshot = None
    if public_record_candidate_snapshot_path.exists():
        validate_instance(
            public_record_candidate_snapshot_path,
            public_record_candidate_snapshot_schema_path,
            errors,
        )
        if public_record_linkage_snapshot is None:
            errors.append(
                "Public-record candidate linkage snapshot exists without an exact linkage snapshot."
            )
        else:
            public_record_candidate_snapshot = normalize_scalars(
                load_json(public_record_candidate_snapshot_path)
            )
            validate_public_record_candidate_snapshot_content(
                public_record_candidate_snapshot,
                public_record_seed_json,
                public_record_linkage_snapshot,
                public_record_manifest,
                errors,
            )

    public_record_candidate_review_snapshot_path = (
        REPO_ROOT
        / "datasets/public-record-derived/linked/alzheimers-public-record-candidate-review-snapshot-v0.json"
    )
    public_record_candidate_review_snapshot_schema_path = (
        REPO_ROOT / "schemas/alzheimers-public-record-candidate-review-snapshot-v0.yaml"
    )
    if public_record_candidate_review_snapshot_path.exists():
        validate_instance(
            public_record_candidate_review_snapshot_path,
            public_record_candidate_review_snapshot_schema_path,
            errors,
        )
        if public_record_linkage_snapshot is None or public_record_candidate_snapshot is None:
            errors.append(
                "Public-record candidate review snapshot exists without exact and candidate linkage snapshots."
            )
        else:
            public_record_candidate_review_snapshot = normalize_scalars(
                load_json(public_record_candidate_review_snapshot_path)
            )
            validate_public_record_candidate_review_snapshot_content(
                public_record_candidate_review_snapshot,
                public_record_seed_json,
                public_record_linkage_snapshot,
                public_record_candidate_snapshot,
                public_record_manifest,
                errors,
            )
    else:
        public_record_candidate_review_snapshot = None

    public_record_exact_anchor_promotion_snapshot_path = (
        REPO_ROOT
        / "datasets/public-record-derived/linked/alzheimers-public-record-exact-anchor-promotion-snapshot-v0.json"
    )
    public_record_exact_anchor_promotion_schema_path = (
        REPO_ROOT
        / "schemas/alzheimers-public-record-exact-anchor-promotion-snapshot-v0.yaml"
    )
    if public_record_exact_anchor_promotion_snapshot_path.exists():
        validate_instance(
            public_record_exact_anchor_promotion_snapshot_path,
            public_record_exact_anchor_promotion_schema_path,
            errors,
        )
        if public_record_candidate_review_snapshot is None:
            errors.append(
                "Public-record exact-anchor promotion snapshot exists without a candidate review snapshot."
            )
        else:
            public_record_exact_anchor_promotion_snapshot = normalize_scalars(
                load_json(public_record_exact_anchor_promotion_snapshot_path)
            )
            validate_public_record_exact_anchor_promotion_snapshot_content(
                public_record_exact_anchor_promotion_snapshot,
                public_record_candidate_review_snapshot,
                errors,
            )
    else:
        public_record_exact_anchor_promotion_snapshot = None

    public_record_exact_anchor_review_record_schema_path = (
        REPO_ROOT / "schemas/alzheimers-public-record-exact-anchor-review-record-v0.yaml"
    )
    public_record_exact_anchor_review_record_paths = sorted(
        (
            REPO_ROOT / "interventions/hypothesis-ledger/exact-anchor-reviews/records"
        ).glob("*-exact-anchor-review-v0.yaml")
    )
    if public_record_exact_anchor_review_record_paths:
        if public_record_exact_anchor_promotion_snapshot is None or public_record_candidate_review_snapshot is None:
            errors.append(
                "Exact-anchor review records exist without promotion and candidate review snapshots."
            )
        current_exact_anchor_names = {
            item["canonical_entity_name"]
            for item in public_record_manifest["tracked_interventions"]
            if item["source_mode"] == "exact_anchor"
        }
        expected_review_names = {
            item["canonical_entity_name"]
            for item in (
                public_record_exact_anchor_promotion_snapshot["promotion_candidates"]
                if public_record_exact_anchor_promotion_snapshot is not None
                else []
            )
        }
        actual_review_names = set()
        for path in public_record_exact_anchor_review_record_paths:
            validate_instance(
                path,
                public_record_exact_anchor_review_record_schema_path,
                errors,
            )
            record = normalize_scalars(load_yaml(path))
            actual_review_names.add(record["canonical_entity_name"])
            if (
                public_record_exact_anchor_promotion_snapshot is not None
                and public_record_candidate_review_snapshot is not None
            ):
                validate_public_record_exact_anchor_review_record_content(
                    record,
                    public_record_exact_anchor_promotion_snapshot,
                    public_record_candidate_review_snapshot,
                    path,
                    errors,
                )
        if not expected_review_names.issubset(actual_review_names):
            errors.append(
                "Exact-anchor review record set is missing one or more current exact-anchor promotion candidates."
            )
        allowed_review_names = expected_review_names | current_exact_anchor_names
        if not actual_review_names.issubset(allowed_review_names):
            errors.append(
                "Exact-anchor review record set contains names that are neither current promotion candidates nor current exact anchors."
            )

    public_record_watchlist_review_record_schema_path = (
        REPO_ROOT / "schemas/alzheimers-public-record-watchlist-review-record-v0.yaml"
    )
    public_record_watchlist_review_record_paths = sorted(
        (
            REPO_ROOT / "interventions/hypothesis-ledger/watchlist-reviews/records"
        ).glob("*-watchlist-review-v0.yaml")
    )
    if public_record_watchlist_review_record_paths:
        if public_record_candidate_review_snapshot is None:
            errors.append(
                "Watchlist review records exist without a candidate review snapshot."
            )
        current_tracked_names = {
            item["canonical_entity_name"]
            for item in public_record_manifest["tracked_interventions"]
        }
        expected_watchlist_names = {
            item["canonical_entity_name"]
            for item in (
                public_record_candidate_review_snapshot["review_items"]
                if public_record_candidate_review_snapshot is not None
                else []
            )
            if item["promotion_readiness"] != "ready_for_exact_anchor_review"
        }
        actual_watchlist_names = set()
        for path in public_record_watchlist_review_record_paths:
            validate_instance(
                path,
                public_record_watchlist_review_record_schema_path,
                errors,
            )
            record = normalize_scalars(load_yaml(path))
            actual_watchlist_names.add(record["canonical_entity_name"])
            if public_record_candidate_review_snapshot is not None:
                validate_public_record_watchlist_review_record_content(
                    record,
                    public_record_candidate_review_snapshot,
                    path,
                    errors,
                )
        if not expected_watchlist_names.issubset(actual_watchlist_names):
            errors.append(
                "Watchlist review record set is missing one or more current unresolved candidate interventions."
            )
        if not actual_watchlist_names.issubset(current_tracked_names):
            errors.append(
                "Watchlist review record set contains names outside the tracked intervention manifest."
            )

    dev_card = list(benchmark_card["development_cohorts"])
    dev_manifest = list(manifest["development_cohorts"])
    dev_checklist = list(checklist["cohort_shell"]["development"])
    if not (dev_card == dev_manifest == dev_checklist):
        errors.append("Development cohort mismatch across benchmark card, manifest, and checklist result.")

    transfer_card = list(benchmark_card["transfer_cohorts"])
    transfer_manifest = list(manifest["transfer_cohorts"])
    transfer_checklist = list(checklist["cohort_shell"]["transfer"])
    if not (transfer_card == transfer_manifest == transfer_checklist):
        errors.append("Transfer cohort mismatch across benchmark card, manifest, and checklist result.")

    dataset_ids = load_dataset_ids()
    for dataset_id in dev_card + transfer_card:
        if dataset_id not in dataset_ids:
            errors.append(f"Admitted cohort missing from dataset catalog: {dataset_id}")
        if dataset_id not in access_records:
            errors.append(f"Admitted cohort missing from access records: {dataset_id}")

    expected_audit_paths = {
        "adni": REPO_ROOT / "benchmarks/contracts/adni-progression-cohort-field-audit-v0.md",
        "nacc-uds": REPO_ROOT / "benchmarks/contracts/nacc-progression-cohort-field-audit-v0.md",
        "oasis-3": REPO_ROOT / "benchmarks/contracts/oasis3-progression-cohort-field-audit-v0.md",
    }
    expected_audit_record_paths = {
        "adni": REPO_ROOT / "benchmarks/contracts/adni-progression-cohort-field-audit-record-v0.yaml",
        "nacc-uds": REPO_ROOT / "benchmarks/contracts/nacc-progression-cohort-field-audit-record-v0.yaml",
        "oasis-3": REPO_ROOT / "benchmarks/contracts/oasis3-progression-cohort-field-audit-record-v0.yaml",
    }
    for dataset_id in dev_card + transfer_card:
        audit_path = expected_audit_paths.get(dataset_id)
        if audit_path is None or not audit_path.exists():
            errors.append(f"Missing cohort audit stub for admitted cohort: {dataset_id}")
        audit_record_path = expected_audit_record_paths.get(dataset_id)
        if audit_record_path is None or not audit_record_path.exists():
            errors.append(f"Missing cohort audit record for admitted cohort: {dataset_id}")
        if dataset_id not in field_audit_records:
            errors.append(f"Missing validated cohort audit record content for admitted cohort: {dataset_id}")

    for relative_path in benchmark_card["source_contract_paths"]:
        if not (benchmark_card_path.parent / relative_path).exists():
            errors.append(f"Benchmark card references missing source artifact: {relative_path}")

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("VALIDATION PASSED")
    print(f"- development cohorts: {', '.join(dev_card)}")
    print(f"- transfer cohorts: {', '.join(transfer_card)}")
    print(f"- access records validated: {len(access_records)}")
    print(f"- field audit records validated: {len(field_audit_records)}")
    print(
        "- schema-validated instances: "
        f"3 benchmark artifacts + {len(access_records)} access records + "
        f"{len(field_audit_records)} field audit records + 4 governance artifacts + "
        "2 public-record artifacts"
    )
    print(f"- harmonized template rows validated: {harmonized_row_count}")
    print("- real-run governance and recipe artifacts validated: 4")
    print(
        f"- public-record sources tracked: {public_record_source_count} "
        f"({public_record_enabled_source_count} enabled in query manifest)"
    )
    print(
        f"- public-record template columns: {public_record_template_column_count} "
        f"(schema requires {public_record_schema_required_count})"
    )
    print(f"- public-record seed rows validated: {public_record_seed_row_count}")
    if public_record_linkage_snapshot_path.exists():
        print("- public-record linkage snapshot validated")
    if public_record_candidate_snapshot_path.exists():
        print("- public-record candidate linkage snapshot validated")
    if public_record_candidate_review_snapshot_path.exists():
        print("- public-record candidate review snapshot validated")
    if public_record_exact_anchor_promotion_snapshot_path.exists():
        print("- public-record exact-anchor promotion snapshot validated")
    if public_record_exact_anchor_review_record_paths:
        print(
            f"- public-record exact-anchor review records validated: {len(public_record_exact_anchor_review_record_paths)}"
        )
    if public_record_watchlist_review_record_paths:
        print(
            f"- public-record watchlist review records validated: {len(public_record_watchlist_review_record_paths)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
