#!/usr/bin/env python3
"""
Colossus 2 PUE Optimizer
=========================
Real-time PUE tracking and cooling optimization.
PUE = Total Facility Power / IT Equipment Power

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("COLOSSUS-ENERGY")


@dataclass
class PUEConfig:
    target_pue: float = 1.03
    warning_threshold: float = 1.10
    critical_threshold: float = 1.15
    emergency_threshold: float = 1.20
    history_max: int = 1440
    history_window_s: float = 60.0
    rolling_avg_window: int = 10
    cooling_reduction_step: float = 0.05
    recommendation_cooldown_s: float = 30.0


@dataclass
class PUESample:
    timestamp: float
    total_power_mw: float
    it_power_mw: float
    pue: float
    cooling_power_mw: float


@dataclass
class CoolingAdjustment:
    type: str
    magnitude: float
    timestamp: str
    reason: str


class PUEOptimizer:
    """Real-time PUE tracking and cooling optimization."""

    def __init__(self, config: Optional[PUEConfig] = None):
        self.config = config or PUEConfig()
        self.history: List[PUESample] = []
        self._current_pue: float = 1.0
        self._peak_pue: float = 1.0
        self._sample_count: int = 0
        self._last_recommendation_time: float = 0.0
        self._adjustments: List[CoolingAdjustment] = []
        self._max_adjustments = 500
        logger.info("PUEOptimizer INITIALIZED | target=%.2f warning=%.2f critical=%.2f emergency=%.2f",
                     self.config.target_pue, self.config.warning_threshold,
                     self.config.critical_threshold, self.config.emergency_threshold)

    def _classify_pue(self, pue: float) -> str:
        if pue <= self.config.target_pue:
            return "optimal"
        if pue <= self.config.warning_threshold:
            return "nominal"
        if pue <= self.config.critical_threshold:
            return "warning"
        if pue <= self.config.emergency_threshold:
            return "critical"
        return "emergency"

    def _compute_rolling_average(self) -> float:
        if not self.history:
            return 1.0
        window = min(self.config.rolling_avg_window, len(self.history))
        recent = self.history[-window:]
        return sum(s.pue for s in recent) / len(recent)

    def _compute_trend(self) -> str:
        if len(self.history) < 20:
            return "INSUFFICIENT_DATA"
        recent = self.history[-10:]
        older = self.history[-20:-10]
        avg_recent = sum(s.pue for s in recent) / len(recent)
        avg_older = sum(s.pue for s in older) / len(older)
        delta = avg_recent - avg_older
        if delta > 0.01:
            return "DEGRADING"
        if delta < -0.01:
            return "IMPROVING"
        return "STABLE"

    def _recommend_cooling(self, pue: float, trend: str) -> str:
        now = time.time()
        if now - self._last_recommendation_time < self.config.recommendation_cooldown_s:
            return "COOLDOWN_ACTIVE"
        classification = self._classify_pue(pue)
        if classification == "optimal":
            return "PUE_OPTIMAL: no adjustment needed"
        if classification == "nominal":
            return "PUE_NOMINAL: within target range"
        if classification == "warning":
            self._last_recommendation_time = now
            return "WARNING: increase coolant flow 5% or reduce GPU DVFS 3%"
        if classification == "critical":
            self._last_recommendation_time = now
            self._adjustments.append(CoolingAdjustment(
                type="INCREASE_COOLANT", magnitude=0.10,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reason=f"CRITICAL PUE={pue:.3f}",
            ))
            return "CRITICAL: increase coolant flow 10% + reduce GPU power 5%"
        self._last_recommendation_time = now
        self._adjustments.append(CoolingAdjustment(
            type="EMERGENCY_COOLING", magnitude=0.20,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=f"EMERGENCY PUE={pue:.3f}",
        ))
        return "EMERGENCY: max cooling + DVFS throttle 15% + shed non-critical loads"

    def get_pue(self, total_power_mw: float = 0.0, it_power_mw: float = 0.0) -> Dict[str, Any]:
        if it_power_mw > 0:
            self.sample(total_power_mw, it_power_mw)
        current = self._compute_rolling_average() if self.history else self._current_pue
        trend = self._compute_trend()
        recommendation = self._recommend_cooling(current, trend)
        return {
            "pue": round(current, 4),
            "target": self.config.target_pue,
            "trend": trend,
            "recommendation": recommendation,
            "classification": self._classify_pue(current),
        }

    def sample(self, total_power_mw: float, it_power_mw: float) -> None:
        if it_power_mw <= 0:
            logger.warning("PUE_SAMPLE_IGNORED: IT power %.1fMW is non-positive", it_power_mw)
            return
        pue = total_power_mw / it_power_mw
        cooling = total_power_mw - it_power_mw
        s = PUESample(
            timestamp=time.time(),
            total_power_mw=total_power_mw,
            it_power_mw=it_power_mw,
            pue=pue,
            cooling_power_mw=cooling,
        )
        self.history.append(s)
        if len(self.history) > self.config.history_max:
            self.history = self.history[-self.config.history_max // 2:]
        self._current_pue = pue
        self._peak_pue = max(self._peak_pue, pue)
        self._sample_count += 1
        if self._classify_pue(pue) in ("critical", "emergency"):
            logger.warning("PUE_ALERT: %.3f (%s) | IT=%.1fMW cooling=%.1fMW",
                           pue, self._classify_pue(pue), it_power_mw, cooling)

    def tick(self, tick_num: int) -> Dict[str, Any]:
        anomalies = []
        actions = []
        if self.history:
            pue = self._compute_rolling_average()
            classification = self._classify_pue(pue)
            if classification == "critical":
                anomalies.append(f"PUE_CRITICAL: {pue:.3f}")
                actions.append(self._recommend_cooling(pue, self._compute_trend()))
            elif classification == "emergency":
                anomalies.append(f"PUE_EMERGENCY: {pue:.3f}")
                actions.append(self._recommend_cooling(pue, self._compute_trend()))
        return {"anomalies": anomalies, "actions": actions}

    def summary(self) -> Dict[str, Any]:
        current = self._compute_rolling_average() if self.history else self._current_pue
        return {
            "current_pue": round(current, 4),
            "peak_pue": round(self._peak_pue, 4),
            "target_pue": self.config.target_pue,
            "classification": self._classify_pue(current),
            "trend": self._compute_trend(),
            "samples": self._sample_count,
            "adjustments": len(self._adjustments),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    optimizer = PUEOptimizer()
    import random
    for i in range(20):
        it = 1200 + random.uniform(-50, 50)
        total = it * (1.03 + random.uniform(0, 0.15))
        optimizer.sample(total, it)
    result = optimizer.get_pue()
    print("PUE:", result)
    print("Summary:", optimizer.summary())
