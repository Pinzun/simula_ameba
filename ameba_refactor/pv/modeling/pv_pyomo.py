# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict
from pyomo.environ import (
    Set, Param, Var, NonNegativeReals, Constraint, Expression
)

def attach_pv_to_model(
    m,
    pvdata,
    enable_expansion: bool = False,
    kbar_by_y: Dict[int, float] | None = None
):
    # ------------------------------
    # Conjuntos y mapeos
    # ------------------------------
    plants = sorted(list(pvdata.plants.keys()))
    m.PV = Set(initialize=plants, ordered=True)

    pv_busbar_map: Dict[str, str] = {p: pvdata.plants[p].busbar for p in plants}
    if not hasattr(m, "B"):
        bus_set = sorted({pv_busbar_map[p] for p in plants})
        m.B = Set(initialize=bus_set, ordered=True)

    m.pv_bus = Param(m.PV, initialize=lambda m,i: pv_busbar_map[i], within=None, default=None)

    # ------------------------------
    # Parámetros
    # ------------------------------
    Pmax = {p: float(pvdata.plants[p].pmax or 0.0) for p in plants}
    Vomc = {p: float(pvdata.plants[p].vomc or 0.0) for p in plants}
    InvC = {p: float(pvdata.plants[p].inv_cost or 0.0) for p in plants}
    Cand = {p: 1 if pvdata.plants[p].candidate else 0 for p in plants}

    m.pv_pmax = Param(m.PV, initialize=lambda m,i: Pmax[i], within=NonNegativeReals)
    m.pv_vomc = Param(m.PV, initialize=lambda m,i: Vomc[i], within=NonNegativeReals, default=0.0)
    m.pv_invc = Param(m.PV, initialize=lambda m,i: InvC[i], within=NonNegativeReals, default=0.0)
    m.pv_is_cand = Param(m.PV, initialize=lambda m,i: Cand[i], within=NonNegativeReals)

    def _af_init(m, i, y, t):
        return float(pvdata.af.get((i, int(y), int(t)), 0.0))
    m.pv_af = Param(m.PV, m.TY, initialize=_af_init, within=NonNegativeReals, default=0.0)

    if enable_expansion and (kbar_by_y is not None):
        m.pv_kbar = Param(m.Y, initialize=lambda m,y: float(kbar_by_y.get(int(y), 1e9)), within=NonNegativeReals, default=1e9)

    # ------------------------------
    # Variables
    # ------------------------------
    m.p_pv = Var(m.PV, m.TY, within=NonNegativeReals)  # MWh/bloque

    if enable_expansion:
        m.x_pv = Var(m.PV, m.Y, within=NonNegativeReals)   # MW nuevos
        m.K_pv = Var(m.PV, m.Y, within=NonNegativeReals)   # MW disponibles

        def _cap_evol(m, i, y):
            y0 = min(list(m.Y.data()))
            if y == y0:
                return m.K_pv[i, y] == m.pv_pmax[i] + m.x_pv[i, y]*m.pv_is_cand[i]
            else:
                return m.K_pv[i, y] == m.K_pv[i, y-1] + m.x_pv[i, y]*m.pv_is_cand[i]
        m.PV_CapEvol = Constraint(m.PV, m.Y, rule=_cap_evol)

        if hasattr(m, "pv_kbar"):
            def _inv_cap(m, y):
                return sum(m.x_pv[i, y] for i in m.PV) <= m.pv_kbar[y]
            m.PV_InvestCap = Constraint(m.Y, rule=_inv_cap)
    else:
        m.K_pv = Param(m.PV, m.Y, initialize=lambda m,i,y: Pmax[i], within=NonNegativeReals)

    # ------------------------------
    # Restricciones
    # ------------------------------
    def _pv_cap_rule(m, i, y, t):
        return m.p_pv[i, (y, t)] <= m.pv_af[i, (y, t)] * m.K_pv[i, y] * m.alpha[(y, t)]
    m.PV_Capacity = Constraint(m.PV, m.TY, rule=_pv_cap_rule)

    # ------------------------------
    # Inyección por barra
    # ------------------------------
    def _gen_pv_bus_init(m, b, y, t):
        return sum(m.p_pv[i,(y,t)] for i in m.PV if m.pv_bus[i] == b)
    m.gen_pv_by_bus = Expression(m.B, m.TY, rule=_gen_pv_bus_init)

    # ------------------------------
    # Costos
    # ------------------------------
    def _cost_op_rule(m):
        return sum(m.df[y] * sum(m.pv_vomc[i] * m.p_pv[i,(y,t)] for i in m.PV) for (y,t) in m.TY)
    m.cost_pv_oper = Expression(rule=_cost_op_rule)

    if enable_expansion:
        def _cost_inv_rule(m):
            return sum(m.df[y] * sum(m.pv_invc[i] * m.x_pv[i, y] for i in m.PV) for y in m.Y)
        m.cost_pv_inv = Expression(rule=_cost_inv_rule)
    else:
        m.cost_pv_inv = Expression(expr=0.0)

    return {
        "gen_pv_by_bus": m.gen_pv_by_bus,
        "cost_pv_oper":  m.cost_pv_oper,
        "cost_pv_inv":   m.cost_pv_inv,
    }