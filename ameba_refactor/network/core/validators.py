# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict
from network.core.types import BusbarRow, BranchRow, SystemRow

def validate_network(busbars: Dict[str, BusbarRow],
                     branches: Dict[str, BranchRow],
                     system: SystemRow) -> None:
    # 1) barra de referencia existe
    if system.busbar_ref not in busbars:
        raise ValueError(f"Busbar de referencia '{system.busbar_ref}' no existe.")

    # 2) ramas: buses y parámetros
    for br in branches.values():
        if br.bus_i not in busbars:
            raise ValueError(f"{br.name}: bus_i '{br.bus_i}' no existe.")
        if br.bus_j not in busbars:
            raise ValueError(f"{br.name}: bus_j '{br.bus_j}' no existe.")
        if br.x is None or br.x == 0:
            raise ValueError(f"{br.name}: reactancia x debe ser != 0 para DC.")
        if br.fmax_ab < 0 or br.fmax_ba < 0:
            raise ValueError(f"{br.name}: límites de flujo no pueden ser negativos.")