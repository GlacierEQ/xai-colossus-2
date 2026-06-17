"""Clean Water Act Section 402 compliance — COLOSSUS 2 waterplant subsystem.

Tracks NPDES discharge permit limits for the Colossus 2 facility in Memphis, TN.
Monitors pH, TSS, temperature, and flow against permitted thresholds. Records
all discharge samples with compliance status and maintains violation history
with timestamps for regulatory reporting.

Permit limits based on typical Tennessee NPDES permits for large industrial
cooling water discharges.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("COLOSSUS-WATERPLANT")

# NPDES permit limits (Tennessee DEQ typical for industrial cooling discharge)
PERMIT_PH_LOW = 6.0
PERMIT_PH_HIGH = 9.0
PERMIT_TSS_MGL = 30.0
PERMIT_TEMP_C = 30.0
PERMIT_FLOW_GPM_MIN = 1000.0
PERMIT_FLOW_GPM_MAX = 50000.0


@dataclass
class DischargeSample:
    """A single discharge water sample."""
    tick_num: int
    timestamp: datetime
    ph: float
    tss_mgl: float
    temp_c: float
    flow_gpm: float


@dataclass
class ComplianceCheckResult:
    """Result of a single discharge compliance check."""
    sample: DischargeSample
    compliant: bool
    violations: list[str]


@dataclass
class ViolationRecord:
    """A recorded violation with timestamp and details."""
    tick_num: int
    timestamp: datetime
    parameter: str
    measured: float
    limit: float
    description: str


class WaterCompliance:
    """NPDES discharge permit compliance tracker.

    Evaluates discharge samples against permit limits and records all violations
    with timestamps. Maintains running compliance rate for regulatory reporting.

    Parameters match Tennessee DEQ NPDES permit limits for large industrial
    cooling water discharges (Colossus 2 Memphis facility).
    """

    def __init__(
        self,
        ph_low: float = PERMIT_PH_LOW,
        ph_high: float = PERMIT_PH_HIGH,
        tss_limit: float = PERMIT_TSS_MGL,
        temp_limit: float = PERMIT_TEMP_C,
        flow_min: float = PERMIT_FLOW_GPM_MIN,
        flow_max: float = PERMIT_FLOW_GPM_MAX,
    ) -> None:
        self.ph_low = ph_low
        self.ph_high = ph_high
        self.tss_limit = tss_limit
        self.temp_limit = temp_limit
        self.flow_min = flow_min
        self.flow_max = flow_max

        self._total_discharges = 0
        self._violations: list[ViolationRecord] = []
        self._compliant_count = 0

    def check_discharge(
        self, sample_data: dict[str, float], tick_num: int = 0
    ) -> ComplianceCheckResult:
        """Evaluate a discharge sample against permit limits.

        Args:
            sample_data: Dict with keys ph, tss_mgl, temp_c, flow_gpm.
            tick_num: Current simulation tick for timestamping.

        Returns:
            ComplianceCheckResult with compliant flag and violation list.
        """
        now = datetime.now(timezone.utc)
        sample = DischargeSample(
            tick_num=tick_num,
            timestamp=now,
            ph=sample_data.get("ph", 0.0),
            tss_mgl=sample_data.get("tss_mgl", 0.0),
            temp_c=sample_data.get("temp_c", 0.0),
            flow_gpm=sample_data.get("flow_gpm", 0.0),
        )
        self._total_discharges += 1

        violations: list[str] = []

        # pH check
        if sample.ph < self.ph_low:
            desc = f"pH {sample.ph:.2f} below minimum {self.ph_low}"
            violations.append(desc)
            self._record_violation(tick_num, now, "pH_LOW", sample.ph, self.ph_low, desc)
        elif sample.ph > self.ph_high:
            desc = f"pH {sample.ph:.2f} above maximum {self.ph_high}"
            violations.append(desc)
            self._record_violation(tick_num, now, "pH_HIGH", sample.ph, self.ph_high, desc)

        # TSS check
        if sample.tss_mgl > self.tss_limit:
            desc = f"TSS {sample.tss_mgl:.1f} mg/L exceeds limit {self.tss_limit}"
            violations.append(desc)
            self._record_violation(tick_num, now, "TSS", sample.tss_mgl, self.tss_limit, desc)

        # Temperature check
        if sample.temp_c > self.temp_limit:
            desc = (
                f"Temperature {sample.temp_c:.1f}°C exceeds limit {self.temp_limit}°C"
            )
            violations.append(desc)
            self._record_violation(
                tick_num, now, "TEMPERATURE", sample.temp_c, self.temp_limit, desc
            )

        # Flow range check
        if sample.flow_gpm < self.flow_min:
            desc = f"Flow {sample.flow_gpm:.0f} GPM below minimum {self.flow_min}"
            violations.append(desc)
            self._record_violation(
                tick_num, now, "FLOW_LOW", sample.flow_gpm, self.flow_min, desc
            )
        elif sample.flow_gpm > self.flow_max:
            desc = f"Flow {sample.flow_gpm:.0f} GPM above maximum {self.flow_max}"
            violations.append(desc)
            self._record_violation(
                tick_num, now, "FLOW_HIGH", sample.flow_gpm, self.flow_max, desc
            )

        compliant = len(violations) == 0
        if compliant:
            self._compliant_count += 1
            logger.debug(
                "[tick %d] Discharge COMPLIANT — all parameters within limits",
                tick_num,
            )
        else:
            for v in violations:
                logger.warning("[tick %d] VIOLATION: %s", tick_num, v)

        return ComplianceCheckResult(
            sample=sample, compliant=compliant, violations=violations
        )

    def _record_violation(
        self,
        tick_num: int,
        timestamp: datetime,
        parameter: str,
        measured: float,
        limit: float,
        description: str,
    ) -> None:
        record = ViolationRecord(
            tick_num=tick_num,
            timestamp=timestamp,
            parameter=parameter,
            measured=measured,
            limit=limit,
            description=description,
        )
        self._violations.append(record)

    def summary(self) -> dict[str, Any]:
        """Return compliance summary statistics."""
        total = self._total_discharges
        violations_total = len(self._violations)
        compliance_rate = (
            (self._compliant_count / total * 100.0) if total > 0 else 100.0
        )
        return {
            "total_discharges": total,
            "violations_total": violations_total,
            "compliance_rate_pct": round(compliance_rate, 2),
        }

    @property
    def violations(self) -> list[ViolationRecord]:
        return list(self._violations)

    @property
    def compliance_rate(self) -> float:
        if self._total_discharges == 0:
            return 100.0
        return self._compliant_count / self._total_discharges * 100.0
