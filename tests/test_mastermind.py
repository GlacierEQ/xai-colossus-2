"""Regression tests for the repair-forward Mastermind orchestration runtime."""

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
    return MastermindOrchestrator(
        REGISTRY,
        discover_siblings=False,
        tick_interval_seconds=0,
    )


def bind_security(value: MastermindOrchestrator):
    calls = []

    async def tick_handler(tick_num: int):
        calls.append(tick_num)
        return {
            "anomalies": [],
            "actions": [{"action": "LOCAL_ANALYSIS", "executed": True}],
            "threat_level": "NONE",
            "external_actions_executed": 0,
        }

    value.register_subsystem(
        "security",
        tick_handler,
        source="test://security",
        summary_handler=lambda: {"state": "ready"},
    )
    return calls


def test_runtime_loads_local_evidence_router_without_collapsing_into_it() -> None:
    value = orchestrator()
    assert value.registry_path == REGISTRY
    assert value.runtime_state == "LOCAL_ORCHESTRATION_RUNTIME_RESTORED"
    assert value.router.summary()["verified_source_count"] == 5
    assert value.summary()["runtime_orchestration_available"] is True


def test_historical_piston_topology_is_restored_as_capability_slots() -> None:
    value = orchestrator()
    assert len(value.pistons) == 12
    assert "stealth_microwave" in value.pistons
    assert "motion_forge" in value.pistons
    assert "evidence_analyzer" in value.pistons
    assert value.pistons["evidence_analyzer"].subsystem_ref == "security"


def test_unbound_subsystem_is_truthful_not_fake_success() -> None:
    value = orchestrator()
    result = asyncio.run(value.tick_subsystem("security"))
    assert result["executed"] is False
    assert result["binding_state"] == "unbound"
    assert result["evidence_record"] is not None


def test_runtime_executes_registered_subsystem_tick() -> None:
    value = orchestrator()
    calls = bind_security(value)
    result = asyncio.run(value.tick_subsystem("security"))
    assert result["executed"] is True
    assert result["health"] == SubsystemHealth.HEALTHY.value
    assert result["tick_count"] == 1
    assert calls == [1]
    assert value.subsystems["security"].actions[0]["action"] == "LOCAL_ANALYSIS"


def test_monitor_health_executes_bound_subsystem_and_preserves_unbound_domains() -> None:
    value = orchestrator()
    bind_security(value)
    report = asyncio.run(value.monitor_health(recover=False))
    assert report["security"]["executed"] is True
    assert report["security"]["health"] == "healthy"
    assert report["microcode"]["executed"] is False
    assert report["microcode"]["health"] == "unbound"


def test_task_assignment_requires_real_execution_binding() -> None:
    value = orchestrator()
    task = Task(
        "t1",
        "unbound legal operation",
        TaskPriority.P1_HIGH,
        preferred_piston="motion_forge",
    )
    result = asyncio.run(value.run_task(task))
    assert result["executed"] is False
    assert task.state is TaskState.BLOCKED_UNBOUND


def test_bound_subsystem_piston_executes_task() -> None:
    value = orchestrator()
    bind_security(value)
    task = Task(
        "t1",
        "analyze security state",
        TaskPriority.P0_CRITICAL,
        preferred_piston="evidence_analyzer",
    )
    result = asyncio.run(value.run_task(task))
    assert result["executed"] is True
    assert result["piston"] == "evidence_analyzer"
    assert task.state is TaskState.COMPLETED
    assert value.pistons["evidence_analyzer"].tasks_completed == 1


def test_explicit_task_handler_turns_capability_slot_into_executor() -> None:
    value = orchestrator()

    async def handler(task: Task):
        return {"artifact": task.payload["artifact"], "verified": True}

    value.register_task_handler("motion_forge", handler)
    task = Task(
        "motion-1",
        "generate artifact",
        TaskPriority.P1_HIGH,
        preferred_piston="motion_forge",
        payload={"artifact": "draft"},
    )
    result = asyncio.run(value.run_task(task))
    assert result["executed"] is True
    assert result["result"] == {"artifact": "draft", "verified": True}
    assert task.state is TaskState.COMPLETED


def test_queue_processes_priority_and_real_handlers() -> None:
    value = orchestrator()
    order = []

    async def handler(task: Task):
        order.append(task.task_id)
        return {"ok": True}

    value.register_task_handler("motion_forge", handler)
    low = Task("low", "low", TaskPriority.P3_LOW, preferred_piston="motion_forge")
    high = Task("high", "high", TaskPriority.P0_CRITICAL, preferred_piston="motion_forge")

    async def scenario():
        await value.submit_task(low)
        await value.submit_task(high)
        return await value.process_tasks(max_tasks=2)

    results = asyncio.run(scenario())
    assert order == ["high", "low"]
    assert all(item["executed"] is True for item in results)


def test_retry_requeues_failed_task_then_completes() -> None:
    value = orchestrator()
    attempts = {"count": 0}

    async def flaky(task: Task):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient")
        return {"ok": True}

    value.register_task_handler("motion_forge", flaky)
    task = Task(
        "retry",
        "retry me",
        TaskPriority.P1_HIGH,
        preferred_piston="motion_forge",
        max_retries=1,
    )

    async def scenario():
        await value.submit_task(task)
        first = await value.process_tasks(max_tasks=1)
        second = await value.process_tasks(max_tasks=1)
        return first, second

    first, second = asyncio.run(scenario())
    assert first[0]["executed"] is False
    assert first[0]["state"] == TaskState.RETRYING.value
    assert second[0]["executed"] is True
    assert task.state is TaskState.COMPLETED
    assert attempts["count"] == 2


def test_chain_tasks_preserves_order_of_submission() -> None:
    value = orchestrator()
    tasks = [
        Task("a", "first", TaskPriority.P1_HIGH),
        Task("b", "second", TaskPriority.P1_HIGH),
    ]
    ids = asyncio.run(value.chain_tasks(tasks))
    assert ids == ["a", "b"]
    assert value.chain_history[-1]["tasks"] == ["a", "b"]


def test_run_executes_real_ticks_without_forced_sleep() -> None:
    value = orchestrator()
    bind_security(value)
    history = asyncio.run(value.run(2, interval_seconds=0))
    assert [item["tick"] for item in history] == [1, 2]
    assert all(item["runtime_state"] == "LOCAL_ORCHESTRATION_RUNTIME_RESTORED" for item in history)
    assert value.running is False


def test_run_validates_duration() -> None:
    with pytest.raises(TypeError):
        asyncio.run(orchestrator().run(True))
    with pytest.raises(ValueError):
        asyncio.run(orchestrator().run(-1))


def test_duplicate_task_identity_is_rejected() -> None:
    value = orchestrator()
    task = Task("same", "one", TaskPriority.P1_HIGH)

    async def scenario():
        await value.submit_task(task)
        await value.submit_task(Task("same", "two", TaskPriority.P2_MEDIUM))

    with pytest.raises(ValueError):
        asyncio.run(scenario())


def test_task_validation_and_stop_are_strict() -> None:
    with pytest.raises(ValueError):
        Task(" ", "description", TaskPriority.P3_LOW)
    with pytest.raises(TypeError):
        Task("t1", "description", "P1_HIGH")

    value = orchestrator()
    value.running = True
    value.stop()
    value.stop()
    assert value.running is False
