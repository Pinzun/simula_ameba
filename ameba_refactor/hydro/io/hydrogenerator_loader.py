# hydro/io/hydrogenerator_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import pandas as pd
from datetime import datetime

from hydro.core.types import HydroGeneratorRow, GeneratorsCatalog

# --- helpers de tiempo (sin límite 2262) ---
def _to_dt_strict_py(s: Optional[str], tag: str, col: str) -> datetime:
    """
    Parse estricto con datetime.strptime (soporta año > 2262).
    Espera '%Y-%m-%d-%H:%M'. Lanza ValueError si viene vacío/None o formato inválido.
    """
    if s is None or (isinstance(s, float) and pd.isna(s)):
        raise ValueError(f"[{tag}] {col} vacío")
    s = str(s).strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d-%H:%M")
    except Exception:
        raise ValueError(f"[{tag}] {col} inválido: {s!r} (esperado '%Y-%m-%d-%H:%M')")

def load_hydrogenerator(path: Path, r_names: List[str], ror_prefix: str = "HG_") -> Tuple[List[HydroGeneratorRow], GeneratorsCatalog]:
    tag = "HydroGenerator"
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    need = ["name","start_time","end_time","report","connected","hydro_group_name","pmax","pmin","eff","vomc_avg"]
    for c in need:
        if c not in df.columns:
            raise ValueError(f"[{tag}] falta columna: {c}")

    # ✅ usar datetime.strptime para soportar 3000-01-01-00:00
    df["start_time"] = df["start_time"].map(lambda s: _to_dt_strict_py(s, tag, "start_time"))
    df["end_time"]   = df["end_time"].map(lambda s: _to_dt_strict_py(s, tag, "end_time"))

    rows: List[HydroGeneratorRow] = []
    HG_all: List[str] = []
    PmaxHG: Dict[str, float] = {}
    PminHG: Dict[str, float] = {}
    kappa_hg: Dict[str, float] = {}
    ROR: List[str] = []

    for _, r in df.iterrows():
        rows.append(HydroGeneratorRow(
            name=str(r["name"]),
            start_time=r["start_time"],
            end_time=r["end_time"],
            report=bool(r["report"]),
            connected=bool(r["connected"]),
            busbar=str(r["busbar"]) if "busbar" in df.columns else None,
            hydro_group_name=str(r["hydro_group_name"]) if pd.notna(r["hydro_group_name"]) else None,
            use_pump_mode=bool(r.get("use_pump_mode", False)),
            pmax=float(r.get("pmax", 0.0)),
            pmin=float(r.get("pmin", 0.0)),
            pmax_pump=float(r.get("pmax_pump", 0.0)) if "pmax_pump" in df.columns else 0.0,
            pmin_pump=float(r.get("pmin_pump", 0.0)) if "pmin_pump" in df.columns else 0.0,
            eff=float(r.get("eff", 1.0)),
            vomc_avg=float(r.get("vomc_avg", 0.0))
        ))

        hg = str(r["hydro_group_name"]) if pd.notna(r["hydro_group_name"]) else None
        if not hg:
            continue
        HG_all.append(hg)
        PmaxHG[hg] = float(r.get("pmax", 0.0))
        PminHG[hg] = float(r.get("pmin", 0.0))
        kappa_hg[hg] = float(r.get("eff", 1.0))

        if hg.startswith(ror_prefix):
            ROR.append(hg)

    HG_all = sorted(set(HG_all))
    ROR = sorted(set(ROR))

    cat = GeneratorsCatalog(
        HG_all=HG_all,
        PmaxHG=PmaxHG,
        PminHG=PminHG,
        kappa_hg=kappa_hg,
        ROR=ROR
    )
    return rows, cat