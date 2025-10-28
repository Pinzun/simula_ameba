# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path

def build_inflows_df(ruta_wide: Path, escenario: str = "H_1960", units: str = "m3s") -> pd.DataFrame:
    """
    Construye un DataFrame de inflows directamente desde un archivo ancho de afluencias.
    No guarda archivos, solo devuelve el DataFrame con columnas ['time','name','inflow'].
    """
    df = pd.read_csv(ruta_wide)
    df.columns = [c.strip() for c in df.columns]

    if "scenario" in df.columns:
        df = df[df["scenario"] == escenario].copy()

    exclude = {"time", "scenario"}
    afl_cols = [c for c in df.columns if c not in exclude]

    long_df = (
        df.melt(id_vars=["time"], value_vars=afl_cols,
                var_name="name", value_name="inflow_raw")
    )

    long_df["time"] = pd.to_datetime(long_df["time"], format="%Y-%m-%d-%H:%M")

    # Conversión de unidades
    if units.lower() == "m3s":
        long_df["inflow"] = long_df["inflow_raw"] * 0.0036  # m³/s → hm³/h
    else:
        long_df["inflow"] = long_df["inflow_raw"]

    out = long_df[["time", "name", "inflow"]].sort_values(["time", "name"]).reset_index(drop=True)
    out["time"] = out["time"].dt.strftime("%Y-%m-%d-%H:%M")

    return out