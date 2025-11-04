"""Cargador de generación eólica con comentarios detallados."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from profiles.io import ProfilePowerStore
from core.calendar import ModelCalendar


@dataclass(frozen=True)
class WindPlant:
    """Define los atributos principales de una planta eólica."""

    name: str
    busbar: str
    profile: str
    pmax: float
    pmin: float
    vomc: float
    inv_cost: float
    candidate: bool


@dataclass
class WindData:
    """Empaqueta el catálogo de plantas y sus factores promedio."""

    plants: Dict[str, WindPlant]
    af: Dict[Tuple[str, int, int], float]


def _num(value, default: float = 0.0) -> float:
    """Convierte ``value`` a número flotante con ``default`` como respaldo."""

    try:
        return float(value)
    except Exception:
        return float(default)


def _bool(value) -> bool:
    """Normaliza valores textuales/numéricos a un booleano estándar."""

    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def load_wind_generators(
    path_wind_csv: Path,
    pstore: ProfilePowerStore,
    calendar: ModelCalendar,
) -> WindData:
    """Lee el CSV de eólica y calcula factores medios por bloque."""

    df = pd.read_csv(path_wind_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    plants: Dict[str, WindPlant] = {}
    plant_to_profile: Dict[str, str] = {}

    for _, row in df.iterrows():
        name = str(row["name"])
        profile = str(row.get("zone", row.get("profile", "")))

        plants[name] = WindPlant(
            name=name,
            busbar=str(row.get("busbar", "")),
            profile=profile,
            pmax=_num(row.get("pmax", 0.0)),
            pmin=_num(row.get("pmin", 0.0)),
            vomc=_num(row.get("vomc_avg", 0.0)),
            inv_cost=_num(row.get("gen_inv_cost", 0.0)),
            candidate=_bool(row.get("candidate", False)),
        )
        plant_to_profile[name] = profile

    blocks_detail = calendar.blocks_assignments_df[["stage", "block", "time"]].copy()
    blocks_detail["time"] = pd.to_datetime(blocks_detail["time"], format="%Y-%m-%d-%H:%M", errors="raise")

    af: Dict[Tuple[str, int, int], float] = {}
    available_profiles = {p for p in plant_to_profile.values() if p in pstore.power_wide.columns}

    for (stage, block), chunk in blocks_detail.groupby(["stage", "block"], sort=False):
        timestamps = chunk["time"]
        if timestamps.empty or not available_profiles:
            continue

        sub = pstore.power_wide.reindex(timestamps)
        if sub is None or sub.empty:
            continue

        sub = sub[list(available_profiles)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        profile_mean = sub.mean(axis=0).to_dict()

        for plant, profile in plant_to_profile.items():
            if profile not in profile_mean:
                continue
            value = float(profile_mean[profile])
            af[(plant, int(stage), int(block))] = max(0.0, min(1.0, value))

    return WindData(plants=plants, af=af)
