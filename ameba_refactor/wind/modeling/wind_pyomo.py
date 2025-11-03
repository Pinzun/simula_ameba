# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict
from pyomo.environ import (
    Set, Param, Var, NonNegativeReals, Constraint, Expression
)

def attach_wind_to_model(
    m,
    winddata,
    enable_expansion: bool = False,
    kbar_by_y: Dict[int, float] | None = None
):
    # --------------------------------
    # Conjuntos y mapeos
    # --------------------------------
    plants = sorted(list(winddata.plants.keys()))
    m.WIND = Set(initialize=plants, ordered=True)

    wind_busbar_map: Dict[str, str] = {p: winddata.plants[p].busbar for p in plants}
    if not hasattr(m, "B"):
        bus_set = sorted({wind_busbar_map[p] for p in plants})
        m.B = Set(initialize=bus_set, ordered=True)

    m.wind_bus = Param(m.WIND, initialize=lambda m,i: wind_busbar_map[i], within=None, default=None)

    # --------------------------------
    # Parámetros
    # --------------------------------
    Pmax = {p: float(winddata.plants[p].pmax or 0.0) for p in plants}
    Vomc = {p: float(winddata.plants[p].vomc or 0.0) for p in plants}
    InvC = {p: float(winddata.plants[p].inv_cost or 0.0) for p in plants}
    Cand = {p: 1 if winddata.plants[p].candidate else 0 for p in plants}

    m.wind_pmax = Param(m.WIND, initialize=lambda m,i: Pmax[i], within=NonNegativeReals)
    m.wind_vomc = Param(m.WIND, initialize=lambda m,i: Vomc[i], within=NonNegativeReals, default=0.0)
    m.wind_invc = Param(m.WIND, initialize=lambda m,i: InvC[i], within=NonNegativeReals, default=0.0)
    m.wind_is_cand = Param(m.WIND, initialize=lambda m,i: Cand[i], within=NonNegativeReals)

    def _af_init(m, i, y, t):
        return float(winddata.af.get((i, int(y), int(t)), 0.0))
    m.wind_af = Param(m.WIND, m.TY, initialize=_af_init, within=NonNegativeReals, default=0.0)

    if enable_expansion and (kbar_by_y is not None):
        m.wind_kbar = Param(m.Y, initialize=lambda m,y: float(kbar_by_y.get(int(y), 1e9)), within=NonNegativeReals, default=1e9)

    # --------------------------------
    # Variables
    # --------------------------------
    m.p_wind = Var(m.WIND, m.TY, within=NonNegativeReals)  # MWh/bloque

    if enable_expansion:
        m.x_wind = Var(m.WIND, m.Y, within=NonNegativeReals)   # MW nuevos
        m.K_wind = Var(m.WIND, m.Y, within=NonNegativeReals)   # MW disponibles

        def _cap_evol(m, i, y):
            y0 = min(list(m.Y.data()))
            if y == y0:
                return m.K_wind[i, y] == m.wind_pmax[i] + m.x_wind[i, y]*m.wind_is_cand[i]
            else:
                return m.K_wind[i, y] == m.K_wind[i, y-1] + m.x_wind[i, y]*m.wind_is_cand[i]
        m.WIND_CapEvol = Constraint(m.WIND, m.Y, rule=_cap_evol)

        if hasattr(m, "wind_kbar"):
            def _inv_cap(m, y):
                return sum(m.x_wind[i, y] for i in m.WIND) <= m.wind_kbar[y]
            m.WIND_InvestCap = Constraint(m.Y, rule=_inv_cap)
    else:
        m.K_wind = Param(m.WIND, m.Y, initialize=lambda m,i,y: Pmax[i], within=NonNegativeReals)

    # --------------------------------
    # Restricciones
    # --------------------------------
    def _wind_cap_rule(m, i, y, t):
        return m.p_wind[i, (y, t)] <= m.wind_af[i, (y, t)] * m.K_wind[i, y] * m.alpha[(y, t)]
    m.WIND_Capacity = Constraint(m.WIND, m.TY, rule=_wind_cap_rule)

    # --------------------------------
    # Inyección por barra
    # --------------------------------
    def _gen_wind_bus_init(m, b, y, t):
        return sum(m.p_wind[i,(y,t)] for i in m.WIND if m.wind_bus[i] == b)
    m.gen_wind_by_bus = Expression(m.B, m.TY, rule=_gen_wind_bus_init)

    # --------------------------------
    # Costos
    # --------------------------------
    def _cost_op_rule(m):
        return sum(m.df[y] * sum(m.wind_vomc[i] * m.p_wind[i,(y,t)] for i in m.WIND) for (y,t) in m.TY)
    m.cost_wind_oper = Expression(rule=_cost_op_rule)

    if enable_expansion:
        def _cost_inv_rule(m):
            return sum(m.df[y] * sum(m.wind_invc[i] * m.x_wind[i, y] for i in m.WIND) for y in m.Y)
        m.cost_wind_inv = Expression(rule=_cost_inv_rule)
    else:
        m.cost_wind_inv = Expression(expr=0.0)

    return {
        "gen_wind_by_bus": m.gen_wind_by_bus,
        "cost_wind_oper":  m.cost_wind_oper,
        "cost_wind_inv":   m.cost_wind_inv,
    }