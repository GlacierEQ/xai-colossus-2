"""Cooling tower water recirculation — COLOSSUS 2 waterplant subsystem.

Models the cooling tower heat rejection loop that cools condenser water
returning from the 200k GPU immersion cooling infrastructure. Heat duty is
derived from facility power draw; tower performance follows approach/range/cycles
relationships per ASHRAE fundamentals.

Design point: ~145 MW reject heat, approach 3.5°C, range 8°C, 5 cycles of
concentration (Memphis, TN — hot-humid climate, design wet-bulb 26°C).
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("COLOSSUS-WATERPLANT")

# Memphis design conditions (ASHRAE 0.4% cooling)
DESIGN_WET_BULB_C = 26.0
DESIGN_DRY_BULB_C = 35.0

# Cooling tower physical parameters
DESIGN_APPROACH_C = 3.5
DESIGN_RANGE_C = 8.0
DESIGN_CYCLES = 5.0
DESIGN_REJECT_MW = 145.0

# Water properties
WATER_SPECIFIC_HEAT_KJ_KG_C = 4.186
WATER_DENSITY_KG_L = 0.997
LITERS_PER_GALLON = 3.78541

# Alert thresholds
ALERT_APPROACH_C = 5.0
ALERT_CYCLES = 6.0
ALERT_MAKEUP_RATIO = 1.25  # 25% above expected


@dataclass
class CoolingTowerTickResult:
    """Result of a single cooling tower tick."""
    tick_num: int
    approach_temp_c: float
    range_temp_c: float
    cycles: float
    blowdown_gpm: float
    makeup_gpm: float
    hot_water_temp_c: float
    cold_water_temp_c: float
    wet_bulb_temp_c: float
    reject_mw: float
    alerts: list[str] = field(default_factory=list)


class CoolingTower:
    """Model of the cooling tower heat rejection system.

    Simulates cooling performance using approach/range/cycles-of-concentration
    relationships. Tracks blowdown and makeup water requirements. Alerts when
    approach degrades, cycles exceed scaling limits, or makeup rate exceeds
    expected demand.
    """

    def __init__(
        self,
        target_reject_mw: float = DESIGN_REJECT_MW,
        design_approach_c: float = DESIGN_APPROACH_C,
        design_range_c: float = DESIGN_RANGE_C,
        design_cycles: float = DESIGN_CYCLES,
        wet_bulb_c: float = DESIGN_WET_BULB_C,
        tower_count: int = 8,
        cells_per_tower: int = 24,
    ) -> None:
        self.target_reject_mw = target_reject_mw
        self.design_approach = design_approach_c
        self.design_range = design_range_c
        self.design_cycles = design_cycles
        self.wet_bulb_c = wet_bulb_c
        self.tower_count = tower_count
        self.cells_per_tower = cells_per_tower
        self._total_cells = tower_count * cells_per_tower

        # State
        self._cycles_current = design_cycles
        self._last_result: CoolingTowerTickResult | None = None
        self._tick_count = 0
        self._alert_history: list[tuple[int, str]] = []
        self._total_blowdown_gal = 0.0
        self._total_makeup_gal = 0.0

    def _calculate_cooling_duty(
        self, reject_mw: float
    ) -> tuple[float, float, float]:
        """Calculate cold water temp from cooling duty.

        Returns (cold_water_temp_c, hot_water_temp_c, flow_gpm).
        """
        # Convert MW to kJ/s
        reject_kjs = reject_mw * 1000.0
        # Required mass flow: Q = m * cp * dT => m = Q / (cp * range)
        # Use design range, actual flow adjusts
        range_c = self.design_range + random.uniform(-0.3, 0.3)
        mass_flow_kgs = reject_kjs / (WATER_SPECIFIC_HEAT_KJ_KG_C * range_c)
        # Convert kg/s to GPM
        flow_gpm = (mass_flow_kgs / WATER_DENSITY_KG_L) * LITERS_PER_GALLON * 60.0

        cold_temp = self.wet_bulb_c + self.design_approach + random.uniform(-0.2, 0.2)
        hot_temp = cold_temp + range_c

        return cold_temp, hot_temp, flow_gpm

    def tick(self, tick_num: int) -> CoolingTowerTickResult:
        """Simulate one cooling tower cycle (500 ms interval)."""
        self._tick_count = tick_num
        alerts: list[str] = []

        # Reject heat varies with facility load (±5%)
        reject_mw = self.target_reject_mw * (1.0 + random.uniform(-0.05, 0.05))

        # Daily wet-bulb temperature cycle (peaks ~15:00 local)
        hour_fraction = (tick_num % 17280) / 17280.0  # 17280 ticks = 2.4h at 500ms
        wb_variation = 1.5 * math.sin(2 * math.pi * (hour_fraction - 0.25))
        wet_bulb = self.wet_bulb_c + wb_variation

        # Cooling performance
        cold_temp, hot_temp, flow_gpm = self._calculate_cooling_duty(reject_mw)
        cold_temp += (wet_bulb - self.wet_bulb_c) * 0.3  # track wet-bulb changes

        approach = cold_temp - wet_bulb
        range_temp = hot_temp - cold_temp

        # Cycles of concentration drift (evaporation concentrates minerals)
        # Blowdown reduces cycles when above setpoint
        evap_rate = 0.008 * range_temp  # ~0.8% per degree range
        self._cycles_current += evap_rate * 0.001
        if self._cycles_current > self.design_cycles:
            # Automatic blowdown when exceeding target cycles
            blowdown_fraction = (self._cycles_current - self.design_cycles) / self._cycles_current
            self._cycles_current = self.design_cycles
        else:
            blowdown_fraction = 0.0

        # Blowdown and makeup calculation
        flow_lps = flow_gpm / (LITERS_PER_GALLON * 60.0)  # gallons/min → L/s approx
        evap_loss_gpm = flow_gpm * evap_rate
        drift_loss_gpm = flow_gpm * 0.0002  # 0.02% drift loss
        blowdown_gpm = max(evap_loss_gpm * blowdown_fraction, flow_gpm * 0.005)
        makeup_gpm = evap_loss_gpm + drift_loss_gpm + blowdown_gpm

        # Accumulate totals
        self._total_blowdown_gal += blowdown_gpm * 0.5 / 60.0  # 500ms tick
        self._total_makeup_gal += makeup_gpm * 0.5 / 60.0

        # Alert evaluation
        if approach > ALERT_APPROACH_C:
            msg = f"Approach {approach:.2f}°C exceeds {ALERT_APPROACH_C}°C — cooling degradation"
            alerts.append(msg)
            self._alert_history.append((tick_num, msg))

        if self._cycles_current > ALERT_CYCLES:
            msg = (
                f"Cycles of concentration {self._cycles_current:.1f} exceeds "
                f"{ALERT_CYCLES} — scaling risk"
            )
            alerts.append(msg)
            self._alert_history.append((tick_num, msg))

        expected_makeup = evap_loss_gpm + drift_loss_gpm + flow_gpm * 0.005
        if expected_makeup > 0 and makeup_gpm > expected_makeup * ALERT_MAKEUP_RATIO:
            msg = (
                f"Makeup water rate {makeup_gpm:.0f} GPM exceeds expected "
                f"{expected_makeup:.0f} GPM by >25%"
            )
            alerts.append(msg)
            self._alert_history.append((tick_num, msg))

        if alerts:
            for a in alerts:
                logger.warning("[tick %d] COOLING TOWER ALERT: %s", tick_num, a)
        else:
            logger.debug("[tick %d] Cooling tower nominal", tick_num)

        result = CoolingTowerTickResult(
            tick_num=tick_num,
            approach_temp_c=approach,
            range_temp_c=range_temp,
            cycles=self._cycles_current,
            blowdown_gpm=blowdown_gpm,
            makeup_gpm=makeup_gpm,
            hot_water_temp_c=hot_temp,
            cold_water_temp_c=cold_temp,
            wet_bulb_temp_c=wet_bulb,
            reject_mw=reject_mw,
            alerts=alerts,
        )
        self._last_result = result
        return result

    def summary(self) -> dict[str, Any]:
        """Return current operating state as a dictionary."""
        r = self._last_result
        if r is None:
            return {
                "approach_temp_c": 0.0,
                "range_temp_c": 0.0,
                "cycles": 0.0,
                "blowdown_gpm": 0.0,
                "makeup_gpm": 0.0,
            }
        return {
            "approach_temp_c": r.approach_temp_c,
            "range_temp_c": r.range_temp_c,
            "cycles": r.cycles,
            "blowdown_gpm": r.blowdown_gpm,
            "makeup_gpm": r.makeup_gpm,
        }

    @property
    def alert_history(self) -> list[tuple[int, str]]:
        return list(self._alert_history)

    @property
    def total_blowdown_gallons(self) -> float:
        return self._total_blowdown_gal

    @property
    def total_makeup_gallons(self) -> float:
        return self._total_makeup_gal
