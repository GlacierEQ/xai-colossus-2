#!/usr/bin/env python3
"""
Colossus 2 — Colloidal Stability Evaluator
============================================
Evaluates nanofluid colloidal stability based on zeta potential, Stokes
settling, volume fraction agglomeration, and age-dependent drift.

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("COLOSSUS-NANOSPHERE")

GRAVITY = 9.81  # m/s²
BOLTZMANN_KB = 1.380649e-23  # J/K
AVOGADRO = 6.022e23
WATER_VISCOSITY_50C = 0.000547  # Pa·s at 50°C
WATER_DENSITY_50C = 988.0  # kg/m³ at 50°C
AMBIENT_TEMP_K = 323.15  # 50°C in Kelvin


@dataclass
class StabilitySpec:
    zeta_potential_mv: float = -30.0
    particle_size_nm: float = 30.0
    volume_fraction: float = 0.03
    temperature_k: float = AMBIENT_TEMP_K
    base_fluid_viscosity_pas: float = WATER_VISCOSITY_50C
    base_fluid_density_kgm3: float = WATER_DENSITY_50C
    particle_density_kgm3: float = 3970.0
    age_days: float = 0.0
    nanoparticle: str = "Al2O3"
    stirring_active: bool = False
    ph_value: float = 7.0


@dataclass
class StabilityResult:
    score: int
    status: str
    risk_factors: List[str]
    zeta_assessment: str
    settling_velocity_ms: float
    agglomeration_risk: str
    age_drift_penalty: float
    replacement_recommended: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "status": self.status,
            "risk_factors": self.risk_factors,
            "zeta_assessment": self.zeta_assessment,
            "settling_velocity_ms": self.settling_velocity_ms,
            "agglomeration_risk": self.agglomeration_risk,
            "age_drift_penalty": round(self.age_drift_penalty, 3),
            "replacement_recommended": self.replacement_recommended,
        }


class StabilityEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.stability_threshold = self.config.get("stability_threshold", 60)
        self._evaluation_count = 0
        self._unstable_count = 0
        logger.info("COLOSSUS-NANOSPHERE: StabilityEngine initialized threshold=%d",
                     self.stability_threshold)

    def _score_zeta_potential(self, zeta_mv: float) -> tuple:
        abs_zeta = abs(zeta_mv)
        if abs_zeta > 35:
            return 40, "stable", "Zeta potential excellent (>35 mV)"
        if abs_zeta > 25:
            return 30, "monitor", "Zeta potential moderate (25-35 mV) — monitor"
        if abs_zeta > 15:
            return 15, "degrading", "Zeta potential concerning (15-25 mV)"
        return 0, "unstable", "Zeta potential critical (<15 mV)"

    def _compute_settling_velocity(self, spec: StabilitySpec) -> float:
        r_m = (spec.particle_size_nm * 1e-9) / 2.0
        rho_p = spec.particle_density_kgm3
        rho_f = spec.base_fluid_density_kgm3
        mu = spec.base_fluid_viscosity_pas
        delta_rho = rho_p - rho_f
        if delta_rho <= 0 or r_m <= 0:
            return 0.0
        v_settle = (2.0 * delta_rho * GRAVITY * r_m ** 2) / (9.0 * mu)
        return v_settle

    def _assess_settling(self, velocity_ms: float) -> tuple:
        if velocity_ms < 1e-8:
            return 30, "negligible", []
        if velocity_ms < 5e-7:
            return 20, "low", ["Mild sedimentation — stirring mitigates"]
        if velocity_ms < 5e-6:
            return 10, "moderate", ["Significant settling rate — agitation required"]
        return 0, "high", ["CRITICAL: Rapid settling — fluid instability imminent"]

    def _assess_agglomeration(self, spec: StabilitySpec) -> tuple:
        phi = spec.volume_fraction
        risk_factors = []
        if phi > 0.10:
            return 0, "severe", ["Volume fraction >10% — severe agglomeration"]
        if phi > 0.06:
            return 5, "high", ["Volume fraction >6% — high agglomeration risk"]
        if phi > 0.04:
            return 10, "moderate", ["Volume fraction >4% — moderate agglomeration"]
        if phi > 0.02:
            return 15, "low", []
        return 20, "negligible", []

    def _age_drift_penalty(self, spec: StabilitySpec) -> float:
        penalty_per_day = 0.0005
        return min(0.20, spec.age_days * penalty_per_day)

    def _compute_score(self, zeta_score: int, settle_score: int, agglomeration_score: int,
                       age_penalty: float) -> int:
        raw = zeta_score + settle_score + agglomeration_score
        adjusted = raw * (1.0 - age_penalty)
        return max(0, min(100, int(round(adjusted))))

    def _status_from_score(self, score: int) -> str:
        if score >= 80:
            return "stable"
        if score >= 60:
            return "monitor"
        if score >= 40:
            return "degrading"
        return "unstable"

    def evaluate_stability(self, spec: StabilitySpec) -> StabilityResult:
        self._evaluation_count += 1
        all_risk_factors = []

        zeta_score, zeta_status, zeta_msg = self._score_zeta_potential(spec.zeta_potential_mv)
        all_risk_factors.append(zeta_msg)

        settling_v = self._compute_settling_velocity(spec)
        settle_score, settle_label, settle_risks = self._assess_settling(settling_v)
        all_risk_factors.extend(settle_risks)

        agglom_score, agglom_label, agglom_risks = self._assess_agglomeration(spec)
        all_risk_factors.extend(agglom_risks)

        age_penalty = self._age_drift_penalty(spec)
        if age_penalty > 0.05:
            all_risk_factors.append(f"Age drift penalty: {age_penalty*100:.1f}%")

        score = self._compute_score(zeta_score, settle_score, agglom_score, age_penalty)
        status = self._status_from_score(score)

        if status in ("degrading", "unstable"):
            self._unstable_count += 1
            all_risk_factors.append("REPLACEMENT_RECOMMENDED")

        replacement = status in ("degrading", "unstable")

        logger.info("COLOSSUS-NANOSPHERE: Stability eval #%d score=%d status=%s risks=%d",
                     self._evaluation_count, score, status, len(all_risk_factors))

        return StabilityResult(
            score=score,
            status=status,
            risk_factors=all_risk_factors,
            zeta_assessment=zeta_status,
            settling_velocity_ms=settling_v,
            agglomeration_risk=agglom_label,
            age_drift_penalty=age_penalty,
            replacement_recommended=replacement,
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "evaluations_total": self._evaluation_count,
            "unstable_count": self._unstable_count,
            "stability_threshold": self.stability_threshold,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    engine = StabilityEngine({"stability_threshold": 60})

    specs = [
        StabilitySpec(zeta_potential_mv=-40.0, particle_size_nm=30.0, volume_fraction=0.03,
                      nanoparticle="Al2O3"),
        StabilitySpec(zeta_potential_mv=-20.0, particle_size_nm=80.0, volume_fraction=0.07,
                      nanoparticle="CuO", age_days=150),
        StabilitySpec(zeta_potential_mv=-10.0, particle_size_nm=120.0, volume_fraction=0.12,
                      nanoparticle="graphene", age_days=300),
    ]

    for spec in specs:
        result = engine.evaluate_stability(spec)
        d = result.to_dict()
        logger.info("Particle=%s | Score=%d | Status=%s | Replacement=%s",
                     spec.nanoparticle, d["score"], d["status"], d["replacement_recommended"])
        for rf in d["risk_factors"]:
            logger.warning("  Risk: %s", rf)
        logger.info("  Settling: %.2e m/s | Agglom: %s | Age penalty: %.1f%%",
                     d["settling_velocity_ms"], d["agglomeration_risk"],
                     d["age_drift_penalty"] * 100)

    print("\n=== Stability Engine Summary ===")
    print(engine.summary())
