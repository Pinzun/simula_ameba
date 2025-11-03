# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd

# Si quieres: from profiles.io import ProfilePowerStore
# y from core import ModelCalendar para tipar, pero no es necesario.

@dataclass(frozen=True)
class WindPlant:
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
    plants: Dict[str, WindPlant]          # {plant -> WindPlant}
    af: Dict[Tuple[str, int, int], float] # {(plant, y, t) -> AF in [0,1]}

def load_wind_generators(path_wind_csv: Path, pstore, calendar) -> WindData:
    """
    Lee WindGenerator.csv, construye catálogo de plantas e interpola/agrupa
    los perfiles de potencia (AF) de pstore por bloque (stage, block) del calendar.
    Devuelve WindData(plants, af) con AF promedio por bloque.
    """
    df = pd.read_csv(path_wind_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    def _num(s, default=0.0):
        try:
            return float(s)
        except Exception:
            return float(default)

    def _bool(x) -> bool:
        return str(x).strip().lower() in {"true","1","yes","y","t"}

    # --- 1) Catálogo de plantas
    plants: Dict[str, WindPlant] = {}
    plant_to_profile: Dict[str, str] = {}

    for _, r in df.iterrows():
        name = str(r["name"])
        profile = str(r.get("zone", r.get("profile", "")))  # en tus CSV viene 'zone' con Profile_*
        plants[name] = WindPlant(
            name=name,
            busbar=str(r.get("busbar", "")),
            profile=profile,
            pmax=_num(r.get("pmax", 0.0)),
            pmin=_num(r.get("pmin", 0.0)),
            vomc=_num(r.get("vomc_avg", 0.0)),
            inv_cost=_num(r.get("gen_inv_cost", 0.0)),
            candidate=_bool(r.get("candidate", False)),
        )
        plant_to_profile[name] = profile

    # --- 2) Detalle horario del calendario
    blocks_detail = calendar.blocks_assignments_df[["stage", "block", "time"]].copy()
    # Asegura dtype de tiempo compatible con el índice de pstore
    blocks_detail["time"] = pd.to_datetime(blocks_detail["time"], format="%Y-%m-%d-%H:%M", errors="raise")

    # --- 3) Columnas de perfiles realmente usados y presentes en pstore
    used_profiles = sorted(set(plant_to_profile.values()))
    available_profiles = [p for p in used_profiles if p in pstore.power_wide.columns]
    if not available_profiles:
        # No hay perfiles disponibles: devuelve AF=0 en todos (opción conservadora)
        return WindData(plants=plants, af={})

    # --- 4) Promedio por bloque (y,t)
    af: Dict[Tuple[str, int, int], float] = {}
    grp = blocks_detail.groupby(["stage", "block"], sort=False)

    for (y, t), chunk in grp:
        ts = chunk["time"]
        if ts.empty:
            continue

        # Reindexa serie horaria al conjunto de horas del bloque
        sub = pstore.power_wide.reindex(ts)  # index=time
        if sub is None or sub.empty:
            continue

        # Toma solo los perfiles necesarios y fuerza a numérico columna a columna
        sub = sub[available_profiles].apply(pd.to_numeric, errors="coerce").fillna(0.0)

        # Promedio por perfil dentro del bloque
        prof_mean = sub.mean(axis=0).to_dict()  # {profile -> af_promedio}

        # Escribir AF por planta, acotado a [0,1]
        for plant, prof in plant_to_profile.items():
            if prof not in prof_mean:
                continue
            val = float(prof_mean[prof])
            af[(plant, int(y), int(t))] = max(0.0, min(1.0, val))

    return WindData(plants=plants, af=af)