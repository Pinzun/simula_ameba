# hydro/core/types.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Tipos numéricos semánticos
MW   = float
MWh  = float
Hm3  = float
Hmh  = float
Frac = float

# =========================
# Calendario (minimalista)
# =========================
# (stage, block)
TimeIndex = Tuple[int, int]

@dataclass(frozen=True)
class CalendarKeys:
    """
    Vista mínima del calendario para Hydro.
    - stages: IDs de stage ordenados (p.ej., [1,2,3,...]).
    - blocks: IDs de block ordenados (p.ej., [1,2,...,24]).
    Hydro NO asume duración aquí; la agregación por bloque
    ya debe haber ocurrido en el módulo de IO/aggregate.
    """
    stages: List[int]
    blocks: List[int]

# =========================
# Catálogo de enums
# =========================
class NodeKind(str, Enum):
    RESERVOIR = "RESERVOIR"
    INFLOW    = "INFLOW"
    HG        = "HG"
    BALANCE   = "BALANCE"
    SINK      = "SINK"
    OTHER     = "OTHER"

class ArcKind(str, Enum):
    TURBINE   = "turb"
    SPILL     = "spill"
    NATURAL   = "nat"
    PUMP      = "pump"
    OTHER     = "other"

# =========================
# Filas "crudas" (IO)
# =========================
@dataclass(frozen=True)
class DamRow:
    name: str
    start_time: datetime
    end_time: datetime
    report: bool
    vmax: Hm3
    vmin: Hm3
    vini: Hm3
    vend: Hm3
    scale: Frac
    non_physical_inflow: bool
    non_physical_inflow_penalty: float
    cond_ovf: bool
    vol_ovf: Hm3
    val_ovf: float

@dataclass(frozen=True)
class HydroNodeRow:
    name: str
    start_time: datetime
    end_time: datetime
    report: bool
    formulate_bal: bool

@dataclass(frozen=True)
class HydroConnectionRow:
    name: str
    start_time: datetime
    end_time: datetime
    report: bool
    h_type: str
    ini: str
    end: str
    h_max_flow: Optional[Hm3]
    h_min_flow: Optional[Hm3]
    h_ramp: Optional[Hm3]
    h_delay: Optional[int]
    h_delayed_q: Optional[Frac]
    h_flow_penalty: Optional[float]

@dataclass(frozen=True)
class HydroGeneratorRow:
    name: str
    start_time: datetime
    end_time: datetime
    report: bool
    connected: bool
    busbar: Optional[str]
    hydro_group_name: Optional[str]
    use_pump_mode: bool
    pmax: MW
    pmin: MW
    pmax_pump: MW
    pmin_pump: MW
    eff: Frac
    vomc_avg: float

@dataclass(frozen=True)
class HydroGroupRow:
    name: str
    start_time: datetime
    end_time: datetime
    report: bool
    hg_sp_min: MW
    hg_sp_max: MW

@dataclass(frozen=True)
class InflowRow:
    name: str
    start_time: datetime
    end_time: datetime
    report: bool
    inflows_qm3: float
    plp_indep_hydro: bool

@dataclass(frozen=True)
class IrrigationRow:
    name: str
    start_time: datetime
    end_time: datetime
    report: bool
    irrigations_qm3: float
    voli: float

# =========================
# Series base (por hora)
# =========================
@dataclass
class InflowSeries:
    name: str                # Afl_* o nodo
    times: List[datetime]    # timestamps horarios
    flow_hm3_per_hour: List[Hm3]

# =========================
# Agregados por bloque (y,t)
# =========================
@dataclass
class BlockAggregates:
    # Aportes naturales ya agregados a bloque (Hmh = Hm3 por hora * horas del bloque).
    I_nat_reservoir: Dict[Tuple[str, TimeIndex], Hmh] = field(default_factory=dict)
    I_nat_hg:        Dict[Tuple[str, TimeIndex], Hmh] = field(default_factory=dict)
    I_irrigation:    Dict[Tuple[str, TimeIndex], Hmh] = field(default_factory=dict)

# =========================
# Catálogos y grafo
# =========================
@dataclass
class ReservoirCatalog:
    names: List[str]
    vmax: Dict[str, Hm3]
    vmin: Dict[str, Hm3]
    vini: Dict[str, Hm3]
    vend: Dict[str, Hm3]
    kappa: Dict[str, float]
    scale: Dict[str, Frac]
    val_ovf: Dict[str, float]
    allow_non_physical: Dict[str, bool]
    penalty_non_physical: Dict[str, float]

@dataclass
class HydroGroupsLimits:
    sp_min: Dict[str, MW]
    sp_max: Dict[str, MW]

@dataclass
class GeneratorsCatalog:
    HG_all: List[str]
    PmaxHG: Dict[str, MW]
    PminHG: Dict[str, MW]
    kappa_hg: Dict[str, float]
    ROR: List[str]

@dataclass
class HydroGraph:
    arcs_spill_res:   List[Tuple[str, str]]
    arcs_turb_res:    List[Tuple[str, str]]
    arcs_spill_to_hg: List[Tuple[str, str]]
    arcs_turb_to_hg:  List[Tuple[str, str]]
    arcs_natural:     List[Tuple[str, str]]
    # con delay (para futuras extensiones)
    arcs_spill_res_d:   List[Tuple[str, str]] = field(default_factory=list)
    arcs_turb_res_d:    List[Tuple[str, str]] = field(default_factory=list)
    arcs_spill_to_hg_d: List[Tuple[str, str]] = field(default_factory=list)
    arcs_turb_to_hg_d:  List[Tuple[str, str]] = field(default_factory=list)

# =========================
# Paquete final para el modelo
# =========================
@dataclass
class HydroData:
    """
    Contrato de salida del módulo Hydro hacia el modelador.
    Se desacopla del calendario antiguo; usa CalendarKeys.
    """
    calendar: CalendarKeys                 # ← lista ordenada de stages y blocks
    reservoirs: ReservoirCatalog
    generators: GeneratorsCatalog
    groups_limits: HydroGroupsLimits
    graph: HydroGraph
    agg: BlockAggregates
    inflow_to_reservoir: Dict[str, str]    # Afl_* → Emb_*
    inflow_to_hg:        Dict[str, str]    # Afl_* → HG_*
    balance_nodes: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)