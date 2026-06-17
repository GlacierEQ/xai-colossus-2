#!/usr/bin/env python3
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("COLOSSUS-THERMAL")


@dataclass
class ImmersionTank:
    tank_id: str
    gpu_count: int = 0
    coolant_temp_c: float = 45.0
    boiling_onset_c: float = 61.0
    vapor_recovery_active: bool = False
    flow_rate_lpm: float = 200.0
    heat_load_kw: float = 0.0
    boiling: bool = False
    critical: bool = False
    consecutive_critical_ticks: int = 0


@dataclass
class ImmersionEngine:
    manifest: Dict[str, Any]
    critical_temp_c: float = 85.0
    hot_temp_c: float = 78.0
    boiling_onset_c: float = 61.0
    tank_count: int = 100
    gpus_per_tank: int = 2000
    _tanks: Dict[str, ImmersionTank] = field(default_factory=dict)
    _anomaly_log: List[Dict[str, Any]] = field(default_factory=list)
    _action_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.critical_temp_c = self.manifest.get("critical_temp_c", 85.0)
        self.hot_temp_c = self.manifest.get("hot_temp_c", 78.0)
        self.boiling_onset_c = self.manifest.get("boiling_onset_c", 61.0)
        self.tank_count = self.manifest.get("immersion_tanks", 100)
        self.gpus_per_tank = self.manifest.get("gpus_per_tank", 2000)
        self._init_tanks()

    def _init_tanks(self) -> None:
        for i in range(self.tank_count):
            tank_id = f"IMM-T{i:03d}"
            self._tanks[tank_id] = ImmersionTank(
                tank_id=tank_id,
                gpu_count=self.gpus_per_tank,
                boiling_onset_c=self.boiling_onset_c,
                coolant_temp_c=40.0 + (i % 5),
                flow_rate_lpm=180.0 + (i % 3) * 20,
            )

    def _simulate_boiling(self, tank: ImmersionTank, tick_num: int) -> None:
        if tank.coolant_temp_c >= tank.boiling_onset_c:
            tank.boiling = True
            phase_change_cooling = 0.3 * (tank.coolant_temp_c - tank.boiling_onset_c)
            tank.coolant_temp_c -= phase_change_cooling
            tank.vapor_recovery_active = True
        else:
            tank.boiling = False
            tank.vapor_recovery_active = False

    def _apply_cooling_action(self, tank: ImmersionTank) -> List[str]:
        actions = []

        if tank.coolant_temp_c > self.hot_temp_c:
            boost = min(tank.flow_rate_lpm * 0.2, 100.0)
            tank.flow_rate_lpm += boost
            actions.append(f"INCREASE_FLOW {tank.tank_id} +{boost:.0f} LPM -> {tank.flow_rate_lpm:.0f}")

        if tank.coolant_temp_c > self.boiling_onset_c and not tank.vapor_recovery_active:
            tank.vapor_recovery_active = True
            actions.append(f"ACTIVATE_VAPOR_RECOVERY {tank.tank_id}")

        if tank.coolant_temp_c > self.critical_temp_c:
            tank.critical = True
            tank.consecutive_critical_ticks += 1
        else:
            tank.critical = False
            tank.consecutive_critical_ticks = 0

        return actions

    async def tick(self, zones: Dict[str, Any], tick_num: int) -> Dict[str, Any]:
        anomalies = []
        actions = []
        critical_zones = []

        for tank in self._tanks.values():
            heat_input_kw = (tank.gpu_count / 2000.0) * 1400.0
            heat_input_kw *= (1.0 + math.sin(tick_num * 0.1) * 0.05)
            tank.heat_load_kw = heat_input_kw

            mass_flow_kg_s = tank.flow_rate_lpm / 60.0
            cp = 1560.0
            cooling_capacity_kw = mass_flow_kg_s * cp * (tank.coolant_temp_c - 25.0) / 1000.0
            net_heat_kw = heat_input_kw - cooling_capacity_kw
            mass_kg = tank.flow_rate_lpm
            delta_t = net_heat_kw * 1000.0 / (mass_kg * cp) if mass_kg > 0 else 0.0
            tank.coolant_temp_c += delta_t

            tank.coolant_temp_c = max(20.0, min(tank.coolant_temp_c, 100.0))

            self._simulate_boiling(tank, tick_num)

            tank_actions = self._apply_cooling_action(tank)
            actions.extend(tank_actions)

            if tank.critical:
                anomalies.append(f"CRITICAL_TANK {tank.tank_id} temp={tank.coolant_temp_c:.1f}C "
                               f"consecutive={tank.consecutive_critical_ticks}")

        zone_map = {}
        for tank in self._tanks.values():
            zone_id = tank.tank_id[-1]
            if zone_id not in zone_map:
                zone_map[zone_id] = []
            zone_map[zone_id].append(tank)

        for zone_id, zone in zones.items():
            zone_tanks = [t for t in self._tanks.values() if t.critical]
            if zone_tanks:
                avg_critical_temp = sum(t.coolant_temp_c for t in zone_tanks) / len(zone_tanks)
                if avg_critical_temp > self.critical_temp_c:
                    critical_zones.append(zone_id)

        self._anomaly_log.extend([{"message": a, "tick": tick_num, "ts": datetime.now(timezone.utc).isoformat()}
                                   for a in anomalies])
        self._action_log.extend([{"message": a, "tick": tick_num, "ts": datetime.now(timezone.utc).isoformat()}
                                  for a in actions])

        return {"anomalies": anomalies, "actions": actions, "critical_zones": critical_zones}

    def summary(self) -> Dict[str, Any]:
        tanks = list(self._tanks.values())
        temps = [t.coolant_temp_c for t in tanks]
        boiling_count = sum(1 for t in tanks if t.boiling)
        critical_count = sum(1 for t in tanks if t.critical)
        avg_temp = sum(temps) / len(temps) if temps else 0.0
        return {
            "tanks_online": len(tanks),
            "avg_temp": round(avg_temp, 2),
            "boiling_active_count": boiling_count,
            "critical_count": critical_count,
            "total_anomalies": len(self._anomaly_log),
            "total_actions": len(self._action_log),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    engine = ImmersionEngine(manifest={
        "critical_temp_c": 85.0,
        "hot_temp_c": 78.0,
        "boiling_onset_c": 61.0,
        "immersion_tanks": 20,
        "gpus_per_tank": 2000,
    })

    zones = {"A": None, "B": None, "C": None}

    import asyncio

    async def demo():
        for tick in range(30):
            result = await engine.tick(zones, tick)
            if tick % 5 == 0:
                summary = engine.summary()
                logger.info("TICK %d | tanks=%d | avg_temp=%.1fC | boiling=%d | anomalies=%d",
                           tick, summary["tanks_online"], summary["avg_temp"],
                           summary["boiling_active_count"], len(result["anomalies"]))
                for a in result["anomalies"]:
                    logger.warning("  ANOMALY: %s", a)
                for a in result["actions"][:3]:
                    logger.info("  ACTION: %s", a)

        print("\n=== Immersion Engine Summary ===")
        print(engine.summary())

    asyncio.run(demo())
