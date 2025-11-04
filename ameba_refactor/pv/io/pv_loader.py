"""Cargador de generación fotovoltaica con documentación en español."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from profiles.io import ProfilePowerStore
from core.calendar import ModelCalendar


@dataclass(frozen=True)
class PVPlant:
    """Describe una planta fotovoltaica y su configuración básica."""

    name: str
    busbar: str
    profile: str  # Nombre del perfil horario (ej. ``Profile_PV_Kimal220``)
    pmax: float
    pmin: float
    vomc: float
    inv_cost: float
    candidate: bool


@dataclass
class PVData:
    """Resultado compuesto de :func:`load_pv_generators`."""

    plants: Dict[str, PVPlant]  # Catálogo de plantas por nombre
    af: Dict[Tuple[str, int, int], float]  # {(plant, stage, block) -> factor medio}


def _num(value, default: float = 0.0) -> float:
    """Convierte ``value`` a ``float`` y aplica ``default`` si falla."""

    try:
        return float(value)
    except Exception:
        return float(default)


def _bool(value) -> bool:
    """Normaliza valores de texto/numéricos a booleanos estándar."""

    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def load_pv_generators(
    path_pv_csv: Path,
    pstore: ProfilePowerStore,
    calendar: ModelCalendar,
) -> PVData:
    """Lee el catálogo de PV y calcula factores medios por bloque.

    Pasos detallados:
    1. Normalizar columnas del CSV y validar campos esenciales.
    2. Construir un diccionario ``PVPlant`` por cada fila.
    3. Tomar el detalle horario del calendario y promediar el perfil asociado
       a cada planta dentro de cada bloque (``stage``, ``block``).
    4. Retornar ``PVData`` con el catálogo y los factores medios en ``[0, 1]``.
    """

    df = pd.read_csv(path_pv_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"name", "busbar", "zone", "pmax"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise AssertionError(f"[PvGenerator] faltan columnas obligatorias: {missing}")

    plants: Dict[str, PVPlant] = {}
    plant_to_profile: Dict[str, str] = {}

    for _, row in df.iterrows():
        name = str(row["name"])
        profile = str(row.get("zone", "")).strip()

        plants[name] = PVPlant(
            name=name,
            busbar=str(row.get("busbar", "")),
            profile=profile,
            pmax=_num(row.get("pmax", 0.0)),
            pmin=_num(row.get("pmin", 0.0)),
            vomc=_num(row.get("vomc_avg", 0.0)),
            inv_cost=_num(row.get("gen_inv_cost", 0.0)),
            candidate=_bool(row.get("candidate", False)),
        )

        if profile:
            plant_to_profile[name] = profile

    # Detalle horario del calendario necesario para el promedio por bloque.
    blocks_detail = calendar.blocks_assignments_df.copy()
    blocks_detail["time"] = pd.to_datetime(blocks_detail["time"], format="%Y-%m-%d-%H:%M")

    af: Dict[Tuple[str, int, int], float] = {}
    used_profiles = {p for p in plant_to_profile.values() if p in pstore.power_wide.columns}

    for (stage, block), chunk in blocks_detail.groupby(["stage", "block"], sort=False):
        timestamps = chunk["time"]
        if timestamps.empty or not used_profiles:
            continue

        # Submatriz con las horas del bloque y solo los perfiles requeridos.
        sub = pstore.power_wide.reindex(timestamps)
        if sub is None or sub.empty:
            continue

        sub = sub[list(used_profiles)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        profile_mean = sub.mean(axis=0).to_dict()

        for plant, profile in plant_to_profile.items():
            if profile not in profile_mean:
                continue
            value = float(profile_mean[profile])
            af[(plant, int(stage), int(block))] = max(0.0, min(1.0, value))

    return PVData(plants=plants, af=af)
