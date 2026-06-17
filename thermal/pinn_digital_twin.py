#!/usr/bin/env python3
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("COLOSSUS-THERMAL")

WATER_CPKJ_KG = 4.186
NOVEC_CPKJ_KG = 1.56


def _xavier_uniform(fan_in: int, fan_out: int) -> list:
    limit = math.sqrt(6.0 / (fan_in + fan_out))
    return [[random.uniform(-limit, limit) for _ in range(fan_out)] for _ in range(fan_in)]


def _init_perceptron():
    w_ih = _xavier_uniform(3, 8)
    b_h = [0.0] * 8
    w_ho = _xavier_uniform(8, 1)
    b_o = [0.0]
    return w_ih, b_h, w_ho, b_o


def _perceptron_forward(x, w_ih, b_h, w_ho, b_o):
    hidden = [0.0] * 8
    for j in range(8):
        s = b_h[j]
        for i in range(3):
            s += x[i] * w_ih[i][j]
        hidden[j] = math.tanh(s)
    out = b_o[0]
    for j in range(8):
        out += hidden[j] * w_ho[j][0]
    return out


@dataclass
class ValidationRecord:
    zone_id: str
    residual: float
    confidence: float
    flagged: bool
    timestamp: str
    physics_q: float
    neural_q: float
    drift_delta: float


