# hydro/io/hydroconn_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Any, Optional
import pandas as pd
import math

from hydro.core.types import HydroConnectionRow

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

def _to_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    try:
        return float(x)
    except Exception:
        return default

def _to_int(x: Any, default: Optional[int] = None) -> Optional[int]:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    try:
        return int(x)
    except Exception:
        return default

# ------------------- Loader -------------------

def load_hydroconnection(path: Path) -> List[HydroConnectionRow]:
    """
    Lee HydroConnection.csv y devuelve una lista de HydroConnectionRow.

    Requeridas:
      name,start_time,end_time,report,h_type,ini,end

    Opcionales:
      h_max_flow,h_min_flow,h_ramp,h_delay,h_delayed_q,h_flow_penalty
    """
    tag = "HydroConnection"
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    _require_columns(df, ["name","start_time","end_time","report","h_type","ini","end"], tag)
    _assert_unique(df, "name", tag)

    # Normalizaciones de tipos
    df["start_time"] = df["start_time"].map(lambda s: _to_dt_strict(s, tag, "start_time"))
    df["end_time"]   = df["end_time"].map(lambda s: _to_dt_strict(s, tag, "end_time"))

    out: List[HydroConnectionRow] = []
    for _, r in df.iterrows():
        # Mantén h_type original (para trazabilidad), pero normaliza para uso
        h_type_raw = str(r["h_type"])
        h_type_norm = h_type_raw.strip().lower()

        out.append(HydroConnectionRow(
            name=str(r["name"]),
            start_time=r["start_time"].to_pydatetime(),
            end_time=r["end_time"].to_pydatetime(),
            report=_to_bool(r.get("report", True), default=True),
            h_type=h_type_norm,
            ini=str(r["ini"]).strip(),
            end=str(r["end"]).strip(),
            h_max_flow=_to_float(r.get("h_max_flow"), default=None),
            h_min_flow=_to_float(r.get("h_min_flow"), default=None),
            h_ramp=_to_float(r.get("h_ramp"), default=None),
            h_delay=_to_int(r.get("h_delay"), default=None),
            h_delayed_q=_to_float(r.get("h_delayed_q"), default=None),
            h_flow_penalty=_to_float(r.get("h_flow_penalty"), default=None),
        ))

    return out