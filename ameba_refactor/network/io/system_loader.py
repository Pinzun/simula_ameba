"""Carga de parámetros globales del sistema eléctrico."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from network.core.types import SystemRow


def load_system(path_csv: Path) -> SystemRow:
    """Lee ``path_csv`` y devuelve una instancia de :class:`SystemRow`."""

    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]
    row = df.iloc[0]

    return SystemRow(
        sbase=float(row["sbase"]),
        busbar_ref=str(row["busbar_ref"]),
        interest_rate=float(row.get("interest_rate", 0.0)),
    )
