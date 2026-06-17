"""Memphis water recycling treatment model — COLOSSUS 2 waterplant subsystem.

Models the industrial water treatment facility that processes Memphis municipal
water for use in the 200k-GPU immersion cooling loop. Five-stage treatment:
INTAKE → FILTRATION → REVERSE_OSMOSIS → UV_STERILIZATION → COOLING_TOWER_RETURN.

Water targets: TDS < 50 ppm, pH 6.5–8.5, turbidity < 0.1 NTU, flow > 10000 gal/min.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("COLOSSUS-WATERPLANT")


class TreatmentStage(Enum):
    INTAKE = "INTAKE"
    FILTRATION = "FILTRATION"
    REVERSE_OSMOSIS = "REVERSE_OSMOSIS"
    UV_STERILIZATION = "UV_STERILIZATION"
    COOLING_TOWER_RETURN = "COOLING_TOWER_RETURN"


# Memphis municipal water baseline (Tennessee river source, pre-treatment)
MEMPHIS_INTAKE_TDS_PPM = 180.0
MEMPHIS_INTAKE_PH = 7.2
MEMPHIS_INTAKE_TURBIDITY_NTU = 2.5
MEMPHIS_INTAKE_TEMP_C = 18.0

# Per-stage reduction factors
STAGE_TDS_REDUCTION = {
    TreatmentStage.INTAKE: 1.0,
    TreatmentStage.FILTRATION: 0.15,
    TreatmentStage.REVERSE_OSMOSIS: 0.95,
    TreatmentStage.UV_STERILIZATION: 0.0,
    TreatmentStage.COOLING_TOWER_RETURN: 0.0,
}

STAGE_TURBIDITY_REDUCTION = {
    TreatmentStage.INTAKE: 1.0,
    TreatmentStage.FILTRATION: 0.90,
    TreatmentStage.REVERSE_OSMOSIS: 0.80,
    TreatmentStage.UV_STERILIZATION: 0.0,
    TreatmentStage.COOLING_TOWER_RETURN: 0.0,
}

# Target operating parameters
TARGET_TDS_PPM = 50.0
TARGET_PH_LOW = 6.5
TARGET_PH_HIGH = 8.5
TARGET_TURBIDITY_NTU = 0.1
TARGET_FLOW_GPM = 10000.0

# Alert thresholds
ALERT_TDS_PPM = 100.0
ALERT_TURBIDITY_NTU = 1.0
ALERT_FLOW_GPM = 5000.0


@dataclass
class StageReading:
    """Snapshot of water quality at a treatment stage."""
    stage: TreatmentStage
    flow_gpm: float
    tds_ppm: float
    ph: float
    turbidity_ntu: float
    water_temp_c: float
    online: bool = True


@dataclass
class TreatmentTickResult:
    """Complete result of a single treatment plant tick."""
    tick_num: int
    flow_gpm: float
    tds_ppm: float
    ph: float
    turbidity_ntu: float
    water_temp_c: float
    stages_online: int
    alerts: list[str] = field(default_factory=list)


class WaterTreatmentPlant:
    """Model of the Memphis industrial water treatment facility.

    Simulates five-stage treatment with per-tick water quality evolution.
    Produces alerts when operating parameters exceed safety thresholds.
    Designed for 200k GPU immersion cooling loop makeup water supply.
    """

    def __init__(
        self,
        target_flow_gpm: float = TARGET_FLOW_GPM,
        intake_tds: float = MEMPHIS_INTAKE_TDS_PPM,
        intake_ph: float = MEMPHIS_INTAKE_PH,
        intake_turbidity: float = MEMPHIS_INTAKE_TURBIDITY_NTU,
        intake_temp_c: float = MEMPHIS_INTAKE_TEMP_C,
        stage_online: dict[TreatmentStage, bool] | None = None,
    ) -> None:
        self.target_flow_gpm = target_flow_gpm
        self.intake_tds = intake_tds
        self.intake_ph = intake_ph
        self.intake_turbidity = intake_turbidity
        self.intake_temp_c = intake_temp_c
        self._stage_online = stage_online or {s: True for s in TreatmentStage}
        self._last_result: TreatmentTickResult | None = None
        self._tick_count = 0
        self._alert_history: list[tuple[int, str]] = []

    def set_stage_online(self, stage: TreatmentStage, online: bool) -> None:
        self._stage_online[stage] = online
        logger.info("Stage %s %s", stage.value, "ONLINE" if online else "OFFLINE")

    def tick(self, tick_num: int) -> TreatmentTickResult:
        """Simulate one treatment cycle (500 ms interval per manifest)."""
        self._tick_count = tick_num
        alerts: list[str] = []

        # Base flow with minor fluctuation (±2%)
        flow = self.target_flow_gpm * (1.0 + random.uniform(-0.02, 0.02))

        # Offline stages degrade output quality
        offline_count = sum(1 for s in TreatmentStage if not self._stage_online[s])
        if offline_count > 0:
            flow *= max(0.3, 1.0 - offline_count * 0.15)
            alerts.append(f"{offline_count} treatment stage(s) offline")

        # Trace through treatment stages
        tds = self.intake_tds
        turbidity = self.intake_turbidity
        ph = self.intake_ph + random.uniform(-0.05, 0.05)
        temp = self.intake_temp_c + random.uniform(-0.3, 0.3)

        for stage in TreatmentStage:
            if not self._stage_online[stage]:
                continue
            tds *= (1.0 - STAGE_TDS_REDUCTION[stage])
            turbidity *= (1.0 - STAGE_TURBIDITY_REDUCTION[stage])
            # UV sterilization has negligible effect on dissolved solids / turbidity
            if stage == TreatmentStage.UV_STERILIZATION:
                tds = max(tds, 2.0)  # minimum residual TDS
                turbidity = max(turbidity, 0.05)

        # Seasonal temperature variation (Memphis: warm summers, mild winters)
        temp += 0.001 * (tick_num % 86400)  # drift over day cycle
        temp = max(10.0, min(35.0, temp))

        stages_online = sum(1 for s in TreatmentStage if self._stage_online[s])

        # Alert evaluation
        if tds > ALERT_TDS_PPM:
            msg = f"TDS {tds:.1f} ppm exceeds alert threshold {ALERT_TDS_PPM}"
            alerts.append(msg)
            self._alert_history.append((tick_num, msg))

        if ph < TARGET_PH_LOW or ph > TARGET_PH_HIGH:
            msg = f"pH {ph:.2f} outside safe range {TARGET_PH_LOW}–{TARGET_PH_HIGH}"
            alerts.append(msg)
            self._alert_history.append((tick_num, msg))

        if turbidity > ALERT_TURBIDITY_NTU:
            msg = f"Turbidity {turbidity:.3f} NTU exceeds alert threshold {ALERT_TURBIDITY_NTU}"
            alerts.append(msg)
            self._alert_history.append((tick_num, msg))

        if flow < ALERT_FLOW_GPM:
            msg = f"Flow {flow:.0f} gal/min below alert threshold {ALERT_FLOW_GPM}"
            alerts.append(msg)
            self._alert_history.append((tick_num, msg))

        if alerts:
            for a in alerts:
                logger.warning("[tick %d] ALERT: %s", tick_num, a)
        else:
            logger.debug("[tick %d] All parameters nominal", tick_num)

        result = TreatmentTickResult(
            tick_num=tick_num,
            flow_gpm=flow,
            tds_ppm=tds,
            ph=ph,
            turbidity_ntu=turbidity,
            water_temp_c=temp,
            stages_online=stages_online,
            alerts=alerts,
        )
        self._last_result = result
        return result

    def summary(self) -> dict[str, Any]:
        """Return current operating state as a dictionary."""
        r = self._last_result
        if r is None:
            return {
                "flow_gpm": 0.0,
                "tds_ppm": 0.0,
                "ph": 0.0,
                "turbidity_ntu": 0.0,
                "water_temp_c": 0.0,
                "stages_online": 0,
            }
        return {
            "flow_gpm": r.flow_gpm,
            "tds_ppm": r.tds_ppm,
            "ph": r.ph,
            "turbidity_ntu": r.turbidity_ntu,
            "water_temp_c": r.water_temp_c,
            "stages_online": r.stages_online,
        }

    def sample_discharge(self) -> dict[str, float]:
        """Return discharge sample for compliance checking."""
        r = self._last_result
        if r is None:
            return {"ph": 0.0, "tss_mgl": 0.0, "temp_c": 0.0, "flow_gpm": 0.0}
        tss = r.turbidity_ntu * 15.0  # approximate TSS from turbidity
        return {
            "ph": r.ph,
            "tss_mgl": tss,
            "temp_c": r.water_temp_c,
            "flow_gpm": r.flow_gpm,
        }

    @property
    def alert_history(self) -> list[tuple[int, str]]:
        return list(self._alert_history)
