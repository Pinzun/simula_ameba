# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class BusbarRow:
    name: str
    voltage: float | int
    voll: float | None = None  # costo de energía no suministrada (opcional)

@dataclass(frozen=True)
class BranchRow:
    name: str
    bus_i: str
    bus_j: str
    x: float                  # reactancia p.u. o equivalente
    fmax_ab: float            # límite MW i→j
    fmax_ba: float            # límite MW j→i (puede ser = fmax_ab)
    dc: bool = True           # usar modelo DC (tu archivo ya lo marca)
    losses: bool = False      # ignorado en DC puro

@dataclass(frozen=True)
class SystemRow:
    sbase: float
    busbar_ref: str
    interest_rate: float | None = None