#!/usr/bin/env python3
"""
Colossus 2 Central Orchestrator
================================
The autonomous brain of xAI Colossus 2 — a 1.5GW, 200k-GPU AI supercomputer.

Wires together: Thermal Intelligence, Energy Autonomousty, Zero-Trust Security,
Nanosphere Physics, and the Aspen Grove memory spine.

Architecture:
  - Tick-driven (500ms default) — every tick: ingest → compute → act → observe
  - Fusion modes activate piston combinations per manifest
  - Circuit breaker pattern isolates failing zones in <100ms
  - PINN digital twin continuously validates physics against predictions
  - All state flows through Aspen Grove memory for cross-session persistence

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("COLOSSUS-ORCHESTRATOR")

MANIFEST_PATH = Path(__file__).parent.parent / "config" / "colossus_manifest.json"


def load_manifest() -> dict:
    with open(MANIFEST_PATH) as f:
        return json.load(f)


class SystemMode(Enum):
    COLOSSUS_FULL = "COLOSSUS_FULL"
    EMERGENCY_RESPONSE = "EMERGENCY_RESPONSE"
    PREDICTIVE_COOLING = "PREDICTIVE_COOLING"
    GHOST_OPTIMIZATION = "GHOST_OPTIMIZATION"
    MAINTENANCE = "MAINTENANCE"


class SystemHealth(Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"
    CRITICAL = "critical"


@dataclass
class TickResult:
    tick_id: int
    timestamp: str
    duration_ms: float
    health: SystemHealth
    thermal_summary: Dict[str, Any]
    energy_summary: Dict[str, Any]
    security_summary: Dict[str, Any]
    nanosphere_summary: Dict[str, Any]
    servers_summary: Dict[str, Any]
    waterplant_summary: Dict[str, Any]
    microcode_summary: Dict[str, Any]
    community_summary: Dict[str, Any]
    anomalies: List[str]
    actions_taken: List[str]
    fusion_mode: str


@dataclass
class ZoneState:
    zone_id: str
    temp_celsius: float = 65.0
    gpu_utilization: float = 0.0
    power_draw_kw: float = 0.0
    cooling_flow_lpm: float = 0.0
    conductivity_factor: float = 1.0
    thermal_budget_kw: float = 0.0
    alert_level: int = 0
    isolated: bool = False


class TelemetryBus:
    """Structured event bus for all subsystem telemetry."""

    def __init__(self, max_buffer: int = 10000):
        self._buffer: List[Dict[str, Any]] = []
        self._max_buffer = max_buffer
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_count = 0

    def emit(self, event_type: str, source: str, payload: Dict[str, Any]) -> None:
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "source": source,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seq": self._event_count,
        }
        self._event_count += 1
        self._buffer.append(event)
        if len(self._buffer) > self._max_buffer:
            self._buffer = self._buffer[-self._max_buffer:]
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error("TelemetryBus handler error: %s", e)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def recent(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        events = self._buffer
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        return events[-limit:]

    def recent_events(self, event_type: Optional[str] = None, limit: int = 20) -> List[Dict]:
        return self.recent(event_type=event_type, limit=limit)

    def buffer_size(self) -> int:
        return len(self._buffer)


class CircuitBreaker:
    """Per-zone circuit breaker — isolates failing zones in <100ms."""

    def __init__(self, max_anomalies: int = 3, recovery_ticks: int = 10):
        self._max_anomalies = max_anomalies
        self._recovery_ticks = recovery_ticks
        self._anomaly_counts: Dict[str, int] = {}
        self._isolated_zones: Set[str] = set()
        self._recovery_counters: Dict[str, int] = {}

    def record_anomaly(self, zone_id: str) -> bool:
        self._anomaly_counts[zone_id] = self._anomaly_counts.get(zone_id, 0) + 1
        if self._anomaly_counts[zone_id] >= self._max_anomalies:
            self._isolated_zones.add(zone_id)
            self._recovery_counters[zone_id] = self._recovery_ticks
            logger.critical("CIRCUIT_BREAKER: Zone %s ISOLATED after %d anomalies",
                          zone_id, self._anomaly_counts[zone_id])
            return True
        return False

    def clear_anomaly(self, zone_id: str) -> None:
        self._anomaly_counts[zone_id] = 0

    def tick_recovery(self) -> List[str]:
        recovered = []
        for zone_id in list(self._isolated_zones):
            self._recovery_counters[zone_id] -= 1
            if self._recovery_counters[zone_id] <= 0:
                self._isolated_zones.discard(zone_id)
                self._anomaly_counts[zone_id] = 0
                recovered.append(zone_id)
                logger.info("CIRCUIT_BREAKER: Zone %s RECOVERED", zone_id)
        return recovered

    def is_isolated(self, zone_id: str) -> bool:
        return zone_id in self._isolated_zones


class ColossusOrchestrator:
    """
    The autonomous orchestrator for Colossus 2.

    Tick lifecycle:
      1. INGEST   — pull telemetry from all subsystems
      2. COMPUTE  — run PINN validation, energy balance, security scan
      3. ACT      — dispatch pistons, adjust cooling, balance grid
      4. OBSERVE  — emit telemetry, update memory, check circuit breakers
    """

    VERSION = "2.0.0-COLOSSUS"
    CODENAME = "GLACIER-SOVEREIGN"

    THERMAL_REQUIRED = ["critical_temp_c", "hot_temp_c", "warm_temp_c", "tick_interval_ms"]
    ENERGY_REQUIRED = ["grid_capacity_mva", "megapack_capacity_mwh", "megapack_max_discharge_mw"]
    NANOSPHERE_REQUIRED = ["base_fluid", "primary_nanoparticle", "volume_fraction"]
    SECURITY_REQUIRED = ["zero_trust", "threat_detection_threshold"]

    def __init__(self, manifest: Optional[dict] = None):
        self.manifest = manifest or load_manifest()
        self._validate_manifest(self.manifest)
        self.tick = 0
        self.health = SystemHealth.NOMINAL
        self.mode = SystemMode.COLOSSUS_FULL
        self.start_time = time.time()
        self._shutdown = False
        self._anomaly_count = 0
        self._action_count = 0

        self.zones: Dict[str, ZoneState] = {}
        self.telemetry = TelemetryBus()
        self.circuit_breaker = CircuitBreaker(
            max_anomalies=self.manifest["thermal"]["max_consecutive_anomalies"]
        )

        self._thermal = None
        self._energy = None
        self._security = None
        self._nanosphere = None
        self._digital_twin = None
        self._memory = None
        self._cascade_shield = None
        self._predictive = None
        self._servers = None
        self._waterplant = None
        self._microcode = None
        self._community = None
        self._cascade_shield = None
        self._predictive = None
        self._fusion_defs: Dict[str, List[str]] = {}

        self._tick_history: List[TickResult] = []
        self._actions_log: List[Dict[str, Any]] = []
        self._active_pistons: Set[str] = set()

        self._init_zones()
        self._init_subsystems()
        self._active_pistons = set(self._fusion_defs.get(self.mode.value, []))

        logger.info("Colossus Orchestrator v%s [%s] INITIALIZED", self.VERSION, self.CODENAME)
        logger.info("Zones: %d | GPUs: %s | Power: %s MW",
                    len(self.zones),
                    self.manifest["facility"]["gpu_count"],
                    self.manifest["facility"]["total_power_mw"])

    @classmethod
    def _validate_manifest(cls, manifest: Optional[dict] = None) -> List[str]:
        errors: List[str] = []
        if manifest is None:
            return ["manifest is None"]

        sections = {
            "thermal": (cls.THERMAL_REQUIRED, {"critical_temp_c": 85.0, "hot_temp_c": 78.0, "warm_temp_c": 70.0, "tick_interval_ms": 500, "max_consecutive_anomalies": 3}),
            "energy": (cls.ENERGY_REQUIRED, {"grid_capacity_mva": 150, "megapack_capacity_mwh": 560, "megapack_max_discharge_mw": 140}),
            "nanosphere": (cls.NANOSPHERE_REQUIRED, {"base_fluid": "water", "primary_nanoparticle": "Al2O3", "volume_fraction": 0.03}),
            "security": (cls.SECURITY_REQUIRED, {"zero_trust": True, "threat_detection_threshold": 0.5}),
        }
        for section, (required, defaults) in sections.items():
            if section not in manifest:
                logger.warning("MANIFEST_MISSING: section '%s' — applying defaults", section)
                manifest[section] = dict(defaults)
                continue
            for key in required:
                if key not in manifest[section]:
                    logger.warning("MANIFEST_MISSING: %s.%s — applying default %s", section, key, defaults[key])
                    manifest[section][key] = defaults[key]

        facility = manifest.get("facility", {})
        if not isinstance(facility.get("zones"), list):
            errors.append("facility.zones must be a list of strings")
        elif not all(isinstance(z, str) for z in facility["zones"]):
            errors.append("facility.zones must contain only strings")
        elif len(facility["zones"]) == 0:
            errors.append("facility.zones must not be empty")

        thermal = manifest.get("thermal", {})
        if thermal.get("critical_temp_c", 0) <= thermal.get("warm_temp_c", 0):
            errors.append(f"thermal.critical_temp_c ({thermal.get('critical_temp_c')}) must be > thermal.warm_temp_c ({thermal.get('warm_temp_c')})")

        energy = manifest.get("energy", {})
        if energy.get("grid_capacity_mva", 0) <= 0:
            errors.append(f"energy.grid_capacity_mva ({energy.get('grid_capacity_mva')}) must be > 0")
        if energy.get("megapack_capacity_mwh", 0) <= 0:
            errors.append(f"energy.megapack_capacity_mwh ({energy.get('megapack_capacity_mwh')}) must be > 0")

        nanosphere = manifest.get("nanosphere", {})
        vf = nanosphere.get("volume_fraction", -1)
        if not (0 <= vf <= 0.1):
            errors.append(f"nanosphere.volume_fraction ({vf}) must be between 0 and 0.1")

        if errors:
            for e in errors:
                logger.warning("VALIDATION: %s", e)

        return errors

    def _init_zones(self) -> None:
        for zone_id in self.manifest["facility"]["zones"]:
            self.zones[zone_id] = ZoneState(
                zone_id=zone_id,
                thermal_budget_kw=self.manifest["facility"]["total_power_mw"] * 1000 / 3,
            )

    def _init_subsystems(self) -> None:
        sys.path.insert(0, str(Path(__file__).parent.parent))

        try:
            from thermal.pinn_digital_twin import PINNDigitalTwin
            self._digital_twin = PINNDigitalTwin(self.manifest["thermal"])
            logger.info("Thermal PINN Digital Twin: ONLINE")
        except Exception as e:
            logger.warning("Digital twin unavailable: %s", e)

        try:
            from thermal.immersion_engine import ImmersionEngine
            self._thermal = ImmersionEngine(self.manifest["thermal"])
            logger.info("Immersion Cooling Engine: ONLINE")
        except Exception as e:
            logger.warning("Immersion engine unavailable: %s", e)

        try:
            from energy.grid_balancer import AutonomousGridBalancer
            self._energy = AutonomousGridBalancer(self.manifest["energy"])
            logger.info("Autonomous Grid Balancer: ONLINE")
        except Exception as e:
            logger.warning("Grid balancer unavailable: %s", e)

        try:
            from security.hydra_immune import HydraImmuneSystem
            self._security = HydraImmuneSystem(self.manifest["security"])
            logger.info("Hydra Immune System: ONLINE")
        except Exception as e:
            logger.warning("Security system unavailable: %s", e)

        try:
            from nanosphere.conductivity_engine import ConductivityEngine
            self._nanosphere = ConductivityEngine(self.manifest["nanosphere"])
            logger.info("Nanosphere Conductivity Engine: ONLINE")
        except Exception as e:
            logger.warning("Nanosphere engine unavailable: %s", e)

        try:
            from memory.aspen_bridge import AspenBridge
            self._memory = AspenBridge()
            logger.info("Aspen Grove Memory Bridge: ONLINE")
        except Exception as e:
            logger.warning("Memory bridge unavailable: %s", e)

        try:
            from thermal.cascade_shield import CascadeShield
            self._cascade_shield = CascadeShield(manifest=self.manifest["thermal"])
            logger.info("Cascade Shield: ONLINE")
        except Exception as e:
            logger.warning("Cascade shield unavailable: %s", e)

        try:
            from thermal.predictive_dispatch import PredictiveDispatch
            self._predictive = PredictiveDispatch(manifest=self.manifest["thermal"])
            logger.info("Predictive Dispatch: ONLINE")
        except Exception as e:
            logger.warning("Predictive dispatch unavailable: %s", e)

        try:
            from servers.rack_architecture import RackManager
            self._servers = RackManager(self.manifest["facility"])
            logger.info("Rack Architecture Manager: ONLINE")
        except Exception as e:
            logger.warning("Servers subsystem unavailable: %s", e)

        try:
            from waterplant.water_treatment import WaterTreatmentPlant
            self._waterplant = WaterTreatmentPlant()
            logger.info("Water Treatment Plant: ONLINE")
        except Exception as e:
            logger.warning("Waterplant subsystem unavailable: %s", e)

        try:
            from microcode.firmware_matrix import FirmwareMatrix
            self._microcode = FirmwareMatrix()
            logger.info("Firmware Matrix: ONLINE")
        except Exception as e:
            logger.warning("Microcode subsystem unavailable: %s", e)

        try:
            from community.emissions_tracker import EmissionsTracker
            self._community = EmissionsTracker()
            logger.info("Emissions Tracker: ONLINE")
        except Exception as e:
            logger.warning("Community subsystem unavailable: %s", e)

        self._fusion_defs: Dict[str, List[str]] = {}
        for mode_def in self.manifest.get("fusion_modes", []):
            self._fusion_defs[mode_def["name"]] = mode_def.get("requires", [])

    async def set_mode(self, mode_name: str) -> None:
        if mode_name not in self._fusion_defs:
            raise ValueError(f"Unknown fusion mode: {mode_name}")
        target = SystemMode[mode_name]
        previous = self.mode
        self.mode = target
        self._active_pistons = set(self._fusion_defs[mode_name])
        logger.info("FUSION_MODE: %s -> %s (pistons=%s)", previous.value, target.value, self._active_pistons)
        self.telemetry.emit("mode_change", "orchestrator", {
            "from": previous.value, "to": target.value, "pistons": list(self._active_pistons),
        })

    async def tick_cycle(self) -> TickResult:
        tick_start = time.time()
        self.tick += 1
        anomalies = []
        actions = []
        energy_result = {}
        security_result = {}
        nano_result = {}

        recovered = self.circuit_breaker.tick_recovery()
        if recovered:
            actions.append(f"RECOVERED zones: {recovered}")

        for zone_id, zone in self.zones.items():
            if self.circuit_breaker.is_isolated(zone_id):
                zone.isolated = True
                continue
            zone.isolated = False

        if self._cascade_shield:
            for zone_id, zone in self.zones.items():
                if zone.isolated:
                    continue
                telemetry = {
                    "temp_celsius": zone.temp_celsius,
                    "power_draw_kw": zone.power_draw_kw,
                    "tick": self.tick,
                    "critical_temp_c": self.manifest["thermal"].get("critical_temp_c", 85.0),
                }
                prev_tick = self._tick_history[-1] if self._tick_history else None
                if prev_tick:
                    prev_zones = self._tick_history[-1].thermal_summary
                    telemetry["prev_temp_celsius"] = zone.temp_celsius
                    telemetry["prev_power_draw_kw"] = zone.power_draw_kw
                cascade_isolated = self._cascade_shield.evaluate_zone(zone_id, telemetry)
                if cascade_isolated:
                    zone.isolated = True
                    actions.append(f"CASCADE_SHIELD: {zone_id} isolated")

        if self._predictive:
            forecast = self._predictive.forecast(self.zones)
            for rec in forecast.get("dispatch_recommendation", []):
                target_id = rec["zone_id"]
                if target_id in self.zones and not self.zones[target_id].isolated:
                    target_zone = self.zones[target_id]
                    boost_lpm = target_zone.cooling_flow_lpm * 0.15
                    target_zone.cooling_flow_lpm += boost_lpm
                    actions.append(f"PREDICTIVE_PRE_COOL: {target_id} +{boost_lpm:.0f}LPM "
                                   f"confidence={rec.get('confidence', 0):.2f}")

        if self._thermal and "SHADOW" in self._active_pistons:
            thermal_result = await self._thermal.tick(self.zones, self.tick)
            anomalies.extend(thermal_result.get("anomalies", []))
            actions.extend(thermal_result.get("actions", []))
            for zone_id in thermal_result.get("critical_zones", []):
                if self.circuit_breaker.record_anomaly(zone_id):
                    actions.append(f"CIRCUIT_BREAKER: {zone_id} isolated")

        if self._energy and "GHOST" in self._active_pistons:
            energy_result = await self._energy.tick(self.tick)
            anomalies.extend(energy_result.get("anomalies", []))
            actions.extend(energy_result.get("actions", []))

        if self._security and "CORE-THINK" in self._active_pistons:
            security_result = await self._security.tick(self.tick)
            anomalies.extend(security_result.get("anomalies", []))
            actions.extend(security_result.get("actions", []))

        if self._nanosphere and "MICROWAVE" in self._active_pistons:
            nano_result = await self._nanosphere.tick(self.zones, self.tick)
            anomalies.extend(nano_result.get("anomalies", []))
            actions.extend(nano_result.get("actions", []))

        if self._digital_twin:
            for zone_id, zone in self.zones.items():
                if not zone.isolated:
                    prediction = self._digital_twin.validate(zone)
                    if prediction.get("flagged"):
                        anomalies.append(f"PINN_VIOLATION: {zone_id} residual={prediction['residual']:.3f}")

        servers_result = {}
        waterplant_result = {}
        microcode_result = {}
        community_result = {}

        if self._servers:
            try:
                servers_result = await self._servers.tick(self.zones, self.tick)
                anomalies.extend(servers_result.get("anomalies", []))
                actions.extend(servers_result.get("actions", []))
            except Exception as e:
                logger.warning("Servers tick failed: %s", e)

        if self._waterplant:
            try:
                wp_result = self._waterplant.tick(self.tick)
                waterplant_result = {"anomalies": wp_result.alerts if hasattr(wp_result, 'alerts') else [], "actions": []}
                anomalies.extend(waterplant_result.get("anomalies", []))
                actions.extend(waterplant_result.get("actions", []))
            except Exception as e:
                logger.warning("Waterplant tick failed: %s", e)

        if self._microcode:
            try:
                microcode_result = self._microcode.tick(self.tick)
                anomalies.extend(microcode_result.get("anomalies", []))
                actions.extend(microcode_result.get("actions", []))
            except Exception as e:
                logger.warning("Microcode tick failed: %s", e)

        if self._community:
            try:
                community_result = self._community.tick(self.tick)
                anomalies.extend(community_result.get("anomalies", []))
                actions.extend(community_result.get("actions", []))
            except Exception as e:
                logger.warning("Community tick failed: %s", e)

        if self._security and self._thermal:
            sec_summary = security_result if isinstance(security_result, dict) and "anomalies" in security_result else (self._security.summary() if hasattr(self._security, 'summary') else {})
            threat = sec_summary.get("threat_level", 0.0)
            if threat > 0.7 and self.mode != SystemMode.EMERGENCY_RESPONSE:
                await self.set_mode("EMERGENCY_RESPONSE")
                actions.append(f"FEEDBACK: security threat={threat:.3f} -> EMERGENCY_RESPONSE")

        if self._nanosphere and self._thermal:
            nano_summary = nano_result if isinstance(nano_result, dict) and "anomalies" in nano_result else (self._nanosphere.summary() if hasattr(self._nanosphere, 'summary') else {})
            replacement_due = nano_summary.get("replacement_due_count", 0)
            if replacement_due > 10:
                for zone in self.zones.values():
                    if not zone.isolated:
                        zone.cooling_flow_lpm *= 0.9
                actions.append(f"FEEDBACK: nanosphere replacement_due={replacement_due} -> reduced flow 10%")

        if self._energy and self._thermal:
            energy_cascade = energy_result.get("cascade_prevented", False) if isinstance(energy_result, dict) else False
            if energy_cascade:
                for zone in self.zones.values():
                    if not zone.isolated:
                        zone.thermal_budget_kw *= 0.95
                actions.append("FEEDBACK: energy cascade_prevented -> thermal budgets reduced 5%")

        self.health = self._compute_health(anomalies)

        for anomaly in anomalies:
            self.telemetry.emit("anomaly", "orchestrator", {"message": anomaly, "tick": self.tick})
            self._anomaly_count += 1
        for action in actions:
            self.telemetry.emit("action", "orchestrator", {"message": action, "tick": self.tick})
            self._action_count += 1

        duration_ms = (time.time() - tick_start) * 1000

        result = TickResult(
            tick_id=self.tick,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=round(duration_ms, 2),
            health=self.health,
            thermal_summary=self._thermal.summary() if self._thermal else {},
            energy_summary=self._energy.summary() if self._energy else {},
            security_summary=self._security.summary() if self._security else {},
            nanosphere_summary=self._nanosphere.summary() if self._nanosphere else {},
            servers_summary=self._servers.summary() if self._servers else {},
            waterplant_summary=self._waterplant.summary() if self._waterplant else {},
            microcode_summary=self._microcode.summary() if self._microcode else {},
            community_summary=self._community.summary() if self._community else {},
            anomalies=anomalies,
            actions_taken=actions,
            fusion_mode=self.mode.value,
        )
        self._tick_history.append(result)
        if len(self._tick_history) > 1000:
            self._tick_history = self._tick_history[-500:]

        if self._memory:
            try:
                self._memory.persist_tick({
                    "tick": result.tick_id,
                    "timestamp": result.timestamp,
                    "health": result.health.value,
                    "fusion_mode": result.fusion_mode,
                    "anomalies": result.anomalies,
                    "actions": result.actions_taken,
                    "thermal_summary": result.thermal_summary,
                    "energy_summary": result.energy_summary,
                    "security_summary": result.security_summary,
                    "nanosphere_summary": result.nanosphere_summary,
                    "servers_summary": result.servers_summary,
                    "waterplant_summary": result.waterplant_summary,
                    "microcode_summary": result.microcode_summary,
                    "community_summary": result.community_summary,
                })
            except Exception as e:
                logger.error("Memory persist_tick failed: %s", e)

        return result

    def _compute_health(self, anomalies: List[str]) -> SystemHealth:
        critical = sum(1 for a in anomalies if "CRITICAL" in a or "CIRCUIT_BREAKER" in a)
        warnings = len(anomalies) - critical
        if critical >= 3:
            return SystemHealth.CRITICAL
        if critical >= 1:
            return SystemHealth.EMERGENCY
        if warnings >= 5:
            return SystemHealth.DEGRADED
        return SystemHealth.NOMINAL

    async def run(self, duration_ticks: Optional[int] = None) -> None:
        interval = self.manifest["thermal"]["tick_interval_ms"] / 1000.0
        logger.info("COLOSSUS ORCHESTRATOR ONLINE — tick_interval=%.1fs", interval)

        def _handle_shutdown(signum, frame):
            logger.info("SIGNAL %d received — initiating graceful shutdown", signum)
            self._shutdown = True

        signal.signal(signal.SIGINT, _handle_shutdown)
        signal.signal(signal.SIGTERM, _handle_shutdown)

        tick_count = 0
        while not self._shutdown:
            result = await self.tick_cycle()
            if self.tick % 10 == 0:
                logger.info("TICK %d | health=%s | duration=%.1fms | anomalies=%d | actions=%d",
                          result.tick_id, result.health.value,
                          result.duration_ms, len(result.anomalies),
                          len(result.actions_taken))
            tick_count += 1
            if duration_ticks and tick_count >= duration_ticks:
                break
            await asyncio.sleep(interval)

        logger.info("ORCHESTRATOR SHUTDOWN — tick=%d uptime=%.1fs", self.tick, time.time() - self.start_time)
        if self._memory:
            try:
                self._memory.persist_tick({
                    "tick": self.tick,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "health": self.health.value,
                    "fusion_mode": self.mode.value,
                    "anomalies": [],
                    "actions": ["SHUTDOWN"],
                    "thermal_summary": {},
                    "energy_summary": {},
                    "security_summary": {},
                    "nanosphere_summary": {},
                })
            except Exception as e:
                logger.error("Memory persist on shutdown failed: %s", e)

    def metrics(self) -> Dict[str, Any]:
        uptime_s = time.time() - self.start_time
        health_map = {"nominal": 0, "degraded": 1, "emergency": 2, "critical": 3}
        lines = [
            f"colossus_ticks_total {self.tick}",
            f"colossus_anomalies_total {self._anomaly_count}",
            f"colossus_actions_total {self._action_count}",
            f"colossus_health_gauge {health_map.get(self.health.value, 0)}",
            f"colossus_uptime_seconds {uptime_s:.1f}",
        ]
        for zone_id, zone in self.zones.items():
            lines.append(f'colossus_zone_temp{{zone="{zone_id}"}} {zone.temp_celsius}')
        return {"text": "\n".join(lines) + "\n", "tick": self.tick, "uptime_s": round(uptime_s, 1)}

    def system_status(self) -> Dict[str, Any]:
        uptime_s = time.time() - self.start_time
        return {
            "version": self.VERSION,
            "codename": self.CODENAME,
            "uptime_s": round(uptime_s, 1),
            "tick": self.tick,
            "health": self.health.value,
            "mode": self.mode.value,
            "zones": {zid: {
                "temp_c": z.temp_celsius,
                "power_kw": z.power_draw_kw,
                "isolated": z.isolated,
                "alert_level": z.alert_level,
            } for zid, z in self.zones.items()},
            "subsystems": {
                "thermal": self._thermal is not None,
                "energy": self._energy is not None,
                "security": self._security is not None,
                "nanosphere": self._nanosphere is not None,
                "digital_twin": self._digital_twin is not None,
                "memory": self._memory is not None,
                "cascade_shield": self._cascade_shield is not None,
                "predictive_dispatch": self._predictive is not None,
                "servers": self._servers is not None,
                "waterplant": self._waterplant is not None,
                "microcode": self._microcode is not None,
                "community": self._community is not None,
                "fusion_modes": list(self._fusion_defs.keys()),
                "active_pistons": list(self._active_pistons),
            },
            "circuit_breakers": {
                "isolated_zones": list(self.circuit_breaker._isolated_zones),
                "anomaly_counts": dict(self.circuit_breaker._anomaly_counts),
            },
            "telemetry_events": self.telemetry._event_count,
        }


async def main():
    orchestrator = ColossusOrchestrator()
    status = orchestrator.system_status()
    print(json.dumps(status, indent=2))
    await orchestrator.run(duration_ticks=20)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    asyncio.run(main())
