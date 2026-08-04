"""Tests for the fail-closed Mastermind compatibility facade."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.mastermind_orchestrator import (
    MastermindOrchestrator,
    SubsystemHealth,
    Task,
    TaskPriority,
    TaskState,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "PORTFOLIO_REGISTRY.json"


def orchestrator() -> MastermindOrchestrator:
    return MastermindOrchestrator(REGISTRY)


def test_facade_loads_local_registry() -> None:
    value = orchestrator()
    assert value.registry_path == REGISTRY
    assert value.evidence_state == "LOCAL_METADATA_ROUTER_NOT_RUNTIME_ORCHESTRATOR"


def test_facade_registers_no_pistons() -> None:
    assert orchestrator().pistons == {}


def test_facade_exposes_evidence_domains_not_live_subsystems() -> None:
    value = orchestrator()
    assert set(value.subsystems) == set(value.router.domains())
    assert all(item["telemetry_available"] is False for item in value.subsystems.values())


def test_facade_marks_health_unknown() -> None:
    value = orchestrator()
    assert all(
        item["health"] == SubsystemHealth.UNKNOWN_NOT_TELEMETRY.value
        for item in value.subsystems.values()
    )


def test_summary_disables_runtime_orchestration() -> None:
    summary = orchestrator().summary()
    assert summary["runtime_orchestration_available"] is False
    assert summary["verified_source_count"] == 5
    assert summary["external_queries_executed"] == 0
    assert summary["external_actions_executed"] == 0


def test_monitor_health_returns_evidence_metadata() -> None:
    report = asyncio.run(orchestrator().monitor_health())
    assert report["security"]["classification"] == "VERIFIED_SOURCE_PROMOTION"
    assert report["microcode"]["classification"] == "REVIEWED_EXECUTION_BLOCKED"
    assert all(item["health"] == "unknown_not_telemetry" for item in report.values())


def test_tick_is_local_metadata_snapshot() -> None:
    value = orchestrator()
    result = asyncio.run(value.tick())
    assert result["tick"] == 1
    assert result["evidence_state"] == value.evidence_state
    assert result["external_queries_executed"] == 0
    assert result["external_actions_executed"] == 0


def test_run_zero_ticks_is_empty() -> None:
    value = orchestrator()
    assert asyncio.run(value.run(0)) == []
    assert value.running is False


def test_run_two_ticks_is_deterministic_counter() -> None:
    value = orchestrator()
    snapshots = asyncio.run(value.run(2))
    assert [item["tick"] for item in snapshots] == [1, 2]
    assert all(item["external_actions_executed"] == 0 for item in snapshots)
    assert value.running is False


def test_run_rejects_boolean_duration() -> None:
    with pytest.raises(TypeError):
        asyncio.run(orchestrator().run(True))


def test_run_rejects_negative_duration() -> None:
    with pytest.raises(ValueError):
        asyncio.run(orchestrator().run(-1))


def test_tick_subsystem_rejects_execution() -> None:
    result = asyncio.run(orchestrator().tick_subsystem("security"))
    assert result["classification"] == "VERIFIED_SOURCE_PROMOTION"
    assert result["execution_rejected"] is True
    assert result["external_queries_executed"] == 0
    assert result["external_actions_executed"] == 0


def test_tick_subsystem_rejects_unknown_domain() -> None:
    with pytest.raises(KeyError):
        asyncio.run(orchestrator().tick_subsystem("unknown"))


def test_submit_task_records_non_execution_receipt() -> None:
    value = orchestrator()
    task = Task("t1", "attempt old runtime operation", TaskPriority.P1_HIGH)
    result = asyncio.run(value.submit_task(task))
    assert result == "t1"
    assert task.state is TaskState.REJECTED_NOT_RUNTIME
    assert task.result == {
        "executed": False,
        "requires_external_system": True,
        "external_actions_executed": 0,
    }
    assert value.tasks == [task]


def test_assign_task_has_no_runtime_assignee() -> None:
    task = Task("t1", "attempt assignment", TaskPriority.P2_MEDIUM)
    assert orchestrator().assign_task(task) is None
    assert task.state is TaskState.PENDING


def test_run_task_rejects_pending_task() -> None:
    value = orchestrator()
    task = Task("t1", "attempt execution", TaskPriority.P0_CRITICAL)
    result = asyncio.run(value.run_task(task))
    assert result["executed"] is False
    assert result["external_actions_executed"] == 0
    assert task.state is TaskState.REJECTED_NOT_RUNTIME


def test_task_requires_nonempty_identity() -> None:
    with pytest.raises(ValueError):
        Task(" ", "description", TaskPriority.P3_LOW)


def test_task_requires_typed_priority() -> None:
    with pytest.raises(TypeError):
        Task("t1", "description", "P1_HIGH")


def test_stop_is_idempotent() -> None:
    value = orchestrator()
    value.running = True
    value.stop()
    value.stop()
    assert value.running is False
