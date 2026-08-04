"""Behavioral tests for the local public portfolio receipt router."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from core.portfolio_router import (
    EVIDENCE_STATE,
    SCHEMA,
    PortfolioReceiptRouter,
    RegistryValidationError,
    load_registry,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "PORTFOLIO_REGISTRY.json"


def raw_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_valid_registry_normalizes() -> None:
    result = validate_registry(raw_registry())
    assert result["schema"] == SCHEMA
    assert result["evidence_state"] == EVIDENCE_STATE


def test_registry_must_be_mapping() -> None:
    with pytest.raises(RegistryValidationError):
        validate_registry([])


def test_wrong_schema_fails_closed() -> None:
    value = raw_registry()
    value["schema"] = "wrong"
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_wrong_evidence_state_fails_closed() -> None:
    value = raw_registry()
    value["evidence_state"] = "RUNTIME_ORCHESTRATOR"
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_non_affiliation_must_be_true() -> None:
    value = raw_registry()
    value["non_affiliation"] = False
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_verified_sources_must_not_be_empty() -> None:
    value = raw_registry()
    value["verified_sources"] = {}
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_verified_repositories_must_be_unique() -> None:
    value = raw_registry()
    value["verified_sources"]["cooling"]["repository"] = value["verified_sources"]["energy"]["repository"]
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_verified_state_must_end_in_verified() -> None:
    value = raw_registry()
    value["verified_sources"]["cooling"]["evidence_state"] = "GENERATED"
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_verified_test_count_must_be_positive() -> None:
    value = raw_registry()
    value["verified_sources"]["cooling"]["bounded_tests_passed"] = 0
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_verified_artifact_ids_must_be_unique() -> None:
    value = raw_registry()
    value["verified_sources"]["cooling"]["artifact_id"] = value["verified_sources"]["energy"]["artifact_id"]
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_verified_sources_must_remain_unmerged() -> None:
    value = raw_registry()
    value["verified_sources"]["cooling"]["merged"] = True
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_verified_public_claim_is_required() -> None:
    value = raw_registry()
    value["verified_sources"]["cooling"]["public_claim"] = " "
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_candidate_classification_must_be_allowed() -> None:
    value = raw_registry()
    value["execution_blocked_candidates"]["microcode"]["classification"] = "VERIFIED"
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_candidate_runner_steps_must_remain_false() -> None:
    value = raw_registry()
    value["execution_blocked_candidates"]["microcode"]["runner_steps_created"] = True
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_candidate_counted_as_verified_must_remain_false() -> None:
    value = raw_registry()
    value["execution_blocked_candidates"]["microcode"]["counted_as_verified"] = True
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_candidate_priorities_must_be_unique() -> None:
    value = raw_registry()
    value["execution_blocked_candidates"]["waterplant"]["strategic_priority"] = value["execution_blocked_candidates"]["microcode"]["strategic_priority"]
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_candidate_repository_cannot_duplicate_verified_source() -> None:
    value = raw_registry()
    value["execution_blocked_candidates"]["microcode"]["repository"] = value["verified_sources"]["security"]["repository"]
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_aggregate_verified_source_count_reconciles() -> None:
    value = raw_registry()
    value["aggregate_executed_evidence"]["verified_source_count"] = 6
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_aggregate_bounded_test_count_reconciles() -> None:
    value = raw_registry()
    value["aggregate_executed_evidence"]["bounded_source_tests_passed"] = 167
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_aggregate_memory_test_count_reconciles() -> None:
    value = raw_registry()
    value["aggregate_executed_evidence"]["additional_energy_memory_unit_tests_passed"] = 18
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_aggregate_artifact_count_reconciles() -> None:
    value = raw_registry()
    value["aggregate_executed_evidence"]["direct_receipt_artifacts"] = 6
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_aggregate_merged_count_must_be_zero() -> None:
    value = raw_registry()
    value["aggregate_executed_evidence"]["source_pull_requests_merged"] = 1
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_canonical_authority_keys_are_exact() -> None:
    value = raw_registry()
    del value["canonical_authorities"]["technical_sources"]
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_historical_runtime_classification_is_exact() -> None:
    value = raw_registry()
    value["historical_runtime_surfaces"]["classification"] = "ACTIVE"
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_historical_excluded_claims_must_not_be_empty() -> None:
    value = raw_registry()
    value["historical_runtime_surfaces"]["excluded_claims"] = []
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_global_exclusions_must_not_be_empty() -> None:
    value = raw_registry()
    value["global_exclusions"] = []
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_repository_action_keys_are_exact() -> None:
    value = raw_registry()
    value["repository_actions"]["unknown"] = 0
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_repository_actions_must_all_be_zero() -> None:
    value = raw_registry()
    value["repository_actions"]["archived"] = 1
    with pytest.raises(RegistryValidationError):
        validate_registry(value)


def test_router_domains_are_exact() -> None:
    router = PortfolioReceiptRouter(raw_registry())
    assert router.domains() == (
        "architecture_planner",
        "cooling",
        "energy",
        "microcode",
        "nanosphere",
        "security",
        "servers",
        "waterplant",
    )


def test_router_routes_verified_source() -> None:
    record = PortfolioReceiptRouter(raw_registry()).route("security")
    assert record["classification"] == "VERIFIED_SOURCE_PROMOTION"
    assert record["promotion_ready"] is True
    assert record["bounded_tests_passed"] == 35


def test_router_routes_blocked_candidate() -> None:
    record = PortfolioReceiptRouter(raw_registry()).route("microcode")
    assert record["classification"] == "REVIEWED_EXECUTION_BLOCKED"
    assert record["promotion_ready"] is False
    assert record["generated_test_contract_count"] == 132


def test_router_rejects_unknown_domain() -> None:
    with pytest.raises(KeyError):
        PortfolioReceiptRouter(raw_registry()).route("unknown")


def test_promotion_readiness_is_exact() -> None:
    router = PortfolioReceiptRouter(raw_registry())
    assert router.promotion_ready("cooling") is True
    assert router.promotion_ready("waterplant") is False


def test_public_claims_include_only_verified_sources() -> None:
    claims = PortfolioReceiptRouter(raw_registry()).public_claims()
    assert len(claims) == 5
    assert {item["domain_id"] for item in claims} == {
        "cooling",
        "energy",
        "servers",
        "security",
        "nanosphere",
    }


def test_summary_totals_are_exact() -> None:
    summary = PortfolioReceiptRouter(raw_registry()).summary()
    assert summary["verified_source_count"] == 5
    assert summary["bounded_source_tests_passed"] == 166
    assert summary["additional_energy_memory_unit_tests_passed"] == 19
    assert summary["execution_blocked_candidate_count"] == 3
    assert summary["candidate_generated_test_contract_count"] == 243
    assert summary["candidate_priority"] == [
        "microcode",
        "architecture_planner",
        "waterplant",
    ]


def test_router_output_is_deterministic() -> None:
    first = PortfolioReceiptRouter(raw_registry()).to_json()
    second = PortfolioReceiptRouter(raw_registry()).to_json()
    assert first == second


def test_load_registry_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RegistryValidationError):
        load_registry(tmp_path / "missing.json")


def test_load_registry_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RegistryValidationError):
        load_registry(path)
