"""Community licensing and agreements management for xAI Colossus 2.

Manages facility licenses, permits, and regulatory compliance tracking.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger("COLOSSUS-COMMUNITY")


@dataclass
class LicenseEntry:
    """A single license or permit record."""

    license_id: str
    type: str
    issuer: str
    issued_date: str
    expiry_date: str
    status: str
    conditions: List[str]


class LicensingManager:
    """Manages facility licenses and permits."""

    def __init__(self) -> None:
        self._licenses: List[LicenseEntry] = []
        logger.info("LicensingManager initialized")

    def register(self, license_entry: LicenseEntry) -> None:
        """Register a new license or update an existing one."""
        existing = next((l for l in self._licenses if l.license_id == license_entry.license_id), None)
        if existing:
            self._licenses.remove(existing)
            logger.info("Updated license %s", license_entry.license_id)
        else:
            logger.info("Registered license %s (type=%s, expiry=%s)", license_entry.license_id, license_entry.type, license_entry.expiry_date)

        self._licenses.append(license_entry)

    def check_expiry(self, days_warning: int = 90) -> List[dict]:
        """Return licenses expiring within the warning window."""
        now = datetime.now()
        expiring: List[dict] = []

        for lic in self._licenses:
            if lic.status not in ("active", "Active"):
                continue
            try:
                expiry_dt = datetime.fromisoformat(lic.expiry_date)
                days_left = (expiry_dt - now).days
                if 0 <= days_left <= days_warning:
                    expiring.append({
                        "license_id": lic.license_id,
                        "type": lic.type,
                        "expiry_date": lic.expiry_date,
                        "days_remaining": days_left,
                    })
            except ValueError:
                logger.warning("Could not parse expiry_date for license %s: %s", lic.license_id, lic.expiry_date)

        logger.info("check_expiry: %d licenses expiring within %d days", len(expiring), days_warning)
        return expiring

    def check_status(self) -> dict:
        """Categorize all licenses by status."""
        result = {"active": 0, "expiring": 0, "expired": 0, "suspended": 0}
        now = datetime.now()

        for lic in self._licenses:
            status_lower = lic.status.lower()

            if status_lower in ("suspended",):
                result["suspended"] += 1
                continue

            if status_lower not in ("active",):
                result["expired"] += 1
                continue

            try:
                expiry_dt = datetime.fromisoformat(lic.expiry_date)
                days_left = (expiry_dt - now).days
                if days_left <= 0:
                    result["expired"] += 1
                elif days_left <= 90:
                    result["expiring"] += 1
                else:
                    result["active"] += 1
            except ValueError:
                result["active"] += 1

        logger.info("License status: %s", result)
        return result

    def summary(self) -> dict:
        """Return overall license summary counts."""
        status = self.check_status()
        return {
            "total_licenses": len(self._licenses),
            "active_count": status["active"],
            "expiring_count": status["expiring"],
            "expired_count": status["expired"],
        }
