"""Lectura del catálogo de barras eléctricas con comentarios detallados."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from network.core.types import BusbarRow


def load_busbars(path_csv: Path) -> Dict[str, BusbarRow]:
    """Convierte el CSV de barras en un diccionario de :class:`BusbarRow`."""

    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]

    out: Dict[str, BusbarRow] = {}
    for _, row in df.iterrows():
        name = str(row["name"])
        voltage = float(row.get("voltage", 0.0))
        voll_value = row.get("prices", None)
        voll_float = float(voll_value) if pd.notna(voll_value) else None

        out[name] = BusbarRow(name=name, voltage=voltage, voll=voll_float)

    return out
