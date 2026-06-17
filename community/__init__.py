"""Community subsystem for xAI Colossus 2.

Tracks environmental emissions, community impact metrics, and facility licensing.
"""

from .emissions_tracker import EmissionsEntry, EmissionsTracker
from .community_impact import ImpactMetric, CommunityImpact
from .licensing import LicenseEntry, LicensingManager

__all__ = [
    "EmissionsEntry",
    "EmissionsTracker",
    "ImpactMetric",
    "CommunityImpact",
    "LicenseEntry",
    "LicensingManager",
]

__version__ = "2.0.0-COLOSSUS"
