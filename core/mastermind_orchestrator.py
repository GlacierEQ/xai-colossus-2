#!/usr/bin/env python3
"""Compatibility facade over the local portfolio evidence router.

Historical versions of this module claimed autonomous subsystem loading,
health monitoring, task execution, auto-restart, and legal/infrastructure
pistons. Those behaviors are non-authoritative and are not preserved here.

The current facade reads one local JSON registry, returns evidence metadata,
and executes no subsystem, network, hardware, legal, or external action.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from core.portfolio_router import PortfolioReceiptRouter

DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "PORTFOLIO_REGISTRY.json"


class TaskPriority(Enum):
    """Legacy import-compatible labels; they do not authorize execution."""

    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


class TaskState(str, Enum):
    """Legacy task states with a mandatory non-executing outcome."""

    PENDING = "pending"
    REJECTED_NOT_RUNTIME = "rejected_not_runtime"


class SubsystemHealth(str, Enum):
    """Evidence state is not operational health; UNKNOWN is the only valid value."""

    UNKNOWN_NOT_TELEMETRY = "unknown_not_telemetry"


@dataclass
class Task:
    """Compatibility record for rejected runtime-task requests."""

    task_id: str
    description: str
    priority: TaskPriority
    state: TaskState = TaskState.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        for name in ("task_id", "description"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            setattr(self, name, value.strip())
        if not isinstance(self.priority, TaskPriority):
            raise TypeError("priority must be a TaskPriority")


class MastermindOrchestrator:
    """Read-only compatibility facade; not a runtime orchestrator.

    This class intentionally preserves the historical import path while
    changing the contract to fail closed. It does not load sibling repositories,
    call tick methods, infer health, start processes, or execute tasks.
    """

    evidence_state = "LOCAL_METADATA_ROUTER_NOT_RUNTIME_ORCHESTRATOR"

    def __init__(self, registry_path: str | Path = DEFAULT_REGISTRY) -> None:
        self.registry_path = Path(registry_path)
        self.router = PortfolioReceiptRouter.from_path(self.registry_path)
        self.tick_count = 0
        self.running = False
        self.pistons: dict[str, Any] = {}
        self.tasks: list[Task] = []
        self.subsystems = {
            domain_id: {
                "classification": self.router.route(domain_id)["classification"],
                "health": SubsystemHealth.UNKNOWN_NOT_TELEMETRY.value,
                "telemetry_available": False,
                "external_queries_executed": 0,
                "external_actions_executed": 0,
            }
            for domain_id in self.router.domains()
        }

    def summary(self) -> dict:
        return {
            **self.router.summary(),
            "compatibility_facade": "MastermindOrchestrator",
            "runtime_orchestration_available": False,
            "subsystems": self.subsystems,
            "pistons": {},
            "tick_count": self.tick_count,
            "external_queries_executed": 0,
            "external_actions_executed": 0,
        }

    async def monitor_health(self) -> dict[str, dict]:
        """Return evidence metadata, never inferred operational health."""

        return {key: dict(value) for key, value in self.subsystems.items()}

    async def tick(self) -> dict:
        """Produce one local metadata snapshot without external activity."""

        self.tick_count += 1
        return {
            "tick": self.tick_count,
            "evidence_state": self.evidence_state,
            "summary": self.router.summary(),
            "external_queries_executed": 0,
            "external_actions_executed": 0,
        }

    async def run(self, duration_ticks: int = 1) -> list[dict]:
        """Return deterministic local snapshots; no clock loop or sleep occurs."""

        if isinstance(duration_ticks, bool) or not isinstance(duration_ticks, int):
            raise TypeError("duration_ticks must be an integer")
        if duration_ticks < 0:
            raise ValueError("duration_ticks must be non-negative")
        self.running = True
        snapshots = [await self.tick() for _ in range(duration_ticks)]
        self.running = False
        return snapshots

    def stop(self) -> None:
        self.running = False

    async def tick_subsystem(self, name: str) -> dict:
        """Reject historical subsystem execution while returning its evidence record."""

        record = self.router.route(name)
        return {
            "domain_id": name,
            "classification": record["classification"],
            "execution_rejected": True,
            "reason": "public suite hub is a local metadata router, not a subsystem runtime",
            "external_queries_executed": 0,
            "external_actions_executed": 0,
        }

    async def submit_task(self, task: Task) -> str:
        """Record and reject a historical runtime task request."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        task.state = TaskState.REJECTED_NOT_RUNTIME
        task.error = "task execution is unavailable in the public receipt router"
        task.result = {
            "executed": False,
            "requires_external_system": True,
            "external_actions_executed": 0,
        }
        self.tasks.append(task)
        return task.task_id

    def assign_task(self, task: Task) -> None:
        """Fail closed: there are no runtime pistons or task assignees."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        return None

    async def run_task(self, task: Task) -> dict:
        """Fail closed and preserve a machine-readable non-execution receipt."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if task.state is TaskState.PENDING:
            await self.submit_task(task)
        return dict(task.result or {})


async def _main() -> None:
    orchestrator = MastermindOrchestrator()
    print(await orchestrator.tick())


if __name__ == "__main__":
    asyncio.run(_main())
