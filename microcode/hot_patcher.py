"""
COLOSSUS 2 — Live microcode patching simulation.
Simulates hot-patching of firmware on GPU and switch components.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("COLOSSUS-MICROCODE")


@dataclass
class PatchEntry:
    """Record of a single firmware patch operation."""
    patch_id: str
    component: str
    version_before: str
    version_after: str
    applied_at: str
    rollback_available: bool = True
    rolled_back: bool = False


class HotPatcher:
    """Simulate live firmware patching for Colossus 2 components."""

    def __init__(self) -> None:
        self._active_versions: Dict[str, str] = {}
        self._patch_history: List[PatchEntry] = []
        self._rollbacks: Dict[str, PatchEntry] = {}
        logger.info("HotPatcher initialized")

    def register_component(self, component: str, current_version: str) -> None:
        self._active_versions[component] = current_version
        logger.info("Registered component %s at version %s", component, current_version)

    def apply_patch(self, component: str, new_version: str) -> Dict[str, str]:
        if component not in self._active_versions:
            logger.error("Cannot patch unknown component: %s", component)
            return {"success": "false", "patch_id": ""}

        old_version = self._active_versions[component]
        patch_id = f"PATCH-{uuid.uuid4().hex[:12].upper()}"
        applied_at = datetime.now(timezone.utc).isoformat()

        entry = PatchEntry(
            patch_id=patch_id,
            component=component,
            version_before=old_version,
            version_after=new_version,
            applied_at=applied_at,
        )

        self._active_versions[component] = new_version
        self._patch_history.append(entry)
        self._rollbacks[patch_id] = entry

        logger.info(
            "Applied patch %s on %s: %s -> %s",
            patch_id, component, old_version, new_version,
        )
        return {"success": "true", "patch_id": patch_id}

    def rollback(self, patch_id: str) -> Dict[str, bool]:
        if patch_id not in self._rollbacks:
            logger.warning("Rollback requested for unknown patch: %s", patch_id)
            return {"success": False}

        entry = self._rollbacks[patch_id]
        if entry.rolled_back:
            logger.warning("Patch %s already rolled back", patch_id)
            return {"success": False}

        self._active_versions[entry.component] = entry.version_before
        entry.rolled_back = True
        entry.rollback_available = False
        del self._rollbacks[patch_id]

        logger.info(
            "Rolled back patch %s on %s: %s -> %s",
            patch_id, entry.component, entry.version_after, entry.version_before,
        )
        return {"success": True}

    def get_patch_history(self) -> List[PatchEntry]:
        return list(self._patch_history)

    def get_current_version(self, component: str) -> Optional[str]:
        return self._active_versions.get(component)

    def summary(self) -> Dict[str, int]:
        total = len(self._patch_history)
        active = sum(1 for p in self._patch_history if not p.rolled_back)
        rollbacks = sum(1 for p in self._patch_history if p.rollback_available and not p.rolled_back)
        return {
            "total_patches": total,
            "active_patches": active,
            "rollbacks_available": rollbacks,
        }
