"""Regression tests for the public receipt-router claim surface."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
REGISTRY_TEXT = (ROOT / "PORTFOLIO_REGISTRY.json").read_text(encoding="utf-8")
REGISTRY = json.loads(REGISTRY_TEXT)
ROUTER = (ROOT / "core" / "portfolio_router.py").read_text(encoding="utf-8")
FACADE = (ROOT / "core" / "mastermind_orchestrator.py").read_text(encoding="utf-8")
HISTORICAL = (ROOT / "HISTORICAL_SURFACES.md").read_text(encoding="utf-8")


def test_public_evidence_state_is_explicit() -> None:
    assert "LOCAL_METADATA_ROUTER_NOT_RUNTIME_ORCHESTRATOR" in README
    assert REGISTRY["evidence_state"] == "LOCAL_METADATA_ROUTER_NOT_RUNTIME_ORCHESTRATOR"
    assert "It validates and routes **local portfolio evidence metadata**" in README


def test_public_non_affiliation_boundary_is_explicit() -> None:
    assert "not an xAI system" in README
    assert "not affiliated with or endorsed by xAI" in README
    assert REGISTRY["non_affiliation"] is True


def test_old_hyperscale_claims_are_absent_from_authoritative_surfaces() -> None:
    authoritative = "\n".join((README, REGISTRY_TEXT, ROUTER, FACADE))
    for phrase in (
        "1.5GW, 200,000-GPU",
        "1.5 GW",
        "200,000 GPUs",
        "12,500 racks",
        "100,000 InfiniBand",
        "100 immersion",
        "16+ API",
        "10 MCP",
        "Build for 200k GPUs",
    ):
        assert phrase not in authoritative


def test_old_legal_and_piston_runtime_claims_are_absent() -> None:
    authoritative = "\n".join((README, REGISTRY_TEXT, ROUTER, FACADE))
    for phrase in (
        "MOTION-FORGE",
        "RICO-MAPPER",
        "FEDERAL-ESCALATION",
        "CONSTITUTIONAL-WARFARE",
        "Legal Motion Generation",
        "Federal Court Filing",
        "12 autonomous pistons",
    ):
        assert phrase not in authoritative


def test_router_is_local_only() -> None:
    forbidden = (
        "requests.",
        "urlopen(",
        "socket.",
        "subprocess.",
        "importlib",
        "sys.path.insert",
        "time.sleep(",
        "asyncio.sleep(",
    )
    for phrase in forbidden:
        assert phrase not in ROUTER
    assert "external_queries_executed" in ROUTER
    assert "external_actions_executed" in ROUTER


def test_compatibility_facade_does_not_load_siblings() -> None:
    forbidden = (
        "xai-colossus-cooling",
        "xai-colossus-energy",
        "xai-colossus-security",
        "spec_from_file_location",
        "tick_cycle",
        "auto-restarting",
        "task_queue",
    )
    for phrase in forbidden:
        assert phrase not in FACADE
    assert "runtime_orchestration_available" in FACADE
    assert "execution_rejected" in FACADE


def test_verified_registry_set_and_totals_are_exact() -> None:
    assert set(REGISTRY["verified_sources"]) == {
        "cooling",
        "energy",
        "servers",
        "security",
        "nanosphere",
    }
    assert REGISTRY["aggregate_executed_evidence"] == {
        "verified_source_count": 5,
        "bounded_source_tests_passed": 166,
        "additional_energy_memory_unit_tests_passed": 19,
        "direct_receipt_artifacts": 5,
        "source_pull_requests_merged": 0,
    }


def test_blocked_candidates_are_not_promoted() -> None:
    candidates = REGISTRY["execution_blocked_candidates"]
    assert set(candidates) == {"microcode", "waterplant", "architecture_planner"}
    assert all(item["runner_steps_created"] is False for item in candidates.values())
    assert all(item["counted_as_verified"] is False for item in candidates.values())
    assert "These contracts are not added to the executed total" in README


def test_canonical_authority_boundaries_are_explicit() -> None:
    assert REGISTRY["canonical_authorities"] == {
        "technical_sources": "individual verified source repositories",
        "portfolio_dependency_model": "GlacierEQ/colossus-build-blueprint",
        "human_evidence_navigator": "GlacierEQ/xai-colossus-community",
        "public_receipt_router": "GlacierEQ/xai-colossus-2",
    }
    assert "The public hub does not copy source implementations" in README


def test_historical_surfaces_are_non_authoritative() -> None:
    assert REGISTRY["historical_runtime_surfaces"]["classification"] == "HISTORICAL_NON_AUTHORITATIVE"
    assert "HISTORICAL_NON_AUTHORITATIVE" in HISTORICAL
    assert "Current authoritative surfaces" in HISTORICAL
    assert "Prohibited evidence use" in HISTORICAL


def test_repository_actions_are_non_destructive() -> None:
    assert REGISTRY["repository_actions"] == {
        "deleted": 0,
        "archived": 0,
        "renamed": 0,
        "collapsed": 0,
        "merged_by_this_pass": 0,
    }
    assert "No repository or historical commit is deleted" in HISTORICAL


def test_career_positioning_is_governance_not_control() -> None:
    for phrase in (
        "evidence-aware systems architecture",
        "trustworthy portfolio and release governance",
        "fail-closed metadata validation",
        "bounded claims and promotion control",
        "public evidence router and governance layer",
    ):
        assert phrase in README
    assert "Do not present it as an infrastructure control system" in README
