"""Colossus 2 Physics — Shared constants, particle database, and conductivity models."""

__all__ = [
    "PARTICLE_DATABASE",
    "BASE_FLUID_THERMAL_CONDUCTIVITY",
    "maxwell_conductivity",
    "hamilton_crosser_conductivity",
    "conductivity_enhancement_pct",
]

from physics.constants import (
    PARTICLE_DATABASE,
    BASE_FLUID_THERMAL_CONDUCTIVITY,
    maxwell_conductivity,
    hamilton_crosser_conductivity,
    conductivity_enhancement_pct,
)
