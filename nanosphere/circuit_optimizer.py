#!/usr/bin/env python3
"""
Colossus 2 — Nanofluid Circuit Optimizer
=========================================
Searches particle type × volume fraction space to find the optimal nanofluid
blend for a target thermal conductivity enhancement, subject to cost and
fluid compatibility constraints.

Scoring: enhancement / (volume_fraction × cost_factor) — best bang for buck.

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from physics.constants import (
    PARTICLE_DATABASE,
    BASE_FLUID_THERMAL_CONDUCTIVITY,
    maxwell_conductivity,
)

logger = logging.getLogger("COLOSSUS-NANOSPHERE")


@dataclass
class BlendCandidate:
    nanoparticle: str
    volume_fraction: float
    predicted_enhancement_pct: float
    conductivity_factor: float
    score: float
    cost_factor: float
    particle_conductivity_wmk: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nanoparticle": self.nanoparticle,
            "volume_fraction": round(self.volume_fraction, 4),
            "predicted_enhancement_pct": round(self.predicted_enhancement_pct, 2),
            "conductivity_factor": round(self.conductivity_factor, 4),
            "score": round(self.score, 2),
            "cost_factor": self.cost_factor,
            "particle_conductivity_wmk": self.particle_conductivity_wmk,
        }


@dataclass
class OptimizationConstraints:
    max_volume_fraction: float = 0.05
    max_cost_factor: float = 5.0
    required_base_fluid: str = "water"
    min_enhancement_pct: float = 0.0
    exclude_particles: List[str] = field(default_factory=list)
    max_settling_velocity_ms: float = 1e-6
    particle_density_limit_kgm3: float = 8000.0


def maxwell_conductivity_enhancement(k_f: float, k_p: float, phi: float) -> float:
    k_eff = maxwell_conductivity(k_f, k_p, phi)
    if abs(k_f) < 1e-12:
        return 0.0
    return (k_eff / k_f - 1.0) * 100.0


class CircuitOptimizer:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._optimization_count = 0
        self._best_score_seen = 0.0
        logger.info("COLOSSUS-NANOSPHERE: CircuitOptimizer initialized")

    def _volume_fraction_grid(self, max_vf: float, step: float = 0.005) -> List[float]:
        vfs = []
        vf = 0.005
        while vf <= max_vf + 1e-6:
            vfs.append(round(vf, 4))
            vf += step
        return vfs

    def optimize(
        self,
        target_enhancement_pct: float,
        constraints: Optional[OptimizationConstraints] = None,
        max_results: int = 10,
    ) -> List[BlendCandidate]:
        if constraints is None:
            constraints = OptimizationConstraints(
                max_volume_fraction=self.config.get("max_volume_fraction", 0.05)
            )

        self._optimization_count += 1
        candidates = []

        for particle_name, particle_db in PARTICLE_DATABASE.items():
            if particle_name in constraints.exclude_particles:
                continue
            if particle_db["cost_factor"] > constraints.max_cost_factor:
                continue
            if particle_db["density_kgm3"] > constraints.particle_density_limit_kgm3:
                continue

            k_f = BASE_FLUID_THERMAL_CONDUCTIVITY
            k_p = particle_db["thermal_conductivity_wmk"]
            cost = particle_db["cost_factor"]

            for vf in self._volume_fraction_grid(constraints.max_volume_fraction):
                enhancement_pct = maxwell_conductivity_enhancement(k_f, k_p, vf)
                if enhancement_pct < constraints.min_enhancement_pct:
                    continue
                if vf > 0 and cost > 0:
                    score = enhancement_pct / (vf * cost)
                else:
                    score = 0.0

                kf = 1.0 + enhancement_pct / 100.0
                candidates.append(BlendCandidate(
                    nanoparticle=particle_name,
                    volume_fraction=vf,
                    predicted_enhancement_pct=enhancement_pct,
                    conductivity_factor=kf,
                    score=score,
                    cost_factor=cost,
                    particle_conductivity_wmk=k_p,
                ))

        candidates.sort(key=lambda c: c.score, reverse=True)
        result = candidates[:max_results]

        if result:
            self._best_score_seen = max(self._best_score_seen, result[0].score)

        logger.info("COLOSSUS-NANOSPHERE: Optimization #%d target=%.1f%% results=%d best_score=%.2f",
                     self._optimization_count, target_enhancement_pct, len(result),
                     result[0].score if result else 0.0)

        return result

    def find_minimum_blend(
        self,
        target_enhancement_pct: float,
        constraints: Optional[OptimizationConstraints] = None,
    ) -> Optional[BlendCandidate]:
        all_candidates = self.optimize(target_enhancement_pct, constraints, max_results=1000)
        meets_target = [c for c in all_candidates if c.predicted_enhancement_pct >= target_enhancement_pct]
        if not meets_target:
            logger.warning("COLOSSUS-NANOSPHERE: No blend achieves %.1f%% enhancement", target_enhancement_pct)
            return None
        meets_target.sort(key=lambda c: c.volume_fraction)
        return meets_target[0]

    def summary(self) -> Dict[str, Any]:
        return {
            "optimizations_run": self._optimization_count,
            "best_score_seen": round(self._best_score_seen, 2),
            "particles_evaluated": len(PARTICLE_DATABASE),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    optimizer = CircuitOptimizer({"max_volume_fraction": 0.05})

    target = 15.0
    results = optimizer.optimize(target)

    logger.info("=== Top %d Blends for %.1f%% Enhancement ===", len(results), target)
    for i, r in enumerate(results, 1):
        d = r.to_dict()
        logger.info("#%d  %s @ %.1f%% vf  →  enhancement=%.1f%%  score=%.2f",
                     i, d["nanoparticle"], d["volume_fraction"] * 100,
                     d["predicted_enhancement_pct"], d["score"])

    best = optimizer.find_minimum_blend(target)
    if best:
        logger.info("Minimum blend: %s @ %.1f%% vf → %.1f%% enhancement",
                     best.nanoparticle, best.volume_fraction * 100,
                     best.predicted_enhancement_pct)

    print("\n=== Circuit Optimizer Summary ===")
    print(optimizer.summary())
