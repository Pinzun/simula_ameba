# hydro/io/hydronode_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Any
import math
import pandas as pd

from hydro.core.types import HydroNodeRow

# ------------------- Helpers -------------------
def _require_columns(df: pd.DataFrame, cols: List[str], tag: str) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"[{tag}] faltan columnas: {miss}. Presentes: {list(df.columns)}")

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
    return s in {"true", "1", "t", "yes", "y", "si", "sí"}

# ------------------- Loader -------------------
def load_hydronode(path: Path) -> List[HydroNodeRow]:
    """
    Lee HydroNode.csv y devuelve una lista de HydroNodeRow.

    Requeridas:
      name,start_time,end_time,report,formulate_bal

    Notas:
    - Admite múltiples filas por 'name' (vigencias distintas).
    - 'report' y 'formulate_bal' se parsean de forma tolerante (true/false, 1/0, sí/no).
    """
    tag = "HydroNode"
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    _require_columns(df, ["name", "start_time", "end_time", "report", "formulate_bal"], tag)

    # Parseo estricto de fechas y booleanos
    df["start_time"]   = df["start_time"].map(lambda s: _to_dt_strict(s, tag, "start_time"))
    df["end_time"]     = df["end_time"].map(lambda s: _to_dt_strict(s, tag, "end_time"))
    df["report"]       = df["report"].map(lambda x: _to_bool(x, True))
    df["formulate_bal"] = df["formulate_bal"].map(lambda x: _to_bool(x, False))

    # Validaciones básicas
    if (df["end_time"] <= df["start_time"]).any():
        bad = df.loc[df["end_time"] <= df["start_time"], "name"].tolist()
        raise ValueError(f"[{tag}] end_time <= start_time en nodos: {bad}")

    out: List[HydroNodeRow] = []
    for _, r in df.iterrows():
        out.append(HydroNodeRow(
            name=str(r["name"]),
            start_time=r["start_time"].to_pydatetime(),
            end_time=r["end_time"].to_pydatetime(),
            report=bool(r["report"]),
            formulate_bal=bool(r["formulate_bal"]),
        ))
    return out