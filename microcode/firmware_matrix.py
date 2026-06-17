"""
COLOSSUS 2 — GPU firmware/driver version tracking matrix.
Tracks firmware versions for all GPU and switch components across 200K H200s.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("COLOSSUS-MICROCODE")


@dataclass
class FirmwareEntry:
    """Single firmware/driver component version record."""
    component: str
    current_version: str
    latest_version: str
    release_date: str
    critical: bool = False
    notes: str = ""
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _hash: Optional[str] = None

    def has_update(self) -> bool:
        return self.current_version != self.latest_version


class FirmwareMatrix:
    """Track firmware versions for all GPU and switch components in Colossus 2."""

    def __init__(self) -> None:
        self._entries: Dict[str, FirmwareEntry] = {}
        self._integrity_hashes: Dict[str, str] = {}
        logger.info("FirmwareMatrix initialized")

    def register(
        self,
        component: str,
        current_version: str,
        latest_version: str,
        critical: bool = False,
        release_date: str = "",
        notes: str = "",
    ) -> FirmwareEntry:
        entry = FirmwareEntry(
            component=component,
            current_version=current_version,
            latest_version=latest_version,
            release_date=release_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            critical=critical,
            notes=notes,
        )
        self._entries[component] = entry
        logger.info(
            "Registered firmware: %s current=%s latest=%s critical=%s",
            component, current_version, latest_version, critical,
        )
        return entry

    def check_updates(self) -> List[FirmwareEntry]:
        updates = [e for e in self._entries.values() if e.has_update()]
        logger.info("Found %d components with available updates", len(updates))
        return updates

    def check_critical(self) -> List[FirmwareEntry]:
        critical = [e for e in self._entries.values() if e.critical and e.has_update()]
        logger.info("Found %d critical security updates", len(critical))
        return critical

    def verify_integrity(self, component: str, expected_hash: str) -> Dict[str, bool]:
        if component not in self._entries:
            logger.warning("Integrity check for unknown component: %s", component)
            return {"valid": False}
        self._integrity_hashes[component] = expected_hash
        entry = self._entries[component]
        computed = hashlib.sha256(
            f"{entry.component}:{entry.current_version}:{entry.latest_version}".encode()
        ).hexdigest()
        valid = computed == expected_hash
        logger.info(
            "Integrity check %s: valid=%s", component, valid,
        )
        return {"valid": valid}

    def summary(self) -> Dict[str, int]:
        total = len(self._entries)
        updates = len(self.check_updates())
        critical = len(self.check_critical())
        return {
            "total_components": total,
            "up_to_date": total - updates,
            "updates_available": updates,
            "critical_updates": critical,
        }

    def tick(self, tick_num: int) -> Dict[str, Any]:
        anomalies = []
        actions = []
        critical = self.check_critical()
        for entry in critical:
            anomalies.append(f"CRITICAL_FIRMWARE: {entry.component} {entry.current_version} -> {entry.latest_version}")
        updates = self.check_updates()
        if len(updates) > 5:
            actions.append(f"FIRMWARE_UPDATE_QUEUE: {len(updates)} components need updates")
        return {"anomalies": anomalies, "actions": actions}
