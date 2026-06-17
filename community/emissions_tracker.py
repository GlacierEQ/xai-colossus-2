"""Environmental emissions monitoring for xAI Colossus 2.

Tracks facility emissions against regulatory permit limits.
"""

import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger("COLOSSUS-COMMUNITY")

PERMIT_LIMITS = {
    "nox_lb_hr": 100.0,
    "sox_lb_hr": 50.0,
    "pm25_ug_m3": 35.0,
    "co2_tons_hr": 500.0,
    "noise_db": 75.0,
}


@dataclass
class EmissionsEntry:
    """Single emissions reading."""

    timestamp: float
    nox_lb_hr: float
    sox_lb_hr: float
    pm25_ug_m3: float
    co2_tons_hr: float
    noise_db: float


class EmissionsTracker:
    """Tracks facility emissions against permit limits."""

    def __init__(self, window_hours: int = 24) -> None:
        self._window_hours = window_hours
        self._entries: List[EmissionsEntry] = []
        self._violations_total = 0
        logger.info("EmissionsTracker initialized (window=%dh, limits=%s)", window_hours, PERMIT_LIMITS)

    def ingest(self, entry: EmissionsEntry) -> dict:
        """Ingest a single emissions reading and check compliance."""
        self._entries.append(entry)
        violations: List[str] = []

        checks = [
            ("NOX", entry.nox_lb_hr, PERMIT_LIMITS["nox_lb_hr"], "lb/hr"),
            ("SOX", entry.sox_lb_hr, PERMIT_LIMITS["sox_lb_hr"], "lb/hr"),
            ("PM2.5", entry.pm25_ug_m3, PERMIT_LIMITS["pm25_ug_m3"], "ug/m3"),
            ("CO2", entry.co2_tons_hr, PERMIT_LIMITS["co2_tons_hr"], "tons/hr"),
            ("Noise", entry.noise_db, PERMIT_LIMITS["noise_db"], "dB"),
        ]

        for name, value, limit, unit in checks:
            if value >= limit:
                violations.append(f"{name}={value:.2f} {unit} >= limit {limit} {unit}")
                self._violations_total += 1

        result = {"compliant": len(violations) == 0, "violations": violations}
        if violations:
            logger.warning("Emissions violation at %.0f: %s", entry.timestamp, violations)
        else:
            logger.debug("Emissions reading compliant at %.0f", entry.timestamp)

        return result

    def _window_entries(self) -> List[EmissionsEntry]:
        """Return entries within the rolling window."""
        cutoff = datetime.now().timestamp() - (self._window_hours * 3600)
        return [e for e in self._entries if e.timestamp >= cutoff]

    def track_24h(self) -> dict:
        """Compute 24-hour rolling averages and compliance rate."""
        entries = self._window_entries()
        if not entries:
            return {
                "avg_nox": 0.0,
                "avg_sox": 0.0,
                "avg_pm25": 0.0,
                "avg_co2": 0.0,
                "avg_noise": 0.0,
                "compliance_rate": 1.0,
            }

        avg_nox = statistics.mean(e.nox_lb_hr for e in entries)
        avg_sox = statistics.mean(e.sox_lb_hr for e in entries)
        avg_pm25 = statistics.mean(e.pm25_ug_m3 for e in entries)
        avg_co2 = statistics.mean(e.co2_tons_hr for e in entries)
        avg_noise = statistics.mean(e.noise_db for e in entries)

        compliant_count = sum(
            1 for e in entries
            if e.nox_lb_hr < PERMIT_LIMITS["nox_lb_hr"]
            and e.sox_lb_hr < PERMIT_LIMITS["sox_lb_hr"]
            and e.pm25_ug_m3 < PERMIT_LIMITS["pm25_ug_m3"]
            and e.co2_tons_hr < PERMIT_LIMITS["co2_tons_hr"]
            and e.noise_db < PERMIT_LIMITS["noise_db"]
        )

        result = {
            "avg_nox": round(avg_nox, 4),
            "avg_sox": round(avg_sox, 4),
            "avg_pm25": round(avg_pm25, 4),
            "avg_co2": round(avg_co2, 4),
            "avg_noise": round(avg_noise, 4),
            "compliance_rate": round(compliant_count / len(entries), 4),
        }

        logger.info(
            "24h tracking: %d entries, compliance=%.2f%%",
            len(entries),
            result["compliance_rate"] * 100,
        )
        return result

    def summary(self) -> dict:
        """Return overall emissions summary."""
        total = len(self._entries)
        return {
            "total_readings": total,
            "violations_total": self._violations_total,
            "compliance_rate_pct": round(
                ((total - self._violations_total) / total * 100) if total else 100.0, 2
            ),
        }

    def tick(self, tick_num: int) -> dict:
        """Simulate a tick — generate random emissions reading and check compliance."""
        import random
        entry = EmissionsEntry(
            timestamp=time.time(),
            nox_lb_hr=random.uniform(20, 120),
            sox_lb_hr=random.uniform(10, 60),
            pm25_ug_m3=random.uniform(5, 40),
            co2_tons_hr=random.uniform(100, 600),
            noise_db=random.uniform(50, 80),
        )
        result = self.ingest(entry)
        anomalies = []
        actions = []
        for v in result.get("violations", []):
            anomalies.append(f"EMISSIONS_VIOLATION: {v}")
        return {"anomalies": anomalies, "actions": actions}
