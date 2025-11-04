"""Lectura detallada del catálogo de líneas eléctricas."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from network.core.types import BranchRow


def load_branches(path_csv: Path) -> Dict[str, BranchRow]:
    """Carga ``BranchRow`` desde ``path_csv`` aplicando filtros y conversiones.

    El archivo de entrada puede contener columnas auxiliares; aquí se
    normalizan los nombres, se ignoran las líneas desconectadas y se
    construyen dataclasses listos para usarse dentro del modelo eléctrico.
    """

    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]

    out: Dict[str, BranchRow] = {}
    for _, row in df.iterrows():
        if not bool(row.get("connected", True)):
            # Se omiten las líneas marcadas como desconectadas en el catálogo.
            continue

        name = str(row["name"])
        bus_i = str(row["busbari"])
        bus_j = str(row["busbarf"])
        reactance = float(row["x"])
        fmax_ab = float(row.get("max_flow", 0.0))
        fmax_ba = float(row.get("max_flow_reverse", fmax_ab))
        dc = bool(row.get("dc", True))
        losses = bool(row.get("losses", False))

        out[name] = BranchRow(
            name=name,
            bus_i=bus_i,
            bus_j=bus_j,
            x=reactance,
            fmax_ab=fmax_ab,
            fmax_ba=fmax_ba,
            dc=dc,
            losses=losses,
        )

    return out
