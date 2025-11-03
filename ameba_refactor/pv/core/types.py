# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

Stage = int
Block = int
Plant = str
Busbar = str
Profile = str

@dataclass
class PvRecord:
    name: Plant
    busbar: Busbar
    profile: Profile          # p.ej. 'Profile_LuzdelNorte'
    pmax: float               # MW (capacidad nominal)
    pmin: float               # MW (normalmente 0 para PV)
    vomc: float               # $/MWh (suele ser ~0, pero traemos del CSV)
    fom: float                # $/MW-año (si luego lo usas en objetivo)
    is_ncre: bool
    connected: bool
    candidate: bool
    inv_cost: float           # $/MW
    lifetime: int             # años
    forced_outage_rate: float # opcional (si después usas disponibilidad efectiva)
    voltage: Optional[float] = None

@dataclass
class PvData:
    plants: Dict[Plant, PvRecord]
    # Factor de disponibilidad por bloque (0..1) ya promediado con el perfil horario:
    af: Dict[Tuple[Plant, Stage, Block], float]