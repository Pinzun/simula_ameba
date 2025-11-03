# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd

def load_demand_series(path_csv: Path, scenario: str | None = None) -> pd.DataFrame:
    """
    Devuelve un DataFrame indexado por time (Timestamp), columnas = nombres L_* (Load.name).
    Si existe columna 'scenario', filtra por ella; si no, la ignora.
    """
    df = pd.read_csv(path_csv)
    # normaliza columnas
    df.columns = [c.strip() for c in df.columns]
    # si hay 'scenario', filtra (si no se especifica, toma la primera)
    if "scenario" in df.columns:
        if scenario is None:
            scenario = df["scenario"].iloc[0]
        df = df[df["scenario"] == scenario].copy()

    # parsea tiempo
    df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%d-%H:%M", errors="coerce")
    df = df.sort_values("time").set_index("time")

    # deja sólo columnas L_*
    load_cols = [c for c in df.columns if c.startswith("L_")]
    if not load_cols:
        raise ValueError("No se encontraron columnas de demanda tipo 'L_*' en Demand.csv")
    return df[load_cols]