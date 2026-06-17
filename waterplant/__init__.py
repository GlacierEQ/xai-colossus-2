"""COLOSSUS 2 Waterplant — municipal water treatment, cooling tower recirculation, and CWA-402 compliance.

Handles the complete water lifecycle for 200k GPU immersion-cooled clusters
in Memphis, TN: intake from municipal supply, multi-stage treatment, cooling
tower heat rejection loop, and Clean Water Act discharge permit tracking.

Usage:
    from waterplant import WaterTreatmentPlant, CoolingTower, WaterCompliance

    wtp = WaterTreatmentPlant()
    ct = CoolingTower(target_reject_mw=145.0)
    wc = WaterCompliance()

    for tick in range(1, 86401):
        wtp.tick(tick)
        ct.tick(tick)
        wc.check_discharge(wtp.sample_discharge())
"""

from waterplant.water_treatment import WaterTreatmentPlant
from waterplant.cooling_tower import CoolingTower
from waterplant.compliance import WaterCompliance

__all__ = ["WaterTreatmentPlant", "CoolingTower", "WaterCompliance"]
__version__ = "1.0.0"
