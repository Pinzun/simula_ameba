# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union, Literal
import pandas as pd
import numpy as np

@dataclass(frozen=True)
class LoadRow:
    name: str            # "L_Cumbre500"
    busbar: str          # "Cumbre500"
    projection_key: str  # "Proj_Cumbre500"
    voll: float | None

def load_loads(
    path_csv: Path,
    return_type: Literal["dict", "dataframe"] = "dict",
) -> Union[Dict[str, LoadRow], pd.DataFrame]:
    """
    Lee el catálogo de cargas y devuelve:
      - return_type="dict":  {name -> LoadRow}
      - return_type="dataframe": DataFrame con columnas ['name','busbar','projection_key','voll']

    Mejoras:
      - Normaliza columnas (strip)
      - Filtra connected==True (si no existe, asume True)
      - Rellena projection_key si falta: Proj_<busbar>
      - VOLL a float o None
    """
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]

    # Normaliza campos esperados (tolerante a faltantes)
    name_col   = "name"
    bus_col    = "busbar"
    proj_col   = "projection_type" if "projection_type" in df.columns else "projection"
    conn_col   = "connected" if "connected" in df.columns else None
    voll_col   = "voll" if "voll" in df.columns else None

    need = {name_col, bus_col}
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise AssertionError(f"[load_loads] faltan columnas requeridas: {miss}")

    # connected → bool (default True si no existe)
    if conn_col is not None:
        conn = df[conn_col]
        if conn.dtype != bool:
            # coerciona: 1/0/True/False/"true"/"false"
            df[conn_col] = conn.map(
                lambda x: str(x).strip().lower() in {"1", "true", "t", "yes", "y"}
            )
        connected_mask = df[conn_col] == True
    else:
        connected_mask = pd.Series(True, index=df.index)

    df = df.loc[connected_mask].copy()

    # Limpiezas básicas
    df[name_col] = df[name_col].astype(str).str.strip()
    df[bus_col]  = df[bus_col].astype(str).str.strip()

    # projection_key
    if proj_col in df.columns:
        df[proj_col] = df[proj_col].astype(str).str.strip()
        # si la celda está vacía, usa fallback
        df["projection_key"] = np.where(
            (df[proj_col].isna()) | (df[proj_col] == ""),
            "Proj_" + df[bus_col],
            df[proj_col],
        )
    else:
        df["projection_key"] = "Proj_" + df[bus_col]

    # voll a float (o None)
    if voll_col is not None and voll_col in df.columns:
        def _to_voll(x):
            try:
                v = float(x)
                return v
            except Exception:
                return None
        df["voll"] = df[voll_col].apply(_to_voll)
    else:
        df["voll"] = None

    # Dedup por 'name' (conserva primera aparición)
    df = df.drop_duplicates(subset=[name_col], keep="first")

    # Salidas
    if return_type == "dataframe":
        return df[[name_col, bus_col, "projection_key", "voll"]].rename(
            columns={name_col: "name", bus_col: "busbar"}
        ).reset_index(drop=True)

    # return_type == "dict"
    out: Dict[str, LoadRow] = {}
    for _, r in df.iterrows():
        name = str(r["name"])
        bus  = str(r["busbar"])
        proj = str(r["projection_key"])
        voll = r["voll"]
        voll_f = float(voll) if (voll is not None and not pd.isna(voll)) else None
        out[name] = LoadRow(name, bus, proj, voll_f)
    return out
