#!/usr/bin/env python3
"""
Colossus 2 Physics Constants
=============================
Single source of truth for nanoparticle database, fluid properties,
and effective medium conductivity models (Maxwell, Hamilton-Crosser).
"""

from typing import Dict, Any

PARTICLE_DATABASE: Dict[str, Dict[str, Any]] = {
    "Al2O3": {
        "name": "Aluminum Oxide",
        "thermal_conductivity_wmk": 40.0,
        "shape": "spherical",
        "shape_factor": 3.0,
        "density_kgm3": 3970.0,
        "half_life_days": 180,
        "cost_factor": 1.0,
        "fresh_enhancement_pct": 12.0,
    },
    "TiO2": {
        "name": "Titanium Dioxide",
        "thermal_conductivity_wmk": 8.4,
        "shape": "spherical",
        "shape_factor": 3.0,
        "density_kgm3": 4230.0,
        "half_life_days": 200,
        "cost_factor": 1.2,
        "fresh_enhancement_pct": 8.5,
    },
    "CuO": {
        "name": "Copper Oxide",
        "thermal_conductivity_wmk": 76.5,
        "shape": "spherical",
        "shape_factor": 3.0,
        "density_kgm3": 6310.0,
        "half_life_days": 150,
        "cost_factor": 1.5,
        "fresh_enhancement_pct": 18.0,
    },
    "graphene": {
        "name": "Graphene Nanoplatelets",
        "thermal_conductivity_wmk": 5000.0,
        "shape": "platelet",
        "shape_factor": 1.5,
        "density_kgm3": 2200.0,
        "half_life_days": 120,
        "cost_factor": 5.0,
        "fresh_enhancement_pct": 35.0,
    },
    "SiC": {
        "name": "Silicon Carbide",
        "thermal_conductivity_wmk": 120.0,
        "shape": "spherical",
        "shape_factor": 3.0,
        "density_kgm3": 3210.0,
        "half_life_days": 220,
        "cost_factor": 2.0,
        "fresh_enhancement_pct": 15.0,
    },
    "ZnO": {
        "name": "Zinc Oxide",
        "thermal_conductivity_wmk": 50.0,
        "shape": "spherical",
        "shape_factor": 3.0,
        "density_kgm3": 5610.0,
        "half_life_days": 170,
        "cost_factor": 0.8,
        "fresh_enhancement_pct": 10.0,
    },
    "Fe3O4": {
        "name": "Magnetite",
        "thermal_conductivity_wmk": 5.6,
        "shape": "spherical",
        "shape_factor": 3.0,
        "density_kgm3": 5180.0,
        "half_life_days": 140,
        "cost_factor": 0.9,
        "fresh_enhancement_pct": 7.0,
    },
}

BASE_FLUID_THERMAL_CONDUCTIVITY = 0.606  # W/m·K for water at 50°C


def maxwell_conductivity(k_f: float, k_p: float, phi: float) -> float:
    numerator = k_p + 2.0 * k_f + 2.0 * phi * (k_p - k_f)
    denominator = k_p + 2.0 * k_f - phi * (k_p - k_f)
    if abs(denominator) < 1e-12:
        return k_f
    return k_f * numerator / denominator


def hamilton_crosser_conductivity(
    k_f: float, k_p: float, phi: float, shape_factor: float
) -> float:
    if abs(k_p - k_f) < 1e-12:
        return k_f
    numerator = (
        k_p
        + (shape_factor - 1.0) * k_f
        - (shape_factor - 1.0) * phi * (k_f - k_p)
    )
    denominator = (
        k_p + (shape_factor - 1.0) * k_f + phi * (k_f - k_p)
    )
    if abs(denominator) < 1e-12:
        return k_f
    return k_f * numerator / denominator


def conductivity_enhancement_pct(k_f: float, k_p: float, phi: float) -> float:
    k_eff = maxwell_conductivity(k_f, k_p, phi)
    if abs(k_f) < 1e-12:
        return 0.0
    return (k_eff / k_f - 1.0) * 100.0
