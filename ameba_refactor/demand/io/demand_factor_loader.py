# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict
import pandas as pd
import numpy as np

def load_demand_factors(path_csv: Path) -> pd.DataFrame:
    """
    Devuelve un DataFrame con índice=Timestamp (columna time) y columnas Proj_* (float).
    Los valores usualmente son anualizados; si hay múltiples filas por año/mes, se respeta.
    """
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]
    df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%d-%H:%M", errors="coerce")
    df = df.sort_values("time").set_index("time")
    proj_cols = [c for c in df.columns if c.startswith("Proj_")]
    if not proj_cols:
        raise ValueError("No se encontraron columnas 'Proj_*' en Factor.csv")
    return df[proj_cols]

def factor_for(proj_df: pd.DataFrame, proj_key: str, ts: pd.Timestamp) -> float:
    """
    Busca el factor vigente para 'proj_key' en la fecha/hora 'ts'.
    Regla: 'forward-fill' del último valor conocido <= ts. Si no hay pasado, usa el primero.
    """
    if proj_key not in proj_df.columns:
        # fallback: 1.0 si no existe la columna
        return 1.0
    s = proj_df[proj_key]
    # si el índice no contiene ts exacto, tomamos el último <= ts
    ix = s.index.searchsorted(ts, side="right") - 1
    if ix < 0:
        return float(s.iloc[0])
    return float(s.iloc[ix])