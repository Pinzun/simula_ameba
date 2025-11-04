# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict
from network.core.types import BusbarRow, BranchRow, SystemRow
import pandas as pd

import pandas as pd

def validate_network(busbars, branches, system) -> None:
    """
    KISS: Valida red aceptando entradas en DF o en objetos/dict sencillos.
    - busbars: DataFrame con columna 'name' o dict {bus_name: BusbarRow}
    - branches: DataFrame con ['name','bus_i','bus_j','x','fmax_ab','fmax_ba']
                o dict {branch_name: BranchRow}
    - system: DataFrame con 'busbar_ref' (se toma la primera fila)
              o objeto con atributo .busbar_ref
    """

    # --- bus_ref (desde system) ---
    if isinstance(system, pd.DataFrame):
        bus_ref = str(system.iloc[0]["busbar_ref"])
    else:
        # p.ej. SystemRow con atributo
        bus_ref = str(getattr(system, "busbar_ref"))

    # --- conjunto de buses ---
    if isinstance(busbars, pd.DataFrame):
        bus_set = set(busbars["name"].astype(str))
    else:
        # dict {name: BusbarRow}
        bus_set = set(map(str, busbars.keys()))

    # 1) barra de referencia
    if bus_ref not in bus_set:
        raise ValueError(f"[network] Busbar de referencia '{bus_ref}' no existe.")

    # --- iterador de ramas (uniforme) ---
    def _iter_branches(br):
        if isinstance(br, pd.DataFrame):
            for _, r in br.iterrows():
                yield (
                    str(r["name"]),
                    str(r["bus_i"]),
                    str(r["bus_j"]),
                    float(r["x"]),
                    float(r["fmax_ab"]),
                    float(r["fmax_ba"]),
                )
        else:
            # dict {name: BranchRow}
            for name, obj in br.items():
                yield (
                    str(name),
                    str(getattr(obj, "bus_i")),
                    str(getattr(obj, "bus_j")),
                    float(getattr(obj, "x")),
                    float(getattr(obj, "fmax_ab")),
                    float(getattr(obj, "fmax_ba")),
                )

    # 2) validaciones de ramas
    for name, bus_i, bus_j, x, fmax_ab, fmax_ba in _iter_branches(branches):
        if bus_i not in bus_set:
            raise ValueError(f"[network] {name}: bus_i '{bus_i}' no existe.")
        if bus_j not in bus_set:
            raise ValueError(f"[network] {name}: bus_j '{bus_j}' no existe.")
        if x == 0 or pd.isna(x):
            raise ValueError(f"[network] {name}: reactancia x debe ser != 0.")
        if fmax_ab < 0 or fmax_ba < 0:
            raise ValueError(f"[network] {name}: límites de flujo no pueden ser negativos.")
