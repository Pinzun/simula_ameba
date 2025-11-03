# hydro/io/dam_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Tuple, Dict, List
from datetime import datetime
import pandas as pd
import math

from hydro.core.types import DamRow, ReservoirCatalog

# ------------------- Helpers -------------------

def _to_dt(s: str) -> datetime:
    # Acepta 'YYYY-MM-DD-HH:MM' o variantes; deja NaT -> error más claro luego
    dt = pd.to_datetime(s, format="%Y-%m-%d-%H:%M", errors="coerce")
    if pd.isna(dt):
        raise ValueError(f"[Dam] fecha inválida: {s!r} (esperado '%Y-%m-%d-%H:%M')")
    # sin tz; el calendario global trabaja en epoch segundos
    return dt.to_pydatetime()

def _to_bool(x) -> bool:
    if isinstance(x, bool):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return False
    s = str(x).strip().lower()
    return s in {"true","1","t","yes","y","si","sí"}

def _to_float(x, default: float = 0.0) -> float:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return float(default)
        return float(x)
    except Exception:
        return float(default)

def _require_columns(df: pd.DataFrame, cols: List[str], tag: str) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"[{tag}] faltan columnas: {miss}. Presentes: {list(df.columns)}")

def _assert_unique(df: pd.DataFrame, col: str, tag: str) -> None:
    if df[col].duplicated().any():
        dups = df.loc[df[col].duplicated(), col].tolist()
        raise ValueError(f"[{tag}] nombres duplicados en '{col}': {sorted(set(dups))[:10]}")

# ------------------- Loader -------------------

def load_dam(path: Path, kappa_default: float = 1.0) -> Tuple[List[DamRow], ReservoirCatalog]:
    """
    Carga Dam.csv y construye:
      - Lista de DamRow (para trazabilidad)
      - ReservoirCatalog (para el modelador)
    Columnas requeridas:
      name,start_time,end_time,report,vmax,vmin,vini,vend,scale,non_physical_inflow,
      non_physical_inflow_penalty,val_ovf
    Opcionales:
      cond_ovf (bool, default True), vol_ovf (float, default 0.0)
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    need = [
        "name","start_time","end_time","report",
        "vmax","vmin","vini","vend","scale",
        "non_physical_inflow","non_physical_inflow_penalty",
        "val_ovf"
    ]
    _require_columns(df, need, "Dam")

    _assert_unique(df, "name", "Dam")

    # Normalizaciones de tipos
    df["start_time"] = df["start_time"].map(_to_dt)
    df["end_time"]   = df["end_time"].map(_to_dt)

    # Construcción de estructuras
    rows: List[DamRow] = []
    names: List[str] = []
    vmax: Dict[str, float] = {}
    vmin: Dict[str, float] = {}
    vini: Dict[str, float] = {}
    vend: Dict[str, float] = {}
    scale: Dict[str, float] = {}
    allow_np: Dict[str, bool] = {}
    pen_np: Dict[str, float] = {}
    val_ovf: Dict[str, float] = {}
    kappa: Dict[str, float] = {}

    for _, r in df.iterrows():
        name = str(r["name"])

        r_report  = _to_bool(r.get("report", True))
        r_vmax    = _to_float(r.get("vmax", 0.0))
        r_vmin    = _to_float(r.get("vmin", 0.0))
        r_vini    = _to_float(r.get("vini", 0.0))
        r_vend    = _to_float(r.get("vend", 0.0))
        r_scale   = _to_float(r.get("scale", 1.0), default=1.0)
        r_np      = _to_bool(r.get("non_physical_inflow", False))
        r_np_pen  = _to_float(r.get("non_physical_inflow_penalty", 0.0))
        r_condovf = _to_bool(r.get("cond_ovf", True))
        r_volovf  = _to_float(r.get("vol_ovf", 0.0))
        r_valovf  = _to_float(r.get("val_ovf", 0.0))

        rows.append(DamRow(
            name=name,
            start_time=r["start_time"],
            end_time=r["end_time"],
            report=r_report,
            vmax=r_vmax,
            vmin=r_vmin,
            vini=r_vini,
            vend=r_vend,
            scale=r_scale,
            non_physical_inflow=r_np,
            non_physical_inflow_penalty=r_np_pen,
            cond_ovf=r_condovf,
            vol_ovf=r_volovf,
            val_ovf=r_valovf,
        ))

        names.append(name)
        vmax[name] = r_vmax
        vmin[name] = r_vmin
        vini[name] = r_vini
        vend[name] = r_vend
        scale[name] = r_scale
        allow_np[name] = r_np
        pen_np[name] = r_np_pen
        val_ovf[name] = r_valovf
        kappa[name] = float(kappa_default)

    catalog = ReservoirCatalog(
        names=names,
        vmax=vmax, vmin=vmin, vini=vini, vend=vend,
        kappa=kappa, scale=scale, val_ovf=val_ovf,
        allow_non_physical=allow_np, penalty_non_physical=pen_np
    )
    return rows, catalog