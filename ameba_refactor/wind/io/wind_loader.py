# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import pandas as pd

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
    plants: Dict[str, WindPlant]                 # {plant -> WindPlant}
    af: Dict[tuple, float]                       # {(plant,y,t) -> AF in [0,1]}

def load_wind_generators(path_wind_csv: Path) -> Dict[str, WindPlant]:
    df = pd.read_csv(path_wind_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    def _num(s, default=0.0):
        try:
            return float(s)
        except Exception:
            return float(default)

    def _bool(x): return str(x).strip().lower() in {"true","1","yes","y","t"}

    plants: Dict[str, WindPlant] = {}
    for _, r in df.iterrows():
        name = str(r["name"])
        plants[name] = WindPlant(
            name=name,
            busbar=str(r.get("busbar","")),
            profile=str(r.get("zone","")),            # <- en tu CSV la columna es 'zone' con Profile_*
            pmax=_num(r.get("pmax",0.0)),
            pmin=_num(r.get("pmin",0.0)),
            vomc=_num(r.get("vomc_avg", 0.0)),
            inv_cost=_num(r.get("gen_inv_cost",0.0)),
            candidate=_bool(r.get("candidate", False)),
        )
    return plants