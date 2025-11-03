# pv/io/pv_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd

# deps del proyecto
from profiles.io import ProfilePowerStore
from core.calendar import ModelCalendar  # ajusta el import si tu módulo se llama distinto

@dataclass(frozen=True)
class PVPlant:
    name: str
    busbar: str
    profile: str           # nombre del perfil (ej. Profile_PV_Kimal220)
    pmax: float
    pmin: float
    vomc: float
    inv_cost: float
    candidate: bool

@dataclass
class PVData:
    plants: Dict[str, PVPlant]                 # {plant -> PVPlant}
    af: Dict[Tuple[str, int, int], float]      # {(plant,y,t) -> AF in [0,1]}

def _num(s, default=0.0) -> float:
    try:
        return float(s)
    except Exception:
        return float(default)

def _bool(x) -> bool:
    return str(x).strip().lower() in {"true","1","yes","y","t"}

def load_pv_generators(path_pv_csv: Path,
                       pstore: ProfilePowerStore,
                       calendar: ModelCalendar) -> PVData:
    """
    Lee el CSV de PV y devuelve:
      - catálogo de plantas (PVPlant)
      - AF promedio por bloque {(plant, y, t) -> af}, usando el perfil (columna 'zone')
        y el mapeo horario del calendario (blocks_assignments_df).
    Requisitos:
      - CSV debe tener columnas: name,busbar,pmax,pmin,vomc_avg,gen_inv_cost,candidate,zone
      - pstore.power_wide: index=time (Timestamp), cols=profiles
      - calendar.blocks_assignments_df: columnas = stage,block,time (strings con formato '%Y-%m-%d-%H:%M')
    """
    df = pd.read_csv(path_pv_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    need = {"name","busbar","zone","pmax"}
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise AssertionError(f"[PvGenerator] faltan columnas: {miss}")

    # --- 1) Catálogo de plantas
    plants: Dict[str, PVPlant] = {}
    plant_to_profile: Dict[str, str] = {}
    for _, r in df.iterrows():
        name = str(r["name"])
        prof = str(r.get("zone","")).strip()  # en tus CSV el perfil viene en 'zone'
        plants[name] = PVPlant(
            name=name,
            busbar=str(r.get("busbar","")),
            profile=prof,
            pmax=_num(r.get("pmax",0.0)),
            pmin=_num(r.get("pmin",0.0)),
            vomc=_num(r.get("vomc_avg", 0.0)),
            inv_cost=_num(r.get("gen_inv_cost",0.0)),
            candidate=_bool(r.get("candidate", False)),
        )
        if prof:
            plant_to_profile[name] = prof

    # --- 2) AF promedio por bloque usando pstore + calendario
    # usamos el detalle horario del calendario (asignación de horas a bloques)
    # y promediamos los valores de perfil dentro de cada (stage, block)
    # Nota: ProfilePowerStore ya tiene la matriz power_wide (time x profile)
    # y un método de ayuda para promediar por bloque.
    # Si tu ProfilePowerStore tiene un método distinto, ajusta aquí.
    blocks_detail = calendar.blocks_assignments_df.copy()
    # Aseguramos tipo de tiempo y formato consistente con pstore.power_wide.index
    blocks_detail["time"] = pd.to_datetime(blocks_detail["time"], format="%Y-%m-%d-%H:%M")

    # Reindex seguro para cada profile dentro de cada bloque y promediar:
    af: Dict[Tuple[str, int, int], float] = {}

    # agrupamos por (stage, block) y para cada planta tomamos el promedio del perfil en esas horas
# ... arriba igual

    grp = blocks_detail.groupby(["stage", "block"], sort=False)
    for (y, t), chunk in grp:
        ts = chunk["time"]

        needed_profiles = [p for p in set(plant_to_profile.values()) if p in pstore.power_wide.columns]
        if not needed_profiles:
            continue

        # Reindexa por las horas del bloque y selecciona solo los perfiles necesarios
        sub = pstore.power_wide.reindex(ts)  # index=time (Timestamp)
        if sub is None or sub.empty:
            continue
        sub = sub[needed_profiles] if needed_profiles else sub

        # 🔧 PARCHE: convertir cada columna a numérico (coerce → NaN → 0.0)
        sub = sub.apply(pd.to_numeric, errors="coerce").fillna(0.0)

        # Promedio por perfil dentro del bloque
        prof_mean = sub.mean(axis=0).to_dict()  # {profile -> af}

        # Escribir AF por planta, acotado a [0,1]
        for plant, prof in plant_to_profile.items():
            af_val = float(prof_mean.get(prof, 0.0))
            af[(plant, int(y), int(t))] = max(0.0, min(1.0, af_val))

    return PVData(plants=plants, af=af)