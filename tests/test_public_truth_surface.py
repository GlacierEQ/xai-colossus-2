"""Regression tests for truth/capability separation on the public project surface."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
REGISTRY_TEXT = (ROOT / "PORTFOLIO_REGISTRY.json").read_text(encoding="utf-8")
REGISTRY = json.loads(REGISTRY_TEXT)
ROUTER = (ROOT / "core" / "portfolio_router.py").read_text(encoding="utf-8")
MASTERMIND = (ROOT / "core" / "mastermind_orchestrator.py").read_text(encoding="utf-8")
HISTORICAL = (ROOT / "HISTORICAL_SURFACES.md").read_text(encoding="utf-8")


def test_product_target_proof_and_projection_are_explicitly_separate() -> None:
    for phrase in (
        "Product / target",
        "Implementation lineage",
        "Current runtime",
        "Evidence / proof",
        "Public projection",
        "proof limits claims; it does not set the product ceiling",
    ):
        assert phrase in README
    assert REGISTRY["evidence_state"] == "LOCAL_METADATA_ROUTER_NOT_RUNTIME_ORCHESTRATOR"


def test_public_non_affiliation_boundary_is_explicit() -> None:
    assert "Independent GlacierEQ engineering project" in README
    assert "does not establish affiliation with" in README
    assert "production deployment at xAI" in README
    assert REGISTRY["non_affiliation"] is True


def test_hyperscale_values_are_not_presented_as_observed_production_facts() -> None:
    assert "Large-scale values such as GPU count" in README
    assert "belong to scenario/target modeling unless a specific source" in README
    assert "control of a live datacenter" in README


def test_router_remains_local_evidence_plane() -> None:
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


def test_mastermind_is_runtime_again_without_claiming_external_deployment() -> None:
    assert "LOCAL_ORCHESTRATION_RUNTIME_RESTORED" in MASTERMIND
    assert '"runtime_orchestration_available": True' in MASTERMIND
    assert "discover_sibling_subsystems" in MASTERMIND
    assert "register_task_handler" in MASTERMIND
    assert "task_queue" in MASTERMIND
    assert "asyncio.sleep" in MASTERMIND
    assert "local orchestration/runtime behavior does not establish external company deployment" in MASTERMIND


def test_unbound_capability_slots_do_not_fabricate_success() -> None:
    assert "piston has no bound execution handler" in MASTERMIND
    assert "no executable piston matches this task" in MASTERMIND
    assert "BLOCKED_UNBOUND" in MASTERMIND
    assert '"executed": False' in MASTERMIND


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
    assert "Counted verified" in README


def test_evidence_router_roles_do_not_replace_product_identity() -> None:
    assert REGISTRY["canonical_authorities"]["public_receipt_router"] == "GlacierEQ/xai-colossus-2"
    assert "The receipt router stays" in README
    assert "one evidence subsystem inside the stronger architecture" in README


def test_historical_runtime_is_preserved_as_capability_donor_not_deployment_proof() -> None:
    assert REGISTRY["historical_runtime_surfaces"]["classification"] == "HISTORICAL_NON_AUTHORITATIVE"
    assert "HISTORICAL_NON_AUTHORITATIVE" in HISTORICAL
    assert "capability donors" in README
    assert "Historical code is not automatically proof" in README


def test_repository_actions_are_non_destructive() -> None:
    assert REGISTRY["repository_actions"] == {
        "deleted": 0,
        "archived": 0,
        "renamed": 0,
        "collapsed": 0,
        "merged_by_this_pass": 0,
    }
    assert "No repository or historical commit is deleted" in HISTORICAL


def test_career_and_engineering_positioning_keeps_ambition_and_truth() -> None:
    for phrase in (
        "Datacenter Infrastructure Orchestration Project",
        "## Architecture",
        "## Counter-engineering result and next frontier",
        "preserve truth, restore function, then exceed the strongest prior implementation",
    ):
        assert phrase in README
    assert "Do not achieve truth by stripping the implementation down" in README
