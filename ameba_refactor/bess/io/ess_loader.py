# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import pandas as pd

@dataclass(frozen=True)
class ESSUnit:
    name: str
    busbar: str
    pmax_dis: float     # MW descarga (columna pmax)
    pmax_ch: float      # MW carga (columna ess_pmaxc)
    pmin_dis: float     # MW descarga mínima (pmin)
    pmin_ch: float      # MW carga mínima (ess_pminc)
    vomc: float         # $/MWh (aplicaremos al throughput o a la descarga, ver nota)
    auxserv: float      # fracción (0..1) reduce inyección neta al sistema
    e_ini: float        # MWh iniciales (ess_eini)
    e_max: float        # MWh máx. (ess_emax)
    e_min: float        # MWh mín. (ess_emin)
    eff_c: float        # eficiencia de carga (ess_effc; si no viene, usar ess_effn)
    eff_d: float        # eficiencia de descarga (ess_effd; si no viene, usar ess_effn)
    cycle_neutral: bool # ess_intrastage_balance (True → cierre de ciclo por etapa)

def _to_bool(x) -> bool:
    return str(x).strip().lower() in {"true","1","t","yes","y"}

def load_ess_assets(path_csv: Path) -> Dict[str, ESSUnit]:
    df = pd.read_csv(path_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    def gv(r, k, default=0.0):
        v = r.get(k, default)
        return float(v) if pd.notna(v) else float(default)

    units: Dict[str, ESSUnit] = {}
    for _, r in df.iterrows():
        name = str(r["name"])
        effn  = gv(r, "ess_effn", 1.0)
        effc  = gv(r, "ess_effc", effn)
        effd  = gv(r, "ess_effd", effn)
        units[name] = ESSUnit(
            name=name,
            busbar=str(r.get("busbar","")),
            pmax_dis=gv(r, "pmax", 0.0),
            pmax_ch=gv(r, "ess_pmaxc", 0.0),
            pmin_dis=gv(r, "pmin", 0.0),
            pmin_ch=gv(r, "ess_pminc", 0.0),
            vomc=gv(r, "vomc_avg", 0.0),
            auxserv=gv(r, "auxserv", 0.0),
            e_ini=gv(r, "ess_eini", 0.0),
            e_max=gv(r, "ess_emax", 0.0),
            e_min=gv(r, "ess_emin", 0.0),
            eff_c=effc,
            eff_d=effd,
            cycle_neutral=_to_bool(r.get("ess_intrastage_balance", False)),
        )
    return units