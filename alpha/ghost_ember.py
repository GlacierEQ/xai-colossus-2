# Alpha (What) — Pure Physics | Omega (How) — Controllers | The Answer is 42.
#!/usr/bin/env python3
"""
Ghost Ember — Perimeter Anomaly Detection for Colossus 2
=========================================================
EMA-based baseline learning per sensor, configurable sigma thresholds,
and drift detection for slow baseline shifts.

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("COLOSSUS-SECURITY")


@dataclass
class SensorBaseline:
    sensor_id: str
    ema_value: float = 0.0
    ema_variance: float = 1.0
    initialized: bool = False
    sample_count: int = 0
    ema_alpha: float = 0.2
    baseline_snapshot: float = 0.0
    drift_window: List[float] = field(default_factory=list)
    drift_detected: bool = False


@dataclass
class AnomalyResult:
    sensor_id: str
    value: float
    anomaly: bool
    severity: str
    deviation: float
    baseline_ema: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly": self.anomaly,
            "severity": self.severity,
            "deviation": round(self.deviation, 4),
            "baseline_ema": round(self.baseline_ema, 4),
            "sensor_id": self.sensor_id,
            "value": round(self.value, 4),
            "timestamp": self.timestamp,
        }


@dataclass
class GhostEmberDetector:
    alert_sigma: float = 3.0
    critical_sigma: float = 5.0
    drift_threshold_pct: float = 10.0
    drift_window_size: int = 100
    _baselines: Dict[str, SensorBaseline] = field(default_factory=dict)
    _anomaly_count: int = 0
    _total_ingests: int = 0
    _drift_alerts: List[Dict[str, Any]] = field(default_factory=list)
    _alert_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        logger.info("Ghost Ember Detector INITIALIZED | alert_sigma=%.1f | critical_sigma=%.1f | drift_threshold=%.1f%%",
                     self.alert_sigma, self.critical_sigma, self.drift_threshold_pct)

    def _get_or_create_baseline(self, sensor_id: str) -> SensorBaseline:
        if sensor_id not in self._baselines:
            self._baselines[sensor_id] = SensorBaseline(sensor_id=sensor_id)
        return self._baselines[sensor_id]

    def _update_ema(self, baseline: SensorBaseline, value: float) -> None:
        if not baseline.initialized:
            baseline.ema_value = value
            baseline.ema_variance = 1.0
            baseline.initialized = True
            baseline.sample_count = 1
            return

        alpha = baseline.ema_alpha
        delta = value - baseline.ema_value
        baseline.ema_value = alpha * value + (1 - alpha) * baseline.ema_value
        baseline.ema_variance = alpha * delta * delta + (1 - alpha) * baseline.ema_variance
        baseline.sample_count += 1

    def _detect_drift(self, baseline: SensorBaseline) -> bool:
        if not baseline.initialized:
            return False

        baseline.drift_window.append(baseline.ema_value)
        if len(baseline.drift_window) > self.drift_window_size:
            baseline.drift_window = baseline.drift_window[-self.drift_window_size:]

        if len(baseline.drift_window) < 20:
            return False

        snapshot = baseline.drift_window[0]
        current = baseline.drift_window[-1]
        if abs(snapshot) < 1e-10:
            return False

        drift_pct = abs(current - snapshot) / abs(snapshot) * 100.0
        if drift_pct > self.drift_threshold_pct and not baseline.drift_detected:
            baseline.drift_detected = True
            drift_alert = {
                "sensor_id": baseline.sensor_id,
                "drift_pct": round(drift_pct, 2),
                "snapshot_value": round(snapshot, 4),
                "current_value": round(current, 4),
                "window_size": len(baseline.drift_window),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._drift_alerts.append(drift_alert)
            logger.warning("DRIFT_DETECTED: %s shifted %.1f%% over %d samples",
                           baseline.sensor_id, drift_pct, len(baseline.drift_window))
            return True

        if drift_pct < self.drift_threshold_pct * 0.5:
            baseline.drift_detected = False

        return baseline.drift_detected

    def _classify_severity(self, deviation: float) -> Tuple[bool, str]:
        if deviation >= self.critical_sigma:
            return True, "critical"
        if deviation >= self.alert_sigma:
            return True, "alert"
        return False, "normal"

    def ingest(self, sensor_id: str, value: float) -> Dict[str, Any]:
        self._total_ingests += 1
        baseline = self._get_or_create_baseline(sensor_id)

        deviation = 0.0
        if baseline.initialized and baseline.ema_variance > 0:
            std_dev = math.sqrt(baseline.ema_variance)
            deviation = abs(value - baseline.ema_value) / max(std_dev, 1e-10)
        elif not baseline.initialized:
            deviation = 0.0

        is_anomaly, severity = self._classify_severity(deviation)

        self._update_ema(baseline, value)
        self._detect_drift(baseline)

        result = AnomalyResult(
            sensor_id=sensor_id,
            value=value,
            anomaly=is_anomaly,
            severity=severity,
            deviation=deviation,
            baseline_ema=baseline.ema_value,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if is_anomaly:
            self._anomaly_count += 1
            self._alert_log.append({
                "sensor_id": sensor_id,
                "severity": severity,
                "deviation": round(deviation, 4),
                "value": round(value, 4),
                "baseline": round(baseline.ema_value, 4),
                "timestamp": result.timestamp,
            })
            logger.warning("ANOMALY [%s]: %s value=%.4f baseline=%.4f deviation=%.2fσ",
                           severity.upper(), sensor_id, value, baseline.ema_value, deviation)

        return result.to_dict()

    def summary(self) -> Dict[str, Any]:
        baselines = list(self._baselines.values())
        return {
            "sensors_tracked": len(baselines),
            "total_ingests": self._total_ingests,
            "anomalies_detected": self._anomaly_count,
            "drift_alerts": len(self._drift_alerts),
            "initialized_sensors": sum(1 for b in baselines if b.initialized),
            "drifted_sensors": sum(1 for b in baselines if b.drift_detected),
            "alert_log_size": len(self._alert_log),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    detector = GhostEmberDetector(alert_sigma=3.0, critical_sigma=5.0)

    sensor_ids = ["PERIM-RACK-001", "PERIM-RACK-002", "PERIM-RACK-003",
                   "DOOR-SENSOR-01", "CAM-MOTION-04", "NET-FLOW-INT"]

    import random
    random.seed(42)

    print("=== Ghost Ember Detector — Ingestion Demo ===\n")
    for tick in range(200):
        for sid in sensor_ids:
            normal = 100.0 + math.sin(tick * 0.05) * 10.0
            value = normal + random.gauss(0, 3)
            if tick > 150 and sid == "PERIM-RACK-001":
                value += 50.0

            result = detector.ingest(sid, value)
            if result["anomaly"]:
                logger.info("TICK %d | %s anomaly: value=%.2f dev=%.2fσ sev=%s",
                            tick, sid, result["value"], result["deviation"], result["severity"])

        if tick % 50 == 0:
            summary = detector.summary()
            print(f"\n--- Tick {tick} Summary ---")
            for k, v in summary.items():
                print(f"  {k}: {v}")

    print("\n=== Final Summary ===")
    print(detector.summary())
