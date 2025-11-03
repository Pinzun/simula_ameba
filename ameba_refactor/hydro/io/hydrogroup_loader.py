# hydro/io/hydrogroup_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Dict, Any
import pandas as pd
import math

from hydro.core.types import HydroGroupRow, HydroGroupsLimits

# ------------------- Helpers -------------------
def _require_columns(df: pd.DataFrame, cols: List[str], tag: str) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"[{tag}] faltan columnas: {miss}. Presentes: {list(df.columns)}")

def _assert_unique(df: pd.DataFrame, col: str, tag: str) -> None:
    if df[col].duplicated().any():
        dups = df.loc[df[col].duplicated(), col].tolist()
        raise ValueError(f"[{tag}] valores duplicados en '{col}': {sorted(set(dups))[:10]}")

def _to_dt_strict(s: Any, tag: str, col: str) -> pd.Timestamp:
    dt = pd.to_datetime(s, format="%Y-%m-%d-%H:%M", errors="coerce")
    if pd.isna(dt):
        raise ValueError(f"[{tag}] {col} inválido: {s!r} (esperado '%Y-%m-%d-%H:%M')")
    return dt

def _to_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    s = str(x).strip().lower()
    return s in {"true","1","t","yes","y","si","sí"}

def _to_float(x: Any, default: float = 0.0) -> float:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    try:
        return float(x)
    except Exception:
        return default

# ------------------- Loader -------------------
def load_hydrogroup(path: Path) -> Tuple[List[HydroGroupRow], HydroGroupsLimits]:
    """
    Lee HydroGroup.csv y devuelve:
      - Lista de HydroGroupRow (uno por fila)
      - HydroGroupsLimits (sp_min/sp_max por grupo)

    Requeridas:
      name,start_time,end_time,report,hg_sp_min,hg_sp_max
      (si hg_sp_max viene vacío, se interpreta como +inf)
    """
    tag = "HydroGroup"
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    _require_columns(df, ["name","start_time","end_time","report","hg_sp_min","hg_sp_max"], tag)
    _assert_unique(df, "name", tag)  # KISS: 1 fila por grupo (si necesitas múltiples vigencias, lo cambiamos)

    # Parseo estricto
    df["start_time"] = df["start_time"].map(lambda s: _to_dt_strict(s, tag, "start_time"))
    df["end_time"]   = df["end_time"].map(lambda s: _to_dt_strict(s, tag, "end_time"))
    df["report"]     = df["report"].map(lambda x: _to_bool(x, True))

    # Números (permitir vacío en max como +inf)
    df["hg_sp_min"] = df["hg_sp_min"].map(lambda x: _to_float(x, 0.0))
    df["hg_sp_max"] = df["hg_sp_max"].map(
        lambda x: float("inf") if (x is None or (isinstance(x, float) and math.isnan(x))) else _to_float(x, float("inf"))
    )

    # Validaciones básicas
    if (df["end_time"] <= df["start_time"]).any():
        bad = df.loc[df["end_time"] <= df["start_time"], "name"].tolist()
        raise ValueError(f"[{tag}] end_time <= start_time en grupos: {bad}")

    if (df["hg_sp_min"] < 0).any():
        bad = df.loc[df["hg_sp_min"] < 0, "name"].tolist()
        raise ValueError(f"[{tag}] hg_sp_min no puede ser negativo: {bad}")

    # Si hay max finito, exigir min <= max
    mask_finite = df["hg_sp_max"].apply(lambda v: math.isfinite(v))
    bad_mm = df.loc[mask_finite & (df["hg_sp_min"] > df["hg_sp_max"]), "name"].tolist()
    if bad_mm:
        raise ValueError(f"[{tag}] hg_sp_min > hg_sp_max en: {bad_mm}")

    # Salidas
    rows: List[HydroGroupRow] = []
    sp_min: Dict[str, float] = {}
    sp_max: Dict[str, float] = {}

    for _, r in df.iterrows():
        name = str(r["name"])
        rows.append(HydroGroupRow(
            name=name,
            start_time=r["start_time"].to_pydatetime(),
            end_time=r["end_time"].to_pydatetime(),
            report=bool(r["report"]),
            hg_sp_min=float(r["hg_sp_min"]),
            hg_sp_max=float(r["hg_sp_max"]),
        ))
        sp_min[name] = float(r["hg_sp_min"])
        sp_max[name] = float(r["hg_sp_max"])

    limits = HydroGroupsLimits(sp_min=sp_min, sp_max=sp_max)
    return rows, limits