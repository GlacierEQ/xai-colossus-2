"""Community impact assessment for xAI Colossus 2.

Tracks community impact metrics and evaluates overall impact level.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

logger = logging.getLogger("COLOSSUS-COMMUNITY")

METRIC_THRESHOLDS = {
    "traffic_increase_pct": {"threshold": 15.0, "unit": "%", "max_safe": 25.0},
    "property_value_impact_pct": {"threshold": -5.0, "unit": "%", "max_safe": -10.0},
    "jobs_created": {"threshold": 100, "unit": "jobs", "max_safe": 50},
    "tax_revenue_annual": {"threshold": 1_000_000, "unit": "USD", "max_safe": 500_000},
    "water_usage_mgd": {"threshold": 5.0, "unit": "mgd", "max_safe": 10.0},
    "energy_demand_mw": {"threshold": 100.0, "unit": "MW", "max_safe": 150.0},
}


class ImpactLevel(str, Enum):
    """Community impact severity levels."""

    BENEFICIAL = "BENEFICIAL"
    NEUTRAL = "NEUTRAL"
    MINOR_ADVERSE = "MINOR_ADVERSE"
    SIGNIFICANT_ADVERSE = "SIGNIFICANT_ADVERSE"


@dataclass
class ImpactMetric:
    """Single community impact measurement."""

    metric_name: str
    current_value: float
    threshold: float
    unit: str
    severity: str


class CommunityImpact:
    """Tracks and evaluates community impact metrics."""

    def __init__(self) -> None:
        self._metrics: List[ImpactMetric] = []
        logger.info("CommunityImpact initialized with %d metric definitions", len(METRIC_THRESHOLDS))

    def register_metric(self, name: str, value: float) -> ImpactMetric:
        """Register or update a community impact metric."""
        if name not in METRIC_THRESHOLDS:
            raise ValueError(f"Unknown metric: {name}. Valid: {list(METRIC_THRESHOLDS.keys())}")

        cfg = METRIC_THRESHOLDS[name]
        severity = self._classify_severity(name, value, cfg)

        metric = ImpactMetric(
            metric_name=name,
            current_value=value,
            threshold=cfg["threshold"],
            unit=cfg["unit"],
            severity=severity,
        )

        existing = next((m for m in self._metrics if m.metric_name == name), None)
        if existing:
            self._metrics.remove(existing)
        self._metrics.append(metric)

        logger.debug("Metric %s=%s %s classified as %s", name, value, cfg["unit"], severity)
        return metric

    @staticmethod
    def _classify_severity(name: str, value: float, cfg: dict) -> str:
        """Classify metric severity based on thresholds."""
        threshold = cfg["threshold"]
        max_safe = cfg["max_safe"]

        if name in ("jobs_created", "tax_revenue_annual"):
            if value >= threshold:
                return ImpactLevel.BENEFICIAL
            elif value >= max_safe:
                return ImpactLevel.NEUTRAL
            elif value > 0:
                return ImpactLevel.MINOR_ADVERSE
            return ImpactLevel.SIGNIFICANT_ADVERSE

        deviation = abs(value) if name in ("traffic_increase_pct", "property_value_impact_pct") else value
        threshold_abs = abs(threshold)
        max_safe_abs = abs(max_safe)

        if deviation <= threshold_abs:
            return ImpactLevel.BENEFICIAL
        elif deviation <= max_safe_abs:
            return ImpactLevel.NEUTRAL
        else:
            return ImpactLevel.SIGNIFICANT_ADVERSE

    def evaluate(self) -> dict:
        """Evaluate overall community impact."""
        if not self._metrics:
            return {
                "overall_impact": ImpactLevel.NEUTRAL,
                "metrics": [],
                "recommendations": [],
            }

        severities = [m.severity for m in self._metrics]
        adverse_count = sum(1 for s in severities if "ADVERSE" in s)
        beneficial_count = sum(1 for s in severities if s == ImpactLevel.BENEFICIAL)

        if beneficial_count > adverse_count:
            overall = ImpactLevel.BENEFICIAL
        elif adverse_count > 2:
            overall = ImpactLevel.SIGNIFICANT_ADVERSE
        elif adverse_count > 0:
            overall = ImpactLevel.MINOR_ADVERSE
        else:
            overall = ImpactLevel.NEUTRAL

        recommendations = self._generate_recommendations()

        result = {
            "overall_impact": overall,
            "metrics": [vars(m) for m in self._metrics],
            "recommendations": recommendations,
        }

        logger.info("Community impact evaluation: %s (adverse=%d, beneficial=%d)", overall, adverse_count, beneficial_count)
        return result

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current metrics."""
        recs: List[str] = []
        for m in self._metrics:
            if m.severity == ImpactLevel.SIGNIFICANT_ADVERSE:
                recs.append(f"URGENT: Mitigate {m.metric_name} (current: {m.current_value}{m.unit})")
            elif m.severity == ImpactLevel.MINOR_ADVERSE:
                recs.append(f"Monitor {m.metric_name} and plan mitigation (current: {m.current_value}{m.unit})")
        return recs

    def summary(self) -> dict:
        """Return summary counts."""
        return {
            "total_metrics": len(self._metrics),
            "adverse_count": sum(1 for m in self._metrics if "ADVERSE" in m.severity),
            "beneficial_count": sum(1 for m in self._metrics if m.severity == ImpactLevel.BENEFICIAL),
        }
