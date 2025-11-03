# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Tuple, Callable
from pyomo.environ import (
    Set, Param, Var, NonNegativeReals, Binary, Constraint, Expression
)

def attach_thermal_to_model(
    m,
    units: Dict[str, "ThermalUnit"],
    fuel_price_fn: Callable[[str,int,int], float],   # (fuel,y,t) -> price
    co2_tax_param_name: str | None = "co2_tax",      # si existe en 'm', lo usamos ($/tCO2)
):
    # ---------------- Conjuntos ----------------
    I = sorted(units.keys())
    m.TH = Set(initialize=I, ordered=True)
    bus_map = {i: units[i].busbar for i in I}
    if not hasattr(m, "B"):
        m.B = Set(initialize=sorted(set(bus_map.values())), ordered=True)

    # ------------- Parámetros por unidad -------------
    m.th_bus   = Param(m.TH, initialize=lambda m,i: bus_map[i], within=None, default=None)
    m.th_pmax  = Param(m.TH, initialize=lambda m,i: units[i].pmax, within=NonNegativeReals)
    m.th_pmin  = Param(m.TH, initialize=lambda m,i: units[i].pmin, within=NonNegativeReals, default=0)
    m.th_vomc  = Param(m.TH, initialize=lambda m,i: units[i].vomc, within=NonNegativeReals, default=0)
    m.th_hr    = Param(m.TH, initialize=lambda m,i: units[i].heatrate, within=NonNegativeReals, default=0)
    m.th_sc    = Param(m.TH, initialize=lambda m,i: units[i].startcost, within=NonNegativeReals, default=0)
    m.th_dc    = Param(m.TH, initialize=lambda m,i: units[i].shutdncost, within=NonNegativeReals, default=0)
    m.th_ru    = Param(m.TH, initialize=lambda m,i: units[i].rampup, within=NonNegativeReals, default=1e9)
    m.th_rd    = Param(m.TH, initialize=lambda m,i: units[i].rampdn, within=NonNegativeReals, default=1e9)
    m.th_upt   = Param(m.TH, initialize=lambda m,i: units[i].minuptime, within=NonNegativeReals, default=0)
    m.th_dnt   = Param(m.TH, initialize=lambda m,i: units[i].mindntime, within=NonNegativeReals, default=0)
    m.th_aux   = Param(m.TH, initialize=lambda m,i: units[i].auxserv, within=NonNegativeReals, default=0)
    m.th_uc    = Param(m.TH, initialize=lambda m,i: 1.0 if units[i].uc_linear else 0.0)
    m.th_co2e  = Param(m.TH, initialize=lambda m,i: units[i].co2_emission, within=NonNegativeReals, default=0)
    m.th_fuel  = Param(m.TH, initialize=lambda m,i: units[i].fuel_name, within=None, default=None)

    # ------------- Precio de combustible por (i,y,t) -------------
    def _fuel_price_init(m, i, y, t):
        return float(fuel_price_fn(m.th_fuel[i], int(y), int(t)))
    m.th_fuel_price = Param(m.TH, m.TY, initialize=_fuel_price_init, within=NonNegativeReals, default=0)

    # ------------- Variables -------------
    m.p_th = Var(m.TH, m.TY, within=NonNegativeReals)      # MWh
    m.u_th = Var(m.TH, m.TY, within=NonNegativeReals)      # si uc=1, actúa como binaria (0/1)
    m.v_on = Var(m.TH, m.TY, within=NonNegativeReals)      # arranques
    m.w_off= Var(m.TH, m.TY, within=NonNegativeReals)      # detenciones

    # Si deseas binarizar estrictamente cuando uc_linear=1, cambia dominio a Binary y agrega big-M
    # (MVP linear-relaxed deja uc como [0,1] y funciona bien para prueba)

    # ------------- Reglas de operación -------------
    # Capacidad neta descontando auxiliares
    def _cap_hi(m, i, y, t):
        return m.p_th[i,(y,t)] <= (m.th_pmax[i] * m.u_th[i,(y,t)]) * (1 - m.th_aux[i]) * m.alpha[(y,t)]
    m.TH_CapHi = Constraint(m.TH, m.TY, rule=_cap_hi)

    def _cap_lo(m, i, y, t):
        return m.p_th[i,(y,t)] >= m.th_pmin[i] * m.u_th[i,(y,t)]
    m.TH_CapLo = Constraint(m.TH, m.TY, rule=_cap_lo)

    # Compromiso: u_t - u_{t-1} = v_on - w_off
    # Se requiere un mapeo de predecesor: m.prev[(y,t)] -> (y,t_prev) ó None
    def _status_balance(m, i, y, t):
        if (y,t) not in m.prev:    # si no existe, no aplicamos transición (primer bloque del horizonte)
            return m.u_th[i,(y,t)] >= 0
        y0,t0 = m.prev[(y,t)]
        return m.u_th[i,(y,t)] - m.u_th[i,(y0,t0)] == m.v_on[i,(y,t)] - m.w_off[i,(y,t)]
    m.TH_Status = Constraint(m.TH, m.TY, rule=_status_balance)

    # Rampas
    def _ramp_up(m, i, y, t):
        if (y,t) not in m.prev: 
            return m.p_th[i,(y,t)] >= 0
        y0,t0 = m.prev[(y,t)]
        return m.p_th[i,(y,t)] - m.p_th[i,(y0,t0)] <= m.th_ru[i]
    m.TH_RampUp = Constraint(m.TH, m.TY, rule=_ramp_up)

    def _ramp_dn(m, i, y, t):
        if (y,t) not in m.prev:
            return m.p_th[i,(y,t)] >= 0
        y0,t0 = m.prev[(y,t)]
        return m.p_th[i,(y0,t0)] - m.p_th[i,(y,t)] <= m.th_rd[i]
    m.TH_RampDn = Constraint(m.TH, m.TY, rule=_ramp_dn)

    # (MVP) Min up/down en forma acumulada simple (relajado):
    # Puedes reemplazar por formulación estándar (tuplas de ventanas) cuando quieras UC estricto
    # — aquí mantenemos el MVP simple y estable numéricamente.

    # ------------- Inyección por barra -------------
    def _gen_th_bus(m, b, y, t):
        return sum(m.p_th[i,(y,t)] for i in m.TH if m.th_bus[i] == b)
    m.gen_th_by_bus = Expression(m.B, m.TY, rule=_gen_th_bus)

    # ------------- Costos -------------
    def _marginal_cost(m, i, y, t):
        # Costo variable = (heatrate * precio_fuel + VOM) * MWh
        fuel_part = m.th_hr[i] * m.th_fuel_price[i,(y,t)]
        vom_part  = m.th_vomc[i]
        return (fuel_part + vom_part) * m.p_th[i,(y,t)]

    def _emission_cost(m, i, y, t):
        if co2_tax_param_name and hasattr(m, co2_tax_param_name):
            return m.__getattribute__(co2_tax_param_name) * m.th_co2e[i] * m.p_th[i,(y,t)]
        return 0.0

    def _start_cost_block(m, i, y, t):
        return m.th_sc[i] * m.v_on[i,(y,t)]

    def _shut_cost_block(m, i, y, t):
        return m.th_dc[i] * m.w_off[i,(y,t)]

    def _cost_oper_rule(m):
        return sum(m.df[y] * (
            _marginal_cost(m,i,y,t) + _emission_cost(m,i,y,t) + _start_cost_block(m,i,y,t) + _shut_cost_block(m,i,y,t)
        ) for (y,t) in m.TY for i in m.TH)
    m.cost_th_oper = Expression(rule=_cost_oper_rule)

    return {
        "gen_th_by_bus": m.gen_th_by_bus,
        "cost_th_oper":  m.cost_th_oper,
        "p_th":          m.p_th,
        "u_th":          m.u_th,
    }