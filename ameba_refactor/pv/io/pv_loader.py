# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import pandas as pd

@dataclass(frozen=True)
class PVPlant:
    name: str
    busbar: str
    profile: str
    pmax: float
    pmin: float
    vomc: float
    inv_cost: float
    candidate: bool

@dataclass
class PVData:
    plants: Dict[str, PVPlant]                 # {plant -> PVPlant}
    af: Dict[tuple, float]                     # {(plant,y,t) -> AF in [0,1]}

def load_pv_generators(path_pv_csv: Path) -> Dict[str, PVPlant]:
    df = pd.read_csv(path_pv_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    def _num(s, default=0.0):
        try:
            return float(s)
        except Exception:
            return float(default)

    def _bool(x) -> bool:
        return str(x).strip().lower() in {"true","1","yes","y","t"}

    plants: Dict[str, PVPlant] = {}
    for _, r in df.iterrows():
        name = str(r["name"])
        plants[name] = PVPlant(
            name=name,
            busbar=str(r.get("busbar","")),
            profile=str(r.get("zone","")),            # <- en tu CSV, el perfil viene en 'zone' (p.ej. Profile_PV_Kimal220)
            pmax=_num(r.get("pmax",0.0)),
            pmin=_num(r.get("pmin",0.0)),
            vomc=_num(r.get("vomc_avg", 0.0)),
            inv_cost=_num(r.get("gen_inv_cost",0.0)),
            candidate=_bool(r.get("candidate", False)),
        )
    return plants