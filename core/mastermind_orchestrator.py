#!/usr/bin/env python3
"""Colossus Mastermind orchestration runtime.

This module restores the execution mechanics removed by the receipt-router rewrite
without reviving unsupported deployment claims.  It is a real local orchestration
runtime: it owns a task queue, piston registry, subsystem bindings, tick loop,
retries, health state, recovery attempts, and evidence-router composition.

Important truth boundary:
- local/runtime execution is not proof of company deployment or infrastructure access;
- sibling repositories are discovered only when they are actually present;
- unbound pistons never fabricate successful work;
- security/cooling/energy adapters execute the behavior provided by the current
  sibling source code, which may itself be simulation/proposal behavior;
- the portfolio receipt router remains an evidence subsystem rather than replacing
  the orchestration runtime.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional

from core.portfolio_router import PortfolioReceiptRouter

logger = logging.getLogger("Colossus.Mastermind")
DEFAULT_REGISTRY = Path(__file__).resolve().parents[1] / "PORTFOLIO_REGISTRY.json"
DEFAULT_ESTATE_ROOT = Path(__file__).resolve().parents[2]

TickHandler = Callable[[int], Awaitable[Mapping[str, Any]]]
SummaryHandler = Callable[[], Mapping[str, Any]]
TaskHandler = Callable[["Task"], Awaitable[Mapping[str, Any]]]


class TaskPriority(Enum):
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


class TaskState(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    BLOCKED_UNBOUND = "blocked_unbound"
    CANCELLED = "cancelled"


class SubsystemHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNBOUND = "unbound"


@dataclass
class Piston:
    piston_id: str
    name: str
    role: str
    lane: str
    subsystem_ref: Optional[str] = None
    status: str = "idle"
    tasks_completed: int = 0
    tasks_failed: int = 0
    max_concurrent: int = 1
    current_load: int = 0
    last_error: Optional[str] = None

    @property
    def health(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total else 1.0

    @property
    def capacity_available(self) -> bool:
        return self.current_load < self.max_concurrent and self.status != "disabled"


@dataclass
class Task:
    task_id: str
    description: str
    priority: TaskPriority
    state: TaskState = TaskState.PENDING
    assigned_piston: Optional[str] = None
    preferred_piston: Optional[str] = None
    required_lane: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string")
        if not isinstance(self.priority, TaskPriority):
            raise TypeError("priority must be a TaskPriority")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int):
            raise TypeError("max_retries must be an integer")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self.task_id = self.task_id.strip()
        self.description = self.description.strip()

    @property
    def duration(self) -> Optional[float]:
        if self.started_at is not None and self.completed_at is not None:
            return self.completed_at - self.started_at
        return None


@dataclass
class SubsystemBinding:
    name: str
    source: str
    tick_handler: TickHandler
    summary_handler: Optional[SummaryHandler] = None
    health: SubsystemHealth = SubsystemHealth.DEGRADED
    tick_count: int = 0
    last_tick_result: Optional[Dict[str, Any]] = None
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    recovery_attempts: int = 0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "health": self.health.value,
            "tick_count": self.tick_count,
            "anomalies": len(self.anomalies),
            "actions": len(self.actions),
            "error": self.error,
            "recovery_attempts": self.recovery_attempts,
        }


class MastermindOrchestrator:
    """Composable asynchronous orchestration runtime with evidence-bound state."""

    runtime_state = "LOCAL_ORCHESTRATION_RUNTIME_RESTORED"

    def __init__(
        self,
        registry_path: str | Path = DEFAULT_REGISTRY,
        *,
        estate_root: str | Path = DEFAULT_ESTATE_ROOT,
        discover_siblings: bool = True,
        tick_interval_seconds: float = 0.5,
    ) -> None:
        if tick_interval_seconds < 0:
            raise ValueError("tick_interval_seconds must be non-negative")
        self.registry_path = Path(registry_path)
        self.estate_root = Path(estate_root)
        self.router = PortfolioReceiptRouter.from_path(self.registry_path)
        self.tick_interval_seconds = float(tick_interval_seconds)

        self.pistons: Dict[str, Piston] = {}
        self.tasks: List[Task] = []
        self.task_queue: asyncio.PriorityQueue[tuple[int, int, Task]] = asyncio.PriorityQueue()
        self.running = False
        self.tick_count = 0
        self._queue_sequence = 0
        self.chain_history: List[Dict[str, Any]] = []
        self.health_history: List[Dict[str, Any]] = []
        self.subsystems: Dict[str, SubsystemBinding] = {}
        self.discovery: Dict[str, Dict[str, Any]] = {}
        self._task_handlers: Dict[str, TaskHandler] = {}
        self._adapter_instances: Dict[str, Any] = {}

        self._register_pistons()
        if discover_siblings:
            self.discover_sibling_subsystems()

    # ------------------------------------------------------------------
    # Capability registration
    # ------------------------------------------------------------------
    def _register_pistons(self) -> None:
        """Restore the historical 12-piston topology as executable capability slots.

        A piston without a subsystem or explicit task handler is *unbound*, not a
        fake-success worker.  Handlers can be registered at runtime.
        """
        specs = (
            ("stealth_microwave", "STEALTH-MICROWAVE", "Parallel Execution", "batch_acceleration", "cooling"),
            ("motion_forge", "MOTION-FORGE", "Legal Motion Generation", "legal_warfare", None),
            ("spiral_memory", "SPIRAL-MEMORY", "Memory Management", "memory_ops", None),
            ("aspen_federation", "ASPEN-FEDERATION", "Connector Orchestration", "connectors", None),
            ("rico_mapper", "RICO-MAPPER", "RICO Analysis", "legal_warfare", None),
            ("federal_escalation", "FEDERAL-ESCALATION", "Federal Court Filing", "legal_warfare", None),
            ("evidence_analyzer", "EVIDENCE-ANALYZER", "Evidence Processing", "forensics", "security"),
            ("notion_sync", "NOTION-SYNC", "Notion Integration", "integrations", None),
            ("morpheus_adapt", "MORPHEUS-ADAPT", "Adaptive Learning", "intelligence", None),
            ("constitutional_warfare", "CONSTITUTIONAL-WARFARE", "Constitutional Law", "legal_warfare", None),
            ("quantum_memory", "QUANTUM-MEMORY", "Advanced Memory", "memory_ops", None),
            ("holographic_mesh", "HOLOGRAPHIC-MESH", "Distributed Computing", "infrastructure", "energy"),
        )
        for piston_id, name, role, lane, subsystem_ref in specs:
            self.pistons[piston_id] = Piston(
                piston_id=piston_id,
                name=name,
                role=role,
                lane=lane,
                subsystem_ref=subsystem_ref,
            )

    def register_subsystem(
        self,
        name: str,
        tick_handler: TickHandler,
        *,
        source: str,
        summary_handler: Optional[SummaryHandler] = None,
        replace: bool = True,
    ) -> SubsystemBinding:
        if not name.strip():
            raise ValueError("subsystem name is required")
        if not callable(tick_handler):
            raise TypeError("tick_handler must be callable")
        if name in self.subsystems and not replace:
            raise ValueError(f"subsystem already registered: {name}")
        binding = SubsystemBinding(
            name=name,
            source=source,
            tick_handler=tick_handler,
            summary_handler=summary_handler,
        )
        self.subsystems[name] = binding
        self.discovery[name] = {
            "state": "bound",
            "source": source,
            "observed_at": time.time(),
        }
        return binding

    def register_task_handler(self, piston_id: str, handler: TaskHandler) -> None:
        if piston_id not in self.pistons:
            raise KeyError(f"unknown piston: {piston_id}")
        if not callable(handler):
            raise TypeError("handler must be callable")
        self._task_handlers[piston_id] = handler

    def unregister_task_handler(self, piston_id: str) -> None:
        self._task_handlers.pop(piston_id, None)

    # ------------------------------------------------------------------
    # Sibling discovery
    # ------------------------------------------------------------------
    def discover_sibling_subsystems(self) -> Dict[str, Dict[str, Any]]:
        """Attempt real local binding to sibling repos when they are present."""
        for name in ("cooling", "energy", "security"):
            self._discover_one(name)
        return {key: dict(value) for key, value in self.discovery.items()}

    def _discover_one(self, name: str) -> bool:
        try:
            if name == "cooling":
                self._bind_cooling()
            elif name == "energy":
                self._bind_energy()
            elif name == "security":
                self._bind_security()
            else:
                raise KeyError(name)
            return True
        except Exception as exc:
            self.discovery[name] = {
                "state": "unbound",
                "source": str(self.estate_root / f"xai-colossus-{name}"),
                "error": f"{type(exc).__name__}: {exc}",
                "observed_at": time.time(),
            }
            existing = self.subsystems.get(name)
            if existing is not None:
                existing.health = SubsystemHealth.OFFLINE
                existing.error = str(exc)
            return False

    @staticmethod
    def _load_module(module_name: str, path: Path) -> Any:
        if not path.is_file():
            raise FileNotFoundError(path)
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot build import spec for {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _bind_cooling(self) -> None:
        repo = self.estate_root / "xai-colossus-cooling"
        if not repo.is_dir():
            raise FileNotFoundError(repo)
        repo_text = str(repo)
        if repo_text not in sys.path:
            sys.path.insert(0, repo_text)
        from apex_core.thermal_orchestrator import (  # type: ignore[import-not-found]
            APEXThermalOrchestrator,
            CoolingMode,
            CoolingZone,
            ThermalNode,
        )

        manifest = {
            "version": getattr(APEXThermalOrchestrator, "VERSION", "UNKNOWN"),
            "thermal_thresholds": {
                "normal_max_c": 70,
                "warm_c": 70,
                "hot_c": 78,
                "critical_c": 85,
                "gpu_throttle_c": 90,
                "zone_crac_boost_c": 75,
                "zone_liquid_boost_c": 80,
                "shadow_anomaly_delta_c": 8,
                "shadow_ema_alpha": 0.05,
                "inlet_intervention_c": 27,
                "exhaust_intervention_c": 40,
                "power_intervention_pct": 0.90,
            },
            "tick_config": {
                "tick_interval_ms": 500,
                "microwave_sweep_every_n_ticks": 5,
                "max_crac_units": 8,
                "liquid_boost_lpm": 10.0,
            },
        }
        orchestrator = APEXThermalOrchestrator(mode=CoolingMode.COLOSSUS, manifest=manifest)
        zone = CoolingZone(zone_id="ZONE-A", zone_name="Mastermind Integration Zone")
        for index, temp in enumerate((65.0, 70.0, 75.0, 80.0)):
            zone.nodes.append(
                ThermalNode(
                    node_id=f"NODE-{index:03d}",
                    rack_id=f"RACK-{index:03d}",
                    zone_id="ZONE-A",
                    temp_celsius=temp,
                    gpu_utilization=0.8,
                    power_watts=700,
                )
            )
        orchestrator.register_zone(zone)
        self._adapter_instances["cooling"] = orchestrator

        async def tick_handler(_: int) -> Mapping[str, Any]:
            return await orchestrator.tick_cycle()

        summary = getattr(orchestrator, "summary", None)
        self.register_subsystem(
            "cooling",
            tick_handler,
            source=str(repo),
            summary_handler=summary if callable(summary) else None,
        )

    def _bind_energy(self) -> None:
        repo = self.estate_root / "xai-colossus-energy"
        module = self._load_module("colossus_energy_grid_balancer", repo / "energy" / "grid_balancer.py")
        balancer = module.GridBalancer()
        self._adapter_instances["energy"] = balancer

        async def tick_handler(tick_num: int) -> Mapping[str, Any]:
            zones = {f"Z{index}": {"gpu_utilization": 0.8} for index in range(4)}
            return await balancer.tick(zones, tick_num)

        self.register_subsystem(
            "energy",
            tick_handler,
            source=str(repo),
            summary_handler=balancer.summary,
        )

    def _bind_security(self) -> None:
        repo = self.estate_root / "xai-colossus-security"
        module = self._load_module("colossus_security_hydra", repo / "security" / "hydra_immune.py")
        hydra = module.HydraImmune()
        self._adapter_instances["security"] = hydra

        async def tick_handler(tick_num: int) -> Mapping[str, Any]:
            return await hydra.tick({}, tick_num)

        self.register_subsystem(
            "security",
            tick_handler,
            source=str(repo),
            summary_handler=hydra.summary,
        )

    def recover_subsystem(self, name: str) -> bool:
        """Perform a real rebind attempt rather than flipping a health label."""
        existing = self.subsystems.get(name)
        if existing is not None:
            existing.recovery_attempts += 1
        self._adapter_instances.pop(name, None)
        self.subsystems.pop(name, None)
        return self._discover_one(name)

    # ------------------------------------------------------------------
    # Runtime execution
    # ------------------------------------------------------------------
    async def tick_subsystem(self, name: str) -> Dict[str, Any]:
        binding = self.subsystems.get(name)
        if binding is None:
            discovery = self.discovery.get(name) or {
                "state": "unbound",
                "error": "no runtime binding registered",
            }
            return {
                "subsystem": name,
                "executed": False,
                "binding_state": discovery.get("state", "unbound"),
                "error": discovery.get("error", "no runtime binding registered"),
                "evidence_record": self.router.route(name) if name in self.router.domains() else None,
            }

        try:
            result = dict(await binding.tick_handler(binding.tick_count + 1))
            binding.tick_count += 1
            binding.last_tick_result = result
            raw_anomalies = result.get("anomalies") or []
            raw_actions = result.get("actions") or []
            binding.anomalies = list(raw_anomalies) if isinstance(raw_anomalies, list) else []
            binding.actions = list(raw_actions) if isinstance(raw_actions, list) else []
            binding.error = None
            critical = any(
                str(item.get("severity", "")).upper() == "CRITICAL"
                for item in binding.anomalies
                if isinstance(item, Mapping)
            )
            binding.health = SubsystemHealth.DEGRADED if critical else SubsystemHealth.HEALTHY
            return {
                "subsystem": name,
                "executed": True,
                "source": binding.source,
                "health": binding.health.value,
                "tick_count": binding.tick_count,
                "result": result,
            }
        except Exception as exc:
            binding.health = SubsystemHealth.CRITICAL
            binding.error = f"{type(exc).__name__}: {exc}"
            logger.exception("subsystem %s tick failed", name)
            return {
                "subsystem": name,
                "executed": False,
                "source": binding.source,
                "health": binding.health.value,
                "error": binding.error,
            }

    async def monitor_health(self, *, recover: bool = True) -> Dict[str, Any]:
        report: Dict[str, Any] = {}
        names = sorted(set(self.router.domains()) | set(self.discovery) | set(self.subsystems))
        for name in names:
            if name in self.subsystems:
                result = await self.tick_subsystem(name)
                report[name] = {
                    **self.subsystems[name].snapshot(),
                    "executed": result.get("executed", False),
                }
                if recover and self.subsystems[name].health is SubsystemHealth.CRITICAL:
                    recovered = self.recover_subsystem(name)
                    report[name]["recovery_attempted"] = True
                    report[name]["rebound"] = recovered
            else:
                discovery = self.discovery.get(name, {"state": "unbound"})
                report[name] = {
                    "health": SubsystemHealth.UNBOUND.value,
                    "executed": False,
                    "binding_state": discovery.get("state", "unbound"),
                    "error": discovery.get("error"),
                    "evidence_record": self.router.route(name) if name in self.router.domains() else None,
                }

        self.health_history.append(
            {
                "tick": self.tick_count,
                "timestamp": time.time(),
                "report": report,
            }
        )
        return report

    def _piston_executable(self, piston: Piston) -> bool:
        if piston.piston_id in self._task_handlers:
            return True
        return bool(piston.subsystem_ref and piston.subsystem_ref in self.subsystems)

    def assign_task(self, task: Task) -> Optional[str]:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        candidates = [
            piston
            for piston in self.pistons.values()
            if piston.capacity_available and self._piston_executable(piston)
        ]
        if task.preferred_piston:
            candidates = [p for p in candidates if p.piston_id == task.preferred_piston]
        if task.required_lane:
            candidates = [p for p in candidates if p.lane == task.required_lane]
        if not candidates:
            return None
        best = max(candidates, key=lambda p: (p.health, -p.current_load))
        task.assigned_piston = best.piston_id
        task.state = TaskState.ASSIGNED
        best.current_load += 1
        return best.piston_id

    async def run_task(self, task: Task) -> Dict[str, Any]:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if task.assigned_piston is None:
            if self.assign_task(task) is None:
                task.state = TaskState.BLOCKED_UNBOUND
                task.error = "no executable piston matches this task"
                return {
                    "executed": False,
                    "task_id": task.task_id,
                    "state": task.state.value,
                    "error": task.error,
                }

        piston = self.pistons[task.assigned_piston]
        task.state = TaskState.RUNNING
        task.started_at = time.time()
        piston.status = "busy"
        try:
            handler = self._task_handlers.get(piston.piston_id)
            if handler is not None:
                result = dict(await handler(task))
            elif piston.subsystem_ref:
                result = await self.tick_subsystem(piston.subsystem_ref)
                if not result.get("executed"):
                    raise RuntimeError(result.get("error") or "subsystem execution failed")
            else:
                raise RuntimeError("piston has no bound execution handler")

            task.state = TaskState.COMPLETED
            task.result = result
            task.completed_at = time.time()
            task.error = None
            piston.tasks_completed += 1
            piston.last_error = None
            return {
                "executed": True,
                "task_id": task.task_id,
                "piston": piston.piston_id,
                "state": task.state.value,
                "result": result,
            }
        except Exception as exc:
            task.error = f"{type(exc).__name__}: {exc}"
            piston.tasks_failed += 1
            piston.last_error = task.error
            if task.retries < task.max_retries:
                task.retries += 1
                task.state = TaskState.RETRYING
                await self._enqueue(task)
            else:
                task.state = TaskState.FAILED
                task.completed_at = time.time()
            return {
                "executed": False,
                "task_id": task.task_id,
                "piston": piston.piston_id,
                "state": task.state.value,
                "error": task.error,
                "retries": task.retries,
            }
        finally:
            piston.current_load = max(0, piston.current_load - 1)
            piston.status = "idle"

    async def _enqueue(self, task: Task) -> None:
        self._queue_sequence += 1
        await self.task_queue.put((task.priority.value, self._queue_sequence, task))

    async def submit_task(self, task: Task) -> str:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if any(existing.task_id == task.task_id for existing in self.tasks):
            raise ValueError(f"duplicate task_id: {task.task_id}")
        await self._enqueue(task)
        self.tasks.append(task)
        return task.task_id

    async def chain_tasks(self, tasks: List[Task]) -> List[str]:
        ids: List[str] = []
        for task in tasks:
            ids.append(await self.submit_task(task))
        self.chain_history.append({"tasks": ids, "created_at": time.time()})
        return ids

    async def process_tasks(self, *, max_tasks: int = 10) -> List[Dict[str, Any]]:
        if isinstance(max_tasks, bool) or not isinstance(max_tasks, int) or max_tasks < 0:
            raise ValueError("max_tasks must be a non-negative integer")
        results: List[Dict[str, Any]] = []
        for _ in range(max_tasks):
            if self.task_queue.empty():
                break
            _, _, task = await self.task_queue.get()
            if task.state in {TaskState.PENDING, TaskState.RETRYING}:
                task.assigned_piston = None
                task.state = TaskState.PENDING
                results.append(await self.run_task(task))
            self.task_queue.task_done()
        return results

    async def tick(self) -> Dict[str, Any]:
        self.tick_count += 1
        health = await self.monitor_health()
        task_results = await self.process_tasks(max_tasks=10)
        return {
            "tick": self.tick_count,
            "runtime_state": self.runtime_state,
            "health": health,
            "tasks_processed": len(task_results),
            "task_results": task_results,
            "evidence_summary": self.router.summary(),
        }

    async def run(
        self,
        duration_ticks: int = 100,
        *,
        interval_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        if isinstance(duration_ticks, bool) or not isinstance(duration_ticks, int):
            raise TypeError("duration_ticks must be an integer")
        if duration_ticks < 0:
            raise ValueError("duration_ticks must be non-negative")
        interval = self.tick_interval_seconds if interval_seconds is None else float(interval_seconds)
        if interval < 0:
            raise ValueError("interval_seconds must be non-negative")

        self.running = True
        history: List[Dict[str, Any]] = []
        try:
            for _ in range(duration_ticks):
                if not self.running:
                    break
                history.append(await self.tick())
                if interval:
                    await asyncio.sleep(interval)
        finally:
            self.running = False
        return history

    def stop(self) -> None:
        self.running = False

    def summary(self) -> Dict[str, Any]:
        completed = sum(task.state is TaskState.COMPLETED for task in self.tasks)
        failed = sum(task.state is TaskState.FAILED for task in self.tasks)
        pending = sum(
            task.state in {TaskState.PENDING, TaskState.RETRYING, TaskState.ASSIGNED, TaskState.RUNNING}
            for task in self.tasks
        )
        blocked = sum(task.state is TaskState.BLOCKED_UNBOUND for task in self.tasks)
        return {
            "runtime_state": self.runtime_state,
            "runtime_orchestration_available": True,
            "tick_count": self.tick_count,
            "running": self.running,
            "total_tasks": len(self.tasks),
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "blocked_unbound": blocked,
            "bound_subsystems": sorted(self.subsystems),
            "discovery": {key: dict(value) for key, value in self.discovery.items()},
            "subsystems": {key: value.snapshot() for key, value in self.subsystems.items()},
            "pistons": {
                piston.piston_id: {
                    "role": piston.role,
                    "lane": piston.lane,
                    "subsystem_ref": piston.subsystem_ref,
                    "executable": self._piston_executable(piston),
                    "health": piston.health,
                    "tasks_completed": piston.tasks_completed,
                    "tasks_failed": piston.tasks_failed,
                    "status": piston.status,
                }
                for piston in self.pistons.values()
            },
            "evidence_router": self.router.summary(),
            "truth_boundary": (
                "local orchestration/runtime behavior does not establish external company deployment "
                "or physical-infrastructure authority"
            ),
        }


async def _main() -> None:
    orchestrator = MastermindOrchestrator()
    print(await orchestrator.tick())


if __name__ == "__main__":
    asyncio.run(_main())
