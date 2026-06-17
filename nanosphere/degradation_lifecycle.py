#!/usr/bin/env python3
"""
Colossus 2 — Nanofluid Degradation Lifecycle Manager
=====================================================
Tracks batch-level nanoparticle degradation across all immersion circuits.

Five-state lifecycle: ACTIVE → DEGRADATION_WARNING → REPLACEMENT_DUE →
                       REPLACEMENT_SCHEDULED → RETIRED

Exponential decay model: k(t) = k_fresh * e^(-ln2 * t / half_life)

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from physics.constants import PARTICLE_DATABASE, BASE_FLUID_THERMAL_CONDUCTIVITY

logger = logging.getLogger("COLOSSUS-NANOSPHERE")


class LifecycleState(Enum):
    ACTIVE = "ACTIVE"
    DEGRADATION_WARNING = "DEGRADATION_WARNING"
    REPLACEMENT_DUE = "REPLACEMENT_DUE"
    REPLACEMENT_SCHEDULED = "REPLACEMENT_SCHEDULED"
    RETIRED = "RETIRED"


@dataclass
class BatchLifecycle:
    batch_id: str
    circuit_id: str
    nanoparticle: str
    volume_fraction: float
    install_date: str
    age_days: float = 0.0
    state: LifecycleState = LifecycleState.ACTIVE
    fresh_enhancement_pct: float = 0.0
    current_enhancement_pct: float = 0.0
    half_life_days: float = 180.0
    warning_threshold: float = 0.75
    due_threshold: float = 0.50
    last_evaluation_tick: int = 0

    def __post_init__(self):
        if self.nanoparticle in PARTICLE_DATABASE:
            db = PARTICLE_DATABASE[self.nanoparticle]
            self.fresh_enhancement_pct = db["fresh_enhancement_pct"]
            self.half_life_days = db["half_life_days"]
            self.current_enhancement_pct = self.fresh_enhancement_pct


@dataclass
class ReplacementEntry:
    batch_id: str
    circuit_id: str
    nanoparticle: str
    priority: int
    days_overdue: float
    current_enhancement_pct: float
    replacement_cost_factor: float


class FleetLifecycleManager:
    def __init__(self, nanosphere_config: Dict[str, Any]):
        self.config = nanosphere_config
        self.halflife_days_default = nanosphere_config.get("degradation_halflife_days", 180)
        self.warning_fraction = nanosphere_config.get("warning_fraction", 0.75)
        self.due_fraction = nanosphere_config.get("due_fraction", 0.50)
        self._batches: Dict[str, BatchLifecycle] = {}
        self._retired_count = 0
        logger.info("COLOSSUS-NANOSPHERE: FleetLifecycleManager initialized halflife=%d days",
                     self.halflife_days_default)

    def register_batch(
        self,
        circuit_id: str,
        nanoparticle: str,
        volume_fraction: float,
        install_date: Optional[str] = None,
    ) -> BatchLifecycle:
        if nanoparticle not in PARTICLE_DATABASE:
            raise ValueError(f"Unknown nanoparticle: {nanoparticle}")
        batch_id = f"BATCH-{circuit_id}-{nanoparticle[:3].upper()}-{uuid.uuid4().hex[:6]}"
        if install_date is None:
            install_date = datetime.now(timezone.utc).isoformat()
        batch = BatchLifecycle(
            batch_id=batch_id,
            circuit_id=circuit_id,
            nanoparticle=nanoparticle,
            volume_fraction=volume_fraction,
            install_date=install_date,
            half_life_days=PARTICLE_DATABASE[nanoparticle]["half_life_days"],
            warning_threshold=self.warning_fraction,
            due_threshold=self.due_fraction,
        )
        self._batches[batch_id] = batch
        logger.info("COLOSSUS-NANOSPHERE: Batch registered %s circuit=%s particle=%s phi=%.3f",
                     batch_id, circuit_id, nanoparticle, volume_fraction)
        return batch

    def conductivity_factor(self, batch: BatchLifecycle, temperature_k: float = 323.15) -> float:
        phi = batch.volume_fraction
        k_f = BASE_FLUID_THERMAL_CONDUCTIVITY
        if batch.nanoparticle not in PARTICLE_DATABASE:
            return 1.0
        k_p = PARTICLE_DATABASE[batch.nanoparticle]["thermal_conductivity_wmk"]
        k_eff = k_f * (k_p + 2.0 * k_f + 2.0 * phi * (k_p - k_f)) / \
                        (k_p + 2.0 * k_f - phi * (k_p - k_f))
        ea_over_r = 2000.0
        t_ref = 323.15
        temp_factor = math.exp(-ea_over_r * (1.0 / temperature_k - 1.0 / t_ref))
        degradation = math.exp(-math.log(2.0) * batch.age_days / batch.half_life_days) * temp_factor
        enhancement = (k_eff / k_f - 1.0) * degradation
        return 1.0 + enhancement

    def update_batch_age(self, batch_id: str, age_days: float) -> None:
        if batch_id not in self._batches:
            return
        batch = self._batches[batch_id]
        batch.age_days = age_days
        degradation = math.exp(-math.log(2.0) * age_days / batch.half_life_days)
        batch.current_enhancement_pct = batch.fresh_enhancement_pct * degradation
        ratio = batch.current_enhancement_pct / batch.fresh_enhancement_pct if batch.fresh_enhancement_pct > 0 else 1.0

        if ratio <= batch.due_threshold and batch.state in (
            LifecycleState.ACTIVE, LifecycleState.DEGRADATION_WARNING
        ):
            batch.state = LifecycleState.REPLACEMENT_DUE
            logger.warning("COLOSSUS-NANOSPHERE: Batch %s REPLACEMENT_DUE age=%.0f days",
                           batch_id, age_days)
        elif ratio <= batch.warning_threshold and batch.state == LifecycleState.ACTIVE:
            batch.state = LifecycleState.DEGRADATION_WARNING
            logger.info("COLOSSUS-NANOSPHERE: Batch %s DEGRADATION_WARNING age=%.0f days",
                        batch_id, age_days)

    def evaluate_batch(self, batch_id: str, current_tick: int, days_per_tick: float = 0.005787) -> Dict[str, Any]:
        if batch_id not in self._batches:
            return {"error": f"Batch {batch_id} not found"}
        batch = self._batches[batch_id]
        age_days = current_tick * days_per_tick
        self.update_batch_age(batch_id, age_days)
        batch.last_evaluation_tick = current_tick
        k_factor = self.conductivity_factor(batch)
        return {
            "batch_id": batch_id,
            "state": batch.state.value,
            "age_days": round(age_days, 1),
            "conductivity_factor": round(k_factor, 4),
            "enhancement_pct": round(batch.current_enhancement_pct, 2),
            "degradation_pct": round((1.0 - batch.current_enhancement_pct / batch.fresh_enhancement_pct) * 100, 1),
        }

    def schedule_replacement(self, batch_id: str) -> bool:
        if batch_id not in self._batches:
            return False
        batch = self._batches[batch_id]
        if batch.state == LifecycleState.REPLACEMENT_DUE:
            batch.state = LifecycleState.REPLACEMENT_SCHEDULED
            logger.info("COLOSSUS-NANOSPHERE: Batch %s REPLACEMENT_SCHEDULED", batch_id)
            return True
        return False

    def retire_batch(self, batch_id: str) -> bool:
        if batch_id not in self._batches:
            return False
        batch = self._batches[batch_id]
        if batch.state in (LifecycleState.REPLACEMENT_DUE, LifecycleState.REPLACEMENT_SCHEDULED):
            batch.state = LifecycleState.RETIRED
            self._retired_count += 1
            logger.info("COLOSSUS-NANOSPHERE: Batch %s RETIRED total_retired=%d",
                        batch_id, self._retired_count)
            return True
        return False

    def generate_replacement_schedule(self) -> List[ReplacementEntry]:
        due_batches = [
            b for b in self._batches.values()
            if b.state in (LifecycleState.REPLACEMENT_DUE, LifecycleState.REPLACEMENT_SCHEDULED)
        ]
        entries = []
        for batch in due_batches:
            days_overdue = batch.age_days - (batch.half_life_days * math.log2(1.0 / batch.due_threshold))
            priority = max(1, int(100 - (batch.current_enhancement_pct / batch.fresh_enhancement_pct * 100)))
            entries.append(ReplacementEntry(
                batch_id=batch.batch_id,
                circuit_id=batch.circuit_id,
                nanoparticle=batch.nanoparticle,
                priority=priority,
                days_overdue=round(max(0, days_overdue), 1),
                current_enhancement_pct=round(batch.current_enhancement_pct, 2),
                replacement_cost_factor=PARTICLE_DATABASE.get(batch.nanoparticle, {}).get("cost_factor", 1.0),
            ))
        entries.sort(key=lambda e: (-e.priority, -e.days_overdue))
        return entries

    def active_batches(self) -> List[BatchLifecycle]:
        return [b for b in self._batches.values() if b.state != LifecycleState.RETIRED]

    def all_batches(self) -> List[BatchLifecycle]:
        return list(self._batches.values())

    def summary(self) -> Dict[str, Any]:
        states = {}
        for batch in self._batches.values():
            states[batch.state.value] = states.get(batch.state.value, 0) + 1
        active = self.active_batches()
        avg_kf = (
            sum(self.conductivity_factor(b) for b in active) / len(active)
            if active else 1.0
        )
        return {
            "total_batches": len(self._batches),
            "active_batches": len(active),
            "state_distribution": states,
            "retired_total": self._retired_count,
            "avg_conductivity_factor": round(avg_kf, 4),
        }
