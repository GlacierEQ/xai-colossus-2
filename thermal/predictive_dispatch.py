#!/usr/bin/env python3
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("COLOSSUS-THERMAL")


@dataclass
class ZoneForecast:
    zone_id: str
    current_temp: float
    predicted_temp_12: float
    surge_confidence: float
    ema_temp: float
    trend_slope: float
    dispatch_recommended: bool


@dataclass
class PredictiveDispatch:
    manifest: Dict[str, Any]
    ema_alpha: float = 0.3
    surge_horizon: int = 12
    surge_confidence_threshold: float = 0.8
    critical_temp_c: float = 85.0
    hot_temp_c: float = 78.0
    _ema_temps: Dict[str, float] = field(default_factory=dict)
    _temp_history: Dict[str, List[float]] = field(default_factory=dict)
    _dispatch_log: List[Dict[str, Any]] = field(default_factory=list)
    _prediction_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.critical_temp_c = self.manifest.get("critical_temp_c", 85.0)
        self.hot_temp_c = self.manifest.get("hot_temp_c", 78.0)

    def _update_ema(self, zone_id: str, temp: float) -> float:
        if zone_id not in self._ema_temps:
            self._ema_temps[zone_id] = temp
        else:
            self._ema_temps[zone_id] = self.ema_alpha * temp + (1.0 - self.ema_alpha) * self._ema_temps[zone_id]
        return self._ema_temps[zone_id]

    def _compute_trend(self, zone_id: str) -> float:
        history = self._temp_history.get(zone_id, [])
        if len(history) < 5:
            return 0.0

        recent = history[-20:]
        n = len(recent)
        sum_x = sum(range(n))
        sum_y = sum(recent)
        sum_xy = sum(i * recent[i] for i in range(n))
        sum_x2 = sum(i * i for i in range(n))

        denom = n * sum_x2 - sum_x * sum_x
        if abs(denom) < 1e-10:
            return 0.0
        return (n * sum_xy - sum_x * sum_y) / denom

    def _predict_future_temp(self, zone_id: str, current_temp: float) -> float:
        ema = self._ema_temps.get(zone_id, current_temp)
        trend = self._compute_trend(zone_id)
        predicted = current_temp + trend * self.surge_horizon

        ema_pull = (ema - current_temp) * 0.1
        predicted += ema_pull

        return predicted

    def _compute_surge_confidence(self, zone_id: str, predicted_temp: float) -> float:
        if predicted_temp <= self.hot_temp_c:
            return 0.0

        history = self._temp_history.get(zone_id, [])
        if len(history) < 10:
            base_conf = min((predicted_temp - self.hot_temp_c) / (self.critical_temp_c - self.hot_temp_c), 1.0)
            return base_conf * 0.6

        recent = history[-30:]
        mean_temp = sum(recent) / len(recent)
        std_temp = math.sqrt(sum((t - mean_temp) ** 2 for t in recent) / len(recent))

        temp_excess = max(predicted_temp - self.hot_temp_c, 0.0)
        temp_range = max(self.critical_temp_c - self.hot_temp_c, 1.0)
        base_conf = min(temp_excess / temp_range, 1.0)

        trend = self._compute_trend(zone_id)
        trend_factor = min(abs(trend) * 10.0, 0.3)

        stability_penalty = min(std_temp / 5.0, 0.2)

        confidence = base_conf + trend_factor - stability_penalty
        return max(0.0, min(confidence, 1.0))

    def forecast(self, zones: Dict[str, Any]) -> Dict[str, Any]:
        predictions = {}
        dispatch_recommendations = []

        for zone_id, zone in zones.items():
            if isinstance(zone, dict):
                temp = zone.get("temp_celsius", 65.0)
                power_kw = zone.get("power_draw_kw", 0.0)
            else:
                temp = zone.temp_celsius
                power_kw = zone.power_draw_kw

            if zone_id not in self._temp_history:
                self._temp_history[zone_id] = []
            self._temp_history[zone_id].append(temp)
            if len(self._temp_history[zone_id]) > 500:
                self._temp_history[zone_id] = self._temp_history[zone_id][-500:]

            ema = self._update_ema(zone_id, temp)
            trend = self._compute_trend(zone_id)
            predicted = self._predict_future_temp(zone_id, temp)
            confidence = self._compute_surge_confidence(zone_id, predicted)
            dispatch = confidence > self.surge_confidence_threshold

            forecast = ZoneForecast(
                zone_id=zone_id,
                current_temp=temp,
                predicted_temp_12=round(predicted, 2),
                surge_confidence=round(confidence, 4),
                ema_temp=round(ema, 2),
                trend_slope=round(trend, 4),
                dispatch_recommended=dispatch,
            )
            predictions[zone_id] = forecast

            if dispatch:
                dispatch_recommendations.append({
                    "zone_id": zone_id,
                    "action": "PRE_COOL",
                    "reason": f"surge confidence {confidence:.2f} > threshold {self.surge_confidence_threshold}",
                    "predicted_temp": predicted,
                    "current_temp": temp,
                    "tick": len(self._temp_history.get(zone_id, [])),
                    "ts": datetime.now(timezone.utc).isoformat(),
                })

        self._dispatch_log.extend(dispatch_recommendations)
        self._prediction_log.append({
            "tick": len(list(self._temp_history.values())[0]) if self._temp_history else 0,
            "predictions": {zid: {"predicted": f.predicted_temp_12, "confidence": f.surge_confidence}
                           for zid, f in predictions.items()},
            "dispatches": len(dispatch_recommendations),
        })

        if dispatch_recommendations:
            for rec in dispatch_recommendations:
                logger.info("PRE_COOL_DISPATCH zone=%s confidence=%.2f predicted=%.1fC",
                           rec["zone_id"], rec["confidence"] if "confidence" in rec else 0,
                           rec["predicted_temp"])

        overall_confidence = max((f.surge_confidence for f in predictions.values()), default=0.0)
        return {
            "predictions": {zid: {"predicted_temp": f.predicted_temp_12, "confidence": f.surge_confidence,
                                   "ema": f.ema_temp, "trend": f.trend_slope}
                           for zid, f in predictions.items()},
            "confidence": overall_confidence,
            "dispatch_recommendation": dispatch_recommendations,
        }

    def summary(self) -> Dict[str, Any]:
        recent_dispatches = self._dispatch_log[-50:] if self._dispatch_log else []
        recent_preds = self._prediction_log[-50:] if self._prediction_log else []
        avg_confidence = 0.0
        if recent_preds:
            all_confs = []
            for p in recent_preds:
                all_confs.extend(pred["confidence"] for pred in p["predictions"].values())
            avg_confidence = sum(all_confs) / len(all_confs) if all_confs else 0.0

        return {
            "zones_tracked": list(self._ema_temps.keys()),
            "total_dispatches": len(self._dispatch_log),
            "recent_dispatches": len(recent_dispatches),
            "avg_confidence": round(avg_confidence, 4),
            "predictions_made": len(self._prediction_log),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    dispatch = PredictiveDispatch(manifest={
        "critical_temp_c": 85.0,
        "hot_temp_c": 78.0,
    })

    import random

    zones = {
        "A": {"zone_id": "A", "temp_celsius": 65.0, "power_draw_kw": 50000.0, "cooling_flow_lpm": 500.0},
        "B": {"zone_id": "B", "temp_celsius": 72.0, "power_draw_kw": 60000.0, "cooling_flow_lpm": 450.0},
        "C": {"zone_id": "C", "temp_celsius": 68.0, "power_draw_kw": 55000.0, "cooling_flow_lpm": 350.0},
    }

    for tick in range(50):
        zones["A"]["temp_celsius"] += random.uniform(-0.3, 0.5)
        zones["B"]["temp_celsius"] += random.uniform(0.1, 0.8)
        zones["C"]["temp_celsius"] += random.uniform(-0.2, 0.3)

        for zid in zones:
            zones[zid]["temp_celsius"] = max(40.0, min(zones[zid]["temp_celsius"], 95.0))

        result = dispatch.forecast(zones)

        if tick % 5 == 0:
            logger.info("TICK %d | overall_confidence=%.3f | dispatches=%d",
                       tick, result["confidence"], len(result["dispatch_recommendation"]))
            for zid, pred in result["predictions"].items():
                logger.info("  zone=%s predicted=%.1fC confidence=%.3f ema=%.1f",
                           zid, pred["predicted_temp"], pred["confidence"], pred["ema"])

    print("\n=== Predictive Dispatch Summary ===")
    print(dispatch.summary())