@dataclass
class PINNDigitalTwin:
    manifest: Dict[str, Any]
    critical_temp_c: float = 0.0
    hot_temp_c: float = 0.0
    warm_temp_c: float = 0.0
    residual_threshold: float = 0.05
    _drift_history: Dict[str, List[float]] = field(default_factory=dict)
    _validation_log: List[ValidationRecord] = field(default_factory=list)
    _calibration_offsets: Dict[str, float] = field(default_factory=dict)
    _perceptron: Optional[tuple] = field(default=None, repr=False)

    def __post_init__(self):
        self.critical_temp_c = self.manifest.get("critical_temp_c", 85.0)
        self.hot_temp_c = self.manifest.get("hot_temp_c", 78.0)
        self.warm_temp_c = self.manifest.get("warm_temp_c", 70.0)
        self._perceptron = _init_perceptron()

    def _compute_physics_heat(self, zone: Dict[str, Any]) -> float:
        power_kw = zone.get("power_draw_kw", 0.0)
        flow_lpm = zone.get("cooling_flow_lpm", 0.0)
        temp_c = zone.get("temp_celsius", 65.0)

        if flow_lpm <= 0:
            return power_kw * 1000.0

        flow_kg_s = flow_lpm / 60.0
        delta_t = max(temp_c - self.warm_temp_c, 0.0)
        q_cooling = flow_kg_s * NOVEC_CPKJ_KG * delta_t * 1000.0
        q_total = power_kw * 1000.0 + q_cooling
        return q_total

    def _neural_prediction(self, zone: Dict[str, Any], physics_q: float) -> float:
        zone_id = zone.get("zone_id", "unknown")
        offset = self._calibration_offsets.get(zone_id, 0.0)
        w_ih, b_h, w_ho, b_o = self._perceptron

        power_kw = zone.get("power_draw_kw", 0.0)
        flow_lpm = zone.get("cooling_flow_lpm", 0.0)
        temp_c = zone.get("temp_celsius", 65.0)
        x = [power_kw / 100000.0, flow_lpm / 1000.0, temp_c / 100.0]

        raw_correction = _perceptron_forward(x, w_ih, b_h, w_ho, b_o)
        correction = 1.0 + raw_correction * 0.1 + offset
        neural_q = physics_q * correction

        self._calibration_offsets[zone_id] = offset * 0.995
        return neural_q

    def _update_drift(self, zone_id: str, residual: float) -> None:
        if zone_id not in self._drift_history:
            self._drift_history[zone_id] = []
        self._drift_history[zone_id].append(residual)
        if len(self._drift_history[zone_id]) > 500:
            self._drift_history[zone_id] = self._drift_history[zone_id][-500:]

    def _compute_confidence(self, zone_id: str) -> float:
        history = self._drift_history.get(zone_id, [])
        if len(history) < 10:
            return 0.5

        recent = history[-50:]
        avg_res = sum(recent) / len(recent)
        try:
            variance = sum((r - avg_res) ** 2 for r in recent) / len(recent)
            std_res = math.sqrt(min(variance, 1e300))
        except (OverflowError, ValueError, ZeroDivisionError):
            std_res = 1e150

        base_conf = max(0.0, 1.0 - avg_res * 5.0)
        stability_bonus = max(0.0, 0.2 - std_res * 2.0)
        return min(base_conf + stability_bonus, 1.0)

    def validate(self, zone: Any) -> Dict[str, Any]:
        zone_id = zone.get("zone_id") if isinstance(zone, dict) else getattr(zone, "zone_id", "unknown")
        zone_dict = zone if isinstance(zone, dict) else {
            "zone_id": zone.zone_id,
            "temp_celsius": zone.temp_celsius,
            "power_draw_kw": zone.power_draw_kw,
            "cooling_flow_lpm": zone.cooling_flow_lpm,
        }

        physics_q = self._compute_physics_heat(zone_dict)
        neural_q = self._neural_prediction(zone_dict, physics_q)

        denom = max(abs(physics_q), 1e-6)
        residual = abs(neural_q - physics_q) / denom

        flagged = residual > self.residual_threshold
        confidence = self._compute_confidence(zone_id)

        self._update_drift(zone_id, residual)

        record = ValidationRecord(
            zone_id=zone_id,
            residual=residual,
            confidence=confidence,
            flagged=flagged,
            timestamp=datetime.now(timezone.utc).isoformat(),
            physics_q=physics_q,
            neural_q=neural_q,
            drift_delta=residual,
        )
        self._validation_log.append(record)

        if flagged:
            logger.warning("PINN_VIOLATION zone=%s residual=%.4f (threshold=%.4f) confidence=%.2f",
                          zone_id, residual, self.residual_threshold, confidence)
            self._calibration_offsets[zone_id] = (physics_q - neural_q) / denom * 0.1

        return {"flagged": flagged, "residual": residual, "confidence": confidence}

    def summary(self) -> Dict[str, Any]:
        recent = self._validation_log[-100:] if self._validation_log else []
        flagged_count = sum(1 for r in recent if r.flagged)
        avg_residual = sum(r.residual for r in recent) / len(recent) if recent else 0.0
        return {
            "total_validations": len(self._validation_log),
            "flagged_count": flagged_count,
            "avg_residual": avg_residual,
            "zones_tracked": list(self._drift_history.keys()),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    twin = PINNDigitalTwin(manifest={
        "critical_temp_c": 85.0,
        "hot_temp_c": 78.0,
        "warm_temp_c": 70.0,
    })

    test_zones = [
        {"zone_id": "A", "temp_celsius": 68.0, "power_draw_kw": 50000.0, "cooling_flow_lpm": 500.0},
        {"zone_id": "B", "temp_celsius": 74.0, "power_draw_kw": 60000.0, "cooling_flow_lpm": 450.0},
        {"zone_id": "C", "temp_celsius": 82.0, "power_draw_kw": 55000.0, "cooling_flow_lpm": 350.0},
    ]

    for tick in range(20):
        for zone in test_zones:
            zone["temp_celsius"] += random.uniform(-0.5, 0.8)
            result = twin.validate(zone)
            status = "FLAGGED" if result["flagged"] else "OK"
            if tick % 5 == 0:
                logger.info("TICK %d | zone=%s | residual=%.4f | confidence=%.2f | %s",
                           tick, zone["zone_id"], result["residual"], result["confidence"], status)

    print("\n=== PINN Digital Twin Summary ===")
    print(twin.summary())
