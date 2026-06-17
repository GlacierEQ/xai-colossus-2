#!/usr/bin/env python3
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("COLOSSUS-THERMAL")


@dataclass
class ZoneCircuitState:
    zone_id: str
    state: str = "CLOSED"
    anomaly_count: int = 0
    consecutive_anomalies: int = 0
    delta_t_history: List[float] = field(default_factory=list)
    power_surge_history: List[float] = field(default_factory=list)
    last_anomaly_tick: int = 0
    isolation_tick: int = 0
    cooldown_remaining: int = 0
    half_open_ticks: int = 0


@dataclass
class CascadeShield:
    manifest: Dict[str, Any]
    max_anomalies: int = 3
    recovery_ticks: int = 10
    delta_t_threshold_c: float = 15.0
    power_surge_threshold_kw: float = 50000.0
    _zones: Dict[str, ZoneCircuitState] = field(default_factory=dict)
    _event_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.max_anomalies = self.manifest.get("max_consecutive_anomalies", 3)
        self.recovery_ticks = self.manifest.get("recovery_ticks", 10)
        self.delta_t_threshold_c = self.manifest.get("cascade_delta_t_max_c", 15.0)
        self.power_surge_threshold_kw = self.manifest.get("cascade_power_surge_mw", 50.0) * 1000.0

    def _get_zone(self, zone_id: str) -> ZoneCircuitState:
        if zone_id not in self._zones:
            self._zones[zone_id] = ZoneCircuitState(zone_id=zone_id)
        return self._zones[zone_id]

    def evaluate_zone(self, zone_id: str, telemetry: Dict[str, Any]) -> bool:
        zone = self._get_zone(zone_id)

        if zone.state == "OPEN":
            return True

        temp_c = telemetry.get("temp_celsius", 0.0)
        prev_temp = telemetry.get("prev_temp_celsius", temp_c)
        delta_t = abs(temp_c - prev_temp)
        zone.delta_t_history.append(delta_t)
        if len(zone.delta_t_history) > 100:
            zone.delta_t_history = zone.delta_t_history[-100:]

        power_kw = telemetry.get("power_draw_kw", 0.0)
        prev_power = telemetry.get("prev_power_draw_kw", power_kw)
        power_surge = abs(power_kw - prev_power)
        zone.power_surge_history.append(power_surge)
        if len(zone.power_surge_history) > 100:
            zone.power_surge_history = zone.power_surge_history[-100:]

        anomaly = False
        reasons = []

        if delta_t > self.delta_t_threshold_c:
            anomaly = True
            reasons.append(f"delta_t={delta_t:.1f}C > threshold={self.delta_t_threshold_c}C")

        if power_surge > self.power_surge_threshold_kw:
            anomaly = True
            reasons.append(f"power_surge={power_surge:.0f}kW > threshold={self.power_surge_threshold_kw:.0f}kW")

        if temp_c > telemetry.get("critical_temp_c", 85.0):
            anomaly = True
            reasons.append(f"temp={temp_c:.1f}C > critical")

        current_tick = telemetry.get("tick", 0)
        if current_tick - zone.last_anomaly_tick > 1:
            zone.consecutive_anomalies = 0

        if anomaly:
            zone.consecutive_anomalies += 1
            zone.anomaly_count += 1
            zone.last_anomaly_tick = current_tick

            self._event_log.append({
                "zone_id": zone_id,
                "type": "cascade_risk",
                "reasons": reasons,
                "consecutive": zone.consecutive_anomalies,
                "tick": current_tick,
                "ts": datetime.now(timezone.utc).isoformat(),
            })

            logger.warning("CASCADE_RISK zone=%s consecutive=%d reasons=%s",
                          zone_id, zone.consecutive_anomalies, "; ".join(reasons))

            if zone.consecutive_anomalies >= self.max_anomalies:
                zone.state = "OPEN"
                zone.isolation_tick = current_tick
                zone.cooldown_remaining = self.recovery_ticks
                logger.critical("CASCADE_SHIELD: Zone %s ISOLATED (OPEN) after %d consecutive anomalies",
                              zone_id, zone.consecutive_anomalies)
                return True

        return anomaly

    def tick_recovery(self, current_tick: int) -> List[str]:
        recovered = []
        for zone in self._zones.values():
            if zone.state == "OPEN":
                zone.cooldown_remaining -= 1
                if zone.cooldown_remaining <= 0:
                    zone.state = "HALF_OPEN"
                    zone.half_open_ticks = 5
                    logger.info("CASCADE_SHIELD: Zone %s -> HALF_OPEN (cooldown expired)", zone.zone_id)

            elif zone.state == "HALF_OPEN":
                zone.half_open_ticks -= 1
                if zone.half_open_ticks <= 0:
                    zone.state = "CLOSED"
                    zone.anomaly_count = 0
                    zone.consecutive_anomalies = 0
                    recovered.append(zone.zone_id)
                    logger.info("CASCADE_SHIELD: Zone %s -> CLOSED (recovery complete)", zone.zone_id)

        return recovered

    def is_isolated(self, zone_id: str) -> bool:
        zone = self._zones.get(zone_id)
        return zone is not None and zone.state == "OPEN"

    def zone_state(self, zone_id: str) -> str:
        zone = self._zones.get(zone_id)
        return zone.state if zone else "CLOSED"

    def summary(self) -> Dict[str, Any]:
        states = {}
        for zid, zone in self._zones.items():
            states[zid] = {
                "state": zone.state,
                "anomaly_count": zone.anomaly_count,
                "consecutive": zone.consecutive_anomalies,
            }
        return {
            "zones": states,
            "total_events": len(self._event_log),
            "isolated_count": sum(1 for z in self._zones.values() if z.state == "OPEN"),
            "half_open_count": sum(1 for z in self._zones.values() if z.state == "HALF_OPEN"),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    shield = CascadeShield(manifest={
        "max_consecutive_anomalies": 3,
        "cascade_delta_t_max_c": 15.0,
        "cascade_power_surge_mw": 50.0,
    })

    import random

    telemetry_streams = {
        "A": [{"temp_celsius": 65 + random.uniform(0, 5), "power_draw_kw": 50000 + random.uniform(-5000, 5000)} for _ in range(50)],
        "B": [{"temp_celsius": 70 + random.uniform(0, 20), "power_draw_kw": 60000 + random.uniform(-5000, 30000)} for _ in range(50)],
        "C": [{"temp_celsius": 68 + random.uniform(0, 3), "power_draw_kw": 55000 + random.uniform(-2000, 2000)} for _ in range(50)],
    }

    for tick in range(50):
        for zone_id, stream in telemetry_streams.items():
            telemetry = stream[tick]
            telemetry["tick"] = tick
            telemetry["critical_temp_c"] = 85.0
            if tick > 0:
                telemetry["prev_temp_celsius"] = stream[tick - 1]["temp_celsius"]
                telemetry["prev_power_draw_kw"] = stream[tick - 1]["power_draw_kw"]
            else:
                telemetry["prev_temp_celsius"] = telemetry["temp_celsius"]
                telemetry["prev_power_draw_kw"] = telemetry["power_draw_kw"]

            risk = shield.evaluate_zone(zone_id, telemetry)

        recovered = shield.tick_recovery(tick)
        if tick % 10 == 0:
            summary = shield.summary()
            logger.info("TICK %d | isolated=%d | half_open=%d | events=%d",
                       tick, summary["isolated_count"], summary["half_open_count"], summary["total_events"])
            for zid, zs in summary["zones"].items():
                if zs["state"] != "CLOSED":
                    logger.info("  zone=%s state=%s consecutive=%d", zid, zs["state"], zs["consecutive"])

    print("\n=== Cascade Shield Summary ===")
    print(shield.summary())
