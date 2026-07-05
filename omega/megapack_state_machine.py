# Omega (How) — Controllers | Alpha (What) — Pure Physics | 1337.
#!/usr/bin/env python3
"""
Tesla Megapack Deterministic Finite State Machine
=================================================
8-state FSM governing battery storage behavior for Colossus 2.

States: IDLE, CHARGING, DISCHARGING, FREQUENCY_RESPONSE,
        PEAK_SHAVE, RESERVE, FAULT, MAINTENANCE

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("COLOSSUS-ENERGY")


class MegapackState(Enum):
    IDLE = "IDLE"
    CHARGING = "CHARGING"
    DISCHARGING = "DISCHARGING"
    FREQUENCY_RESPONSE = "FREQUENCY_RESPONSE"
    PEAK_SHAVE = "PEAK_SHAVE"
    RESERVE = "RESERVE"
    FAULT = "FAULT"
    MAINTENANCE = "MAINTENANCE"


@dataclass
class StateTransition:
    from_state: MegapackState
    to_state: MegapackState
    timestamp: str
    reason: str
    guard_passed: bool


@dataclass
class MegapackConfig:
    capacity_mwh: float = 560.0
    max_discharge_mw: float = 140.0
    max_charge_mw: float = 70.0
    low_soc_threshold: float = 0.10
    critical_soc_threshold: float = 0.05
    full_soc_threshold: float = 0.95
    efficiency: float = 0.92
    pulse_max_duration_s: float = 30.0
    frequency_response_max_s: float = 5.0


@dataclass
class MegapackState_:
    state: MegapackState = MegapackState.IDLE
    soc: float = 0.50
    power_mw: float = 0.0
    temperature_c: float = 25.0
    grid_available: bool = True
    fault_code: Optional[str] = None
    maintenance_scheduled: bool = False


class TeslaMegapack:
    """Deterministic FSM for Tesla Megapack battery storage."""

    def __init__(self, config: Optional[MegapackConfig] = None):
        self.config = config or MegapackConfig()
        self.current = MegapackState_()
        self.transition_log: List[StateTransition] = []
        self._max_log = 1000
        logger.info("TeslaMegapack INITIALIZED | capacity=%.0fMWh max_discharge=%.0fMW",
                     self.config.capacity_mwh, self.config.max_discharge_mw)

    def get_transition_log(self) -> List[Dict[str, Any]]:
        return [
            {"from": t.from_state.value, "to": t.to_state.value,
             "timestamp": t.timestamp, "reason": t.reason, "guard_passed": t.guard_passed}
            for t in self.transition_log[-50:]
        ]

    def _log_transition(self, to_state: MegapackState, reason: str, guard_passed: bool) -> None:
        entry = StateTransition(
            from_state=self.current.state,
            to_state=to_state,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            guard_passed=guard_passed,
        )
        self.transition_log.append(entry)
        if len(self.transition_log) > self._max_log:
            self.transition_log = self.transition_log[-self._max_log // 2:]
        logger.info("MEGAPACK_TRANSITION: %s → %s | reason=%s | SOC=%.1f%%",
                     self.current.state.value, to_state.value, reason, self.current.soc * 100)

    def _can_transition(self, to_state: MegapackState) -> Tuple[bool, str]:
        s = self.current.state
        if s == MegapackState.FAULT:
            if to_state == MegapackState.MAINTENANCE:
                return True, "FAULT→MAINTENANCE: fault requires maintenance"
            return False, "FAULT: locked until cleared"
        if s == MegapackState.MAINTENANCE:
            if to_state == MegapackState.IDLE:
                return True, "MAINTENANCE→IDLE: maintenance complete"
            return False, "MAINTENANCE: locked until cleared"
        if self.current.soc <= self.config.critical_soc_threshold:
            if to_state == MegapackState.DISCHARGING:
                return False, f"CRITICAL SOC {self.current.soc:.1%} blocks discharge"
            if to_state == MegapackState.IDLE:
                return True, f"CRITICAL SOC → IDLE for safety"
        if self.current.soc >= self.config.full_soc_threshold:
            if to_state == MegapackState.CHARGING:
                return False, f"FULL SOC {self.current.soc:.1%} blocks charging"
        if not self.current.grid_available:
            allowed_grid_loss = {MegapackState.DISCHARGING, MegapackState.IDLE}
            if to_state not in allowed_grid_loss:
                return False, f"GRID LOSS: {to_state.value} unavailable without grid"
        if s == to_state:
            return False, f"Already in {s.value}"
        return True, f"Guard passed: {s.value}→{to_state.value}"

    def transition_to(self, to_state: MegapackState, reason: str) -> bool:
        allowed, msg = self._can_transition(to_state)
        self._log_transition(to_state, reason, allowed)
        if not allowed:
            logger.warning("MEGAPACK_GUARD_BLOCKED: %s", msg)
            return False
        self.current.state = to_state
        return True

    def set_grid_status(self, available: bool) -> None:
        if self.current.grid_available == available:
            return
        self.current.grid_available = available
        if not available:
            logger.critical("MEGAPACK_GRID_LOSS: grid unavailable — initiating failover")
            self.transition_to(MegapackState.DISCHARGING, "GRID_LOSS_FAILOVER")
        else:
            logger.info("MEGAPACK_GRID_RESTORED: grid restored")
            if self.current.state == MegapackState.DISCHARGING:
                self.transition_to(MegapackState.IDLE, "GRID_RESTORED")

    def trigger_fault(self, fault_code: str) -> None:
        self.current.fault_code = fault_code
        self.transition_to(MegapackState.FAULT, f"FAULT_TRIGGERED: {fault_code}")

    def clear_fault(self) -> None:
        if self.current.state == MegapackState.FAULT:
            self.current.fault_code = None
            self.transition_to(MegapackState.MAINTENANCE, "FAULT_CLEARED")

    def pulse_discharge(self, power_mw: float, duration_s: float) -> bool:
        if duration_s > self.config.pulse_max_duration_s:
            logger.warning("PULSE_BLOCKED: duration %.1fs exceeds max %.1fs",
                           duration_s, self.config.pulse_max_duration_s)
            return False
        if power_mw > self.config.max_discharge_mw:
            logger.warning("PULSE_BLOCKED: power %.1fMW exceeds max %.1fMW",
                           power_mw, self.config.max_discharge_mw)
            return False
        if self.current.state == MegapackState.DISCHARGING:
            self.current.power_mw = power_mw
            return True
        if self.transition_to(MegapackState.DISCHARGING, f"PULSE_DISCHARGE: {power_mw}MW/{duration_s}s"):
            self.current.power_mw = power_mw
            return True
        return False

    def update_soc(self, power_mw: float, dt_s: float) -> None:
        energy_delta = power_mw * dt_s / 3600.0
        if power_mw > 0:
            energy_delta *= self.config.efficiency
        elif power_mw < 0:
            energy_delta *= (1.0 / self.config.efficiency)
        self.current.soc = max(0.0, min(1.0, self.current.soc + energy_delta / self.config.capacity_mwh))
        if self.current.soc <= self.config.critical_soc_threshold:
            logger.critical("MEGAPACK_SOC_CRITICAL: %.1f%%", self.current.soc * 100)
        elif self.current.soc <= self.config.low_soc_threshold:
            logger.warning("MEGAPACK_SOC_LOW: %.1f%%", self.current.soc * 100)

    def tick(self, tick_num: int) -> Dict[str, Any]:
        anomalies = []
        actions = []
        if self.current.state == MegapackState.IDLE and self.current.soc < self.config.low_soc_threshold:
            if self.current.grid_available:
                self.transition_to(MegapackState.CHARGING, "LOW_SOC_RECHARGE")
                actions.append("LOW_SOC_RECHARGE initiated")
        if self.current.state == MegapackState.DISCHARGING:
            if self.current.soc <= self.config.critical_soc_threshold:
                self.transition_to(MegapackState.IDLE, "CRITICAL_SOC_CUTOFF")
                anomalies.append("MEGAPACK_CRITICAL_SOC_CUTOFF")
                actions.append("Discharge halted — critical SOC")
        if self.current.state == MegapackState.CHARGING:
            self.update_soc(self.config.max_charge_mw, 0.5)
        if self.current.state == MegapackState.FAULT:
            anomalies.append(f"MEGAPACK_FAULT: {self.current.fault_code}")
        return {
            "state": self.current.state.value,
            "soc": round(self.current.soc, 4),
            "power_mw": self.current.power_mw,
            "grid_available": self.current.grid_available,
            "fault_code": self.current.fault_code,
            "anomalies": anomalies,
            "actions": actions,
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "state": self.current.state.value,
            "soc_percent": round(self.current.soc * 100, 2),
            "power_mw": self.current.power_mw,
            "temperature_c": self.current.temperature_c,
            "grid_available": self.current.grid_available,
            "fault_code": self.current.fault_code,
            "transitions": len(self.transition_log),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    mp = TeslaMegapack()
    print("Initial:", mp.summary())
    for i in range(10):
        result = mp.tick(i)
        print(f"Tick {i}: {result}")
    print("Final:", mp.summary())
    print("Transition log:", len(mp.transition_log), "entries")
