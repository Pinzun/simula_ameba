"""Lectura del catálogo de barras eléctricas con comentarios detallados."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from network.core.types import BusbarRow


# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

def load_busbars(path_csv: Path) -> pd.DataFrame:
    """
    Carga el CSV de barras eléctricas y devuelve un DataFrame con columnas
    normalizadas: ['name', 'voltage', 'voll'].
    """
    df = pd.read_csv(path_csv)
    df.columns = [c.strip().lower() for c in df.columns]  # normaliza headers a minúsculas

    # Renombra columnas si es necesario (por ejemplo, 'prices' -> 'voll')
    if "prices" in df.columns and "voll" not in df.columns:
        df = df.rename(columns={"prices": "voll"})

    # Asegura las columnas requeridas
    need = {"name", "voltage", "voll"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"[load_busbars] faltan columnas requeridas: {missing}")

    # Tipos de datos
    df["name"] = df["name"].astype(str).str.strip()
    df["voltage"] = pd.to_numeric(df["voltage"], errors="coerce")
    df["voll"] = pd.to_numeric(df["voll"], errors="coerce")

    return df[["name", "voltage", "voll"]].copy()

