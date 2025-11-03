# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict
from pyomo.environ import (
    Set, Param, Var, NonNegativeReals, Binary, Constraint, Expression
)

def attach_ess_to_model(
    m,
    ess_units: Dict[str, "ESSUnit"],
    *,
    forbid_simultaneous: bool = True,    # True: prohíbe cargar y descargar a la vez
    binary_switch: bool = False,         # True: y_c es binaria; False: relajada [0,1]
    vom_on: str = "discharge",           # "discharge" | "throughput"
):
    """
    Requiere en el modelo:
      - m.TY: conjunto de (y,t)
      - m.prev[(y,t)] -> (y_prev, t_prev) para el balance temporal
      - m.B: barras
      - m.alpha[(y,t)], m.df[(y,t)] (si usas escaladores y duración)
    """

    # ---------------- Conjuntos ----------------
    I = sorted(ess_units.keys())
    m.ESS = Set(initialize=I, ordered=True)

    bus_map = {i: ess_units[i].busbar for i in I}
    if not hasattr(m, "B"):
        m.B = Set(initialize=sorted(set(bus_map.values())), ordered=True)

    # ---------------- Parámetros ----------------
    m.ess_bus  = Param(m.ESS, initialize=lambda m,i: bus_map[i], within=None, default=None)
    m.ess_pmaxd= Param(m.ESS, initialize=lambda m,i: ess_units[i].pmax_dis, within=NonNegativeReals, default=0)
    m.ess_pmaxc= Param(m.ESS, initialize=lambda m,i: ess_units[i].pmax_ch,  within=NonNegativeReals, default=0)
    m.ess_pmind= Param(m.ESS, initialize=lambda m,i: ess_units[i].pmin_dis, within=NonNegativeReals, default=0)
    m.ess_pminc= Param(m.ESS, initialize=lambda m,i: ess_units[i].pmin_ch,  within=NonNegativeReals, default=0)
    m.ess_vom  = Param(m.ESS, initialize=lambda m,i: ess_units[i].vomc,     within=NonNegativeReals, default=0)
    m.ess_aux  = Param(m.ESS, initialize=lambda m,i: ess_units[i].auxserv,  within=NonNegativeReals, default=0)
    m.ess_eini = Param(m.ESS, initialize=lambda m,i: ess_units[i].e_ini,    within=NonNegativeReals, default=0)
    m.ess_emax = Param(m.ESS, initialize=lambda m,i: ess_units[i].e_max,    within=NonNegativeReals, default=0)
    m.ess_emin = Param(m.ESS, initialize=lambda m,i: ess_units[i].e_min,    within=NonNegativeReals, default=0)
    m.ess_effc = Param(m.ESS, initialize=lambda m,i: ess_units[i].eff_c,    within=NonNegativeReals, default=1.0)
    m.ess_effd = Param(m.ESS, initialize=lambda m,i: ess_units[i].eff_d,    within=NonNegativeReals, default=1.0)

    # ---------------- Variables ----------------
    # Potencia de descarga y carga (MWh por bloque si m.df ya multiplica horarios; si no, MW)
    m.pd = Var(m.ESS, m.TY, within=NonNegativeReals)  # descarga
    m.pc = Var(m.ESS, m.TY, within=NonNegativeReals)  # carga
    m.e  = Var(m.ESS, m.TY, within=NonNegativeReals)  # estado de carga (MWh)

    # Switch de modo (carga vs descarga) — binario opcional
    dom = Binary if binary_switch else NonNegativeReals
    m.yc = Var(m.ESS, m.TY, within=dom)  # 1≈cargando; 0≈descargando (relajado si no binario)

    # ---------------- Límites potencia ----------------
    def _cap_dis_hi(m, i, y, t):
        # descarga ≤ pmax_dis * (1 - aux) * alpha * (1 - yc)
        return m.pd[i,(y,t)] <= m.ess_pmaxd[i] * (1 - m.ess_aux[i]) * m.alpha[(y,t)] * (1 - m.yc[i,(y,t)])
    m.ESS_PdisHi = Constraint(m.ESS, m.TY, rule=_cap_dis_hi)

    def _cap_dis_lo(m, i, y, t):
        return m.pd[i,(y,t)] >= m.ess_pmind[i] * (1 - m.yc[i,(y,t)])
    m.ESS_PdisLo = Constraint(m.ESS, m.TY, rule=_cap_dis_lo)

    def _cap_ch_hi(m, i, y, t):
        # carga ≤ pmax_ch * alpha * yc
        return m.pc[i,(y,t)] <= m.ess_pmaxc[i] * m.alpha[(y,t)] * m.yc[i,(y,t)]
    m.ESS_PchHi = Constraint(m.ESS, m.TY, rule=_cap_ch_hi)

    def _cap_ch_lo(m, i, y, t):
        return m.pc[i,(y,t)] >= m.ess_pminc[i] * m.yc[i,(y,t)]
    m.ESS_PchLo = Constraint(m.ESS, m.TY, rule=_cap_ch_lo)

    # (Opcional) Prohibir simultaneidad estricta (cuando yc es binaria ya se evita)
    if forbid_simultaneous and not binary_switch:
        # relajado: obligamos pd * pc ≈ 0 linealmente via upper bounds acoplados
        # pd ≤ pmax_d * (1 - yc), pc ≤ pmax_c * yc  (ya está), y sum ≤ max → suficiente en práctica.
        pass

    # ---------------- Dinámica del SoC ----------------
    def _soc_balance(m, i, y, t):
        if (y,t) not in m.prev:
            # primer bloque: fijar e a e_ini
            return m.e[i,(y,t)] == m.ess_eini[i] + (m.ess_effc[i]*m.pc[i,(y,t)] - m.pd[i,(y,t)]/m.ess_effd[i]) * m.df[(y,t)]
        y0,t0 = m.prev[(y,t)]
        return m.e[i,(y,t)] == m.e[i,(y0,t0)] + (m.ess_effc[i]*m.pc[i,(y,t)] - m.pd[i,(y,t)]/m.ess_effd[i]) * m.df[(y,t)]
    m.ESS_SoC = Constraint(m.ESS, m.TY, rule=_soc_balance)

    def _soc_hi(m, i, y, t):
        return m.e[i,(y,t)] <= m.ess_emax[i]
    m.ESS_SoCHi = Constraint(m.ESS, m.TY, rule=_soc_hi)

    def _soc_lo(m, i, y, t):
        return m.e[i,(y,t)] >= m.ess_emin[i]
    m.ESS_SoCLo = Constraint(m.ESS, m.TY, rule=_soc_lo)

    # ---------------- Cierre de ciclo por etapa (si aplica) ----------------
    # Si tu calendario define m.first_in_year[y] y m.last_in_year[y] (parejas (y,t))
    # aplicamos e(last_y) = e(first_y) cuando cycle_neutral=True
    if hasattr(m, "first_in_year") and hasattr(m, "last_in_year"):
        def _cycle_neutral_rule(m, i, y):
            # buscamos si la unidad i pide cierre de ciclo
            # (si no, soltamos la restricción: e_last >= e_first)
            # Extra: si quieres condición “solo si cycle_neutral=True”, usa un set de i que lo cumplan
            return m.e[i, m.last_in_year[y]] == m.e[i, m.first_in_year[y]]
        # Por simplicidad la aplicamos a todas; si quieres solo subset:
        # arma un set m.ESS_CYCLENEUT = {i | ess_units[i].cycle_neutral}
        from pyomo.environ import Any
        m.ESS_CycleNeutral = Constraint(m.ESS, m.Y, rule=lambda m,i,y: _cycle_neutral_rule(m,i,y))

    # ---------------- Inyección neta por barra ----------------
    # net = descarga_neta - carga   (descarga se reduce por auxserv)
    def _inj_bus(m, b, y, t):
        return sum( (m.pd[i,(y,t)] * (1 - m.ess_aux[i]) - m.pc[i,(y,t)])
                    for i in m.ESS if m.ess_bus[i] == b )
    m.gen_ess_by_bus = Expression(m.B, m.TY, rule=_inj_bus)

    # ---------------- Costos VOM ----------------
    if vom_on == "throughput":
        def _cost_vom(m):
            return sum(m.df[(y,t)] * m.ess_vom[i] * (m.pc[i,(y,t)] + m.pd[i,(y,t)])
                       for i in m.ESS for (y,t) in m.TY)
    else:  # "discharge"
        def _cost_vom(m):
            return sum(m.df[(y,t)] * m.ess_vom[i] * m.pd[i,(y,t)]
                       for i in m.ESS for (y,t) in m.TY)
    m.cost_ess_oper = Expression(rule=_cost_vom)

    return {
        "gen_ess_by_bus": m.gen_ess_by_bus,
        "cost_ess_oper":  m.cost_ess_oper,
        "pd": m.pd, "pc": m.pc, "e": m.e, "yc": m.yc,
    }