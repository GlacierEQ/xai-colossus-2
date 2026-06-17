"""
COLOSSUS 2 Microcode Subsystem
GPU firmware/driver tracking, compatibility matrix, and hot-patching simulation.
"""

from .firmware_matrix import FirmwareMatrix, FirmwareEntry
from .driver_compatibility import DriverCompatibility, CompatibilityEntry
from .hot_patcher import HotPatcher, PatchEntry

__all__ = [
    "FirmwareMatrix",
    "FirmwareEntry",
    "DriverCompatibility",
    "CompatibilityEntry",
    "HotPatcher",
    "PatchEntry",
]
