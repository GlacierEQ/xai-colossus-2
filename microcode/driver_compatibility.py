"""
COLOSSUS 2 — CUDA/driver compatibility matrix.
Manages CUDA-driver-GPU compatibility across 200K H200 nodes.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger("COLOSSUS-MICROCODE")


@dataclass
class CompatibilityEntry:
    """A known CUDA-driver-GPU compatibility record."""
    cuda_version: str
    driver_version: str
    supported_gpus: List[str]
    known_issues: List[str] = field(default_factory=list)


@dataclass
class _CheckResult:
    compatible: bool
    warnings: List[str]


class DriverCompatibility:
    """Manage CUDA-driver-GPU compatibility for Colossus 2."""

    def __init__(self) -> None:
        self._entries: List[CompatibilityEntry] = []
        self._incompatible: Set[tuple] = set()
        self._checked_count = 0
        logger.info("DriverCompatibility initialized")

    def register(
        self,
        cuda_version: str,
        driver_version: str,
        supported_gpus: List[str],
        known_issues: Optional[List[str]] = None,
    ) -> CompatibilityEntry:
        entry = CompatibilityEntry(
            cuda_version=cuda_version,
            driver_version=driver_version,
            supported_gpus=supported_gpus,
            known_issues=known_issues or [],
        )
        self._entries.append(entry)
        logger.info(
            "Registered compatibility: CUDA %s + Driver %s (GPUs: %s)",
            cuda_version, driver_version, supported_gpus,
        )
        return entry

    def register_incompatible(self, cuda_version: str, driver_version: str, gpu_model: str) -> None:
        self._incompatible.add((cuda_version, driver_version, gpu_model))
        logger.warning(
            "Registered incompatible: CUDA %s + Driver %s + GPU %s",
            cuda_version, driver_version, gpu_model,
        )

    def check(
        self, cuda_version: str, driver_version: str, gpu_model: str,
    ) -> Dict[str, object]:
        self._checked_count += 1
        warnings: List[str] = []

        if (cuda_version, driver_version, gpu_model) in self._incompatible:
            logger.warning(
                "Incompatible combination detected: CUDA %s + Driver %s + GPU %s",
                cuda_version, driver_version, gpu_model,
            )
            return {"compatible": False, "warnings": ["Known incompatible combination"]}

        entry = self._find_entry(cuda_version, driver_version)
        if entry is None:
            warnings.append(
                f"No compatibility record for CUDA {cuda_version} + Driver {driver_version}"
            )
            logger.info(
                "No record for CUDA %s + Driver %s; GPU %s",
                cuda_version, driver_version, gpu_model,
            )
            return {"compatible": True, "warnings": warnings}

        if gpu_model not in entry.supported_gpus:
            warnings.append(
                f"GPU {gpu_model} not in supported list for CUDA {cuda_version} + Driver {driver_version}"
            )

        if entry.known_issues:
            warnings.extend(entry.known_issues)

        compatible = gpu_model in entry.supported_gpus
        logger.info(
            "Checked CUDA %s + Driver %s + GPU %s: compatible=%s warnings=%d",
            cuda_version, driver_version, gpu_model, compatible, len(warnings),
        )
        return {"compatible": compatible, "warnings": warnings}

    def _find_entry(self, cuda_version: str, driver_version: str) -> Optional[CompatibilityEntry]:
        for e in self._entries:
            if e.cuda_version == cuda_version and e.driver_version == driver_version:
                return e
        return None

    def summary(self) -> Dict[str, int]:
        return {
            "total_entries": len(self._entries),
            "checked_count": self._checked_count,
            "incompatible_count": len(self._incompatible),
        }
