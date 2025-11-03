# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Iterable, Callable, Tuple
import pyomo.environ as pyo
from network.core.types import BusbarRow, BranchRow, SystemRow

GenExpr = Callable[[pyo.ConcreteModel, str, int, int], pyo.Expression]
# firma: (m, bus, y, t) -> Pyomo expression (MW). La sumamos en el balance.

def build_dc_network(
    busbars: Dict[str, BusbarRow],
    branches: Dict[str, BranchRow],
    system: SystemRow,
    time_index: Iterable[Tuple[int,int]],                    # iterable de (y,t)
    *,
    demand_by_bus_time: Dict[Tuple[int,int], Dict[str,float]] | None = None,
    gen_terms: Tuple[GenExpr, ...] = tuple(),
    include_shed: bool = True,
) -> pyo.ConcreteModel:
    """
    Crea un modelo DC base. No crea variables de generación; en su lugar
    espera una tupla de funciones 'gen_terms' que devuelven expresiones
    de inyección por (bus, y, t). Esto permite “enchufar” tus módulos de generación.
    """
    # --- Pyomo model
    m = pyo.ConcreteModel()

    # Sets
    m.B = pyo.Set(initialize=sorted(busbars.keys()))
    m.L = pyo.Set(initialize=sorted(branches.keys()))
    m.TY = pyo.Set(initialize=list(time_index), dimen=2)  # pares (y,t)

    # Parámetros de líneas
    m.bus_i = pyo.Param(m.L, initialize={k: branches[k].bus_i for k in branches})
    m.bus_j = pyo.Param(m.L, initialize={k: branches[k].bus_j for k in branches})
    m.x     = pyo.Param(m.L, initialize={k: branches[k].x for k in branches})
    m.fmax_ab = pyo.Param(m.L, initialize={k: branches[k].fmax_ab for k in branches})
    m.fmax_ba = pyo.Param(m.L, initialize={k: branches[k].fmax_ba for k in branches})

    # VOLL por barra (si None, usa un valor alto por defecto al usar shedding)
    DEFAULT_VOLL = 10000.0
    def _voll_init(b):
        v = busbars[b].voll
        return DEFAULT_VOLL if (v is None or v == 0) else float(v)
    m.VOLL = pyo.Param(m.B, initialize=_voll_init, mutable=True)

    # Demanda D[b,y,t] (MW). Si no se entrega, es 0.
    def _D_init(m, b, y, t):
        if demand_by_bus_time is None:
            return 0.0
        v = demand_by_bus_time.get((y, t), {}).get(b, 0.0)
        return float(v)
    m.D = pyo.Param(m.B, m.TY, initialize=_D_init, mutable=True)

    # Variables
    m.theta = pyo.Var(m.B, m.TY, bounds=(-3.1416, 3.1416))  # rad aprox; DC no lo usa estricto
    m.flow  = pyo.Var(m.L, m.TY)                            # MW

    if include_shed:
        m.shed = pyo.Var(m.B, m.TY, within=pyo.NonNegativeReals)  # MW
    else:
        m.shed = None

    # Flujo DC por línea
    def flow_rule(m, l, y, t):
        bi = m.bus_i[l]
        bj = m.bus_j[l]
        return m.flow[l, (y, t)] == (m.theta[bi, (y, t)] - m.theta[bj, (y, t)]) / m.x[l]
    m.FlowDef = pyo.Constraint(m.L, m.TY, rule=flow_rule)

    # Límites de flujo
    def fmax_up_rule(m, l, y, t):
        return m.flow[l, (y, t)] <= m.fmax_ab[l]
    def fmax_dn_rule(m, l, y, t):
        return m.flow[l, (y, t)] >= -m.fmax_ba[l]
    m.FlowUp = pyo.Constraint(m.L, m.TY, rule=fmax_up_rule)
    m.FlowDn = pyo.Constraint(m.L, m.TY, rule=fmax_dn_rule)

    # Ángulo de referencia
    ref = system.busbar_ref
    def ref_rule(m, y, t):
        return m.theta[ref, (y, t)] == 0.0
    m.RefAngle = pyo.Constraint(m.TY, rule=ref_rule)

    # Suma de inyecciones de generación (a través de callbacks)
    def gen_sum(m, b, y, t):
        if not gen_terms:
            return 0.0
        return sum(expr(m, b, y, t) for expr in gen_terms)
    m.Pgen_bus = pyo.Expression(m.B, m.TY, rule=gen_sum)

    # Balance nodal: Gen - D + (shed) - sum(flows salientes) = 0
    def nbalance_rule(m, b, y, t):
        # suma de flujos que salen de b (signo convencional)
        flow_out = 0.0
        for l in m.L:
            bi = m.bus_i[l]
            bj = m.bus_j[l]
            if bi == b:
                flow_out += m.flow[l, (y, t)]
            elif bj == b:
                flow_out -= m.flow[l, (y, t)]
        lhs = m.Pgen_bus[b, (y, t)] - m.D[b, (y, t)]
        if m.shed is not None:
            lhs = lhs + m.shed[b, (y, t)]
        return lhs - flow_out == 0.0
    m.NodeBalance = pyo.Constraint(m.B, m.TY, rule=nbalance_rule)

    # Objetivo (solo shedding por ahora; los costos de generación se agregan desde cada tecnología)
    def obj_rule(m):
        shed_cost = 0.0
        if m.shed is not None:
            shed_cost = sum(m.VOLL[b] * m.shed[b, (y, t)] for b in m.B for (y, t) in m.TY)
        return shed_cost
    m.OBJ = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    return m