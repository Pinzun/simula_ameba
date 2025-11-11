# model/hydro_balance.py
from __future__ import annotations
import logging
from typing import Dict, Tuple, Iterable
from pyomo.environ import (
    Set, Param, Var, NonNegativeReals, Reals, Constraint
)

def _succ_tuple(m, s, b):
    if (s, b) in m.SB_SUCC:
        return int(m.SuccStage[s, b]), int(m.SuccBlock[s, b])
    return None

def build_hydro_balance(
    m,
    tb,
    hd: Dict,
    inflow_node: Dict[Tuple[str, int, int], float],
    irr: Dict,
):
    """Construye el módulo de balance hídrico multinodal."""
    log = logging.getLogger("hydro_balance")

    # --- 1. Conjuntos base -------------------------------------------------
    nodes = hd["hydro_nodes"]
    dams = hd["dams"]
    gens = hd["gens"]
    arcs = hd["arcs"]

    m.HN = Set(initialize=nodes)
    m.HD = Set(initialize=dams)
    m.HG = Set(initialize=gens)
    m.HA = Set(dimen=2, initialize=arcs)

    log.info("[hydro_balance] nodos=%d, embalses=%d, generadores=%d, arcos=%d",
             len(nodes), len(dams), len(gens), len(arcs))

    # --- 2. Mapeos internos -------------------------------------------------
    m._dam_node = hd["dam_node"]
    m._gens_by_node = hd["gens_by_node"]
    m._dams_by_node = hd["dams_by_node"]
    m._gen_node = hd["gen_node"]
    m._gen_dam = hd["gen_dam"]

    # --- 3. Parámetros de flujos -------------------------------------------
    m.HFmax = Param(m.HA, initialize=hd["Fmax"], within=Reals, default=0.0)
    m.HFmin = Param(m.HA, initialize=hd["Fmin"], within=Reals, default=0.0)

    # --- 4. Almacenamientos agregados por nodo ------------------------------
    Vmax_d, Vmin_d, Vini_d, Vend_d = (
        hd.get("Vmax", {}), hd.get("Vmin", {}), hd.get("Vini", {}), hd.get("Vend", {})
    )

    def _sum_by_node(node, src): return sum(float(src.get(d, 0)) for d in m._dams_by_node.get(node, []))
    Vmax_node = {n: _sum_by_node(n, Vmax_d) for n in nodes}
    Vmin_node = {n: _sum_by_node(n, Vmin_d) for n in nodes}
    Vini_node = {n: _sum_by_node(n, Vini_d) for n in nodes}
    Vend_node = {n: _sum_by_node(n, Vend_d) for n in nodes}

    m.HNodesWithStorage = Set(initialize=[n for n in nodes if Vmax_node.get(n, 0.0) > 0.0])
    log.info("[hydro_balance] nodos con almacenamiento: %d", len(m.HNodesWithStorage))

    m.HVmax = Param(m.HNodesWithStorage, initialize=lambda m, n: Vmax_node[n], within=Reals, default=0.0)
    m.HVmin = Param(m.HNodesWithStorage, initialize=lambda m, n: Vmin_node[n], within=Reals, default=0.0)
    m.HVini = Param(m.HNodesWithStorage, initialize=lambda m, n: Vini_node[n], within=Reals, default=0.0)
    m.HVend = Param(m.HNodesWithStorage, initialize=lambda m, n: Vend_node[n], within=Reals, default=0.0)

    # --- 5. Inflows & Irrigación -------------------------------------------
    m.HInflow = Param(
        m.HN, m.SB,
        initialize=lambda m, n, s, b: float(inflow_node.get((n, int(s), int(b)), 0.0)),
        within=Reals, default=0.0
    )
    log.info("[hydro_balance] inflows cargados: %d", len(inflow_node))

    irr_required_node = (irr or {}).get("irr_required_node", {})
    m.HIrrReq = Param(
        m.HN, m.SB,
        initialize=lambda m, n, s, b: float(irr_required_node.get((n, int(s), int(b)), 0.0)),
        within=Reals, default=0.0
    )
    log.info("[hydro_balance] riegos cargados: %d", len(irr_required_node))

    # --- 6. Variables -------------------------------------------------------
    m.HFlow = Var(m.HA, m.SB, domain=NonNegativeReals)
    m.HRTurb = Var(m.HN, m.SB, domain=NonNegativeReals)
    m.HSpill = Var(m.HN, m.SB, domain=NonNegativeReals)
    m.HIrr   = Var(m.HN, m.SB, domain=NonNegativeReals)
    m.HStorage = Var(m.HNodesWithStorage, m.SB, domain=NonNegativeReals)
    m.HDischarge = Var(m.HG, m.SB, domain=NonNegativeReals)
    log.info("[hydro_balance] variables creadas correctamente")

    # --- 7. Balance de masa -------------------------------------------------
    _UP = {n: [] for n in nodes}
    _DN = {n: [] for n in nodes}
    for (i, j) in arcs:
        _DN[i].append(j)
        _UP[j].append(i)

    def _mass_balance_rule(m, n, s, b):
        inflow_up = sum(m.HFlow[i, n, s, b] for i in _UP[n] if (i, n) in m.HA)
        outflow_dn = sum(m.HFlow[n, j, s, b] for j in _DN[n] if (n, j) in m.HA)
        I_nt = m.HInflow[n, s, b]
        use_turb = m.HRTurb[n, s, b]
        spill = m.HSpill[n, s, b]
        irr_e = m.HIrr[n, s, b]
        if n in m.HNodesWithStorage:
            succ = _succ_tuple(m, s, b)
            if succ is None:
                return (m.HStorage[n, s, b] + (I_nt + inflow_up - outflow_dn - use_turb - spill - irr_e)
                        == m.HVend[n])
            s2, b2 = succ
            return (m.HStorage[n, s2, b2]
                    == m.HStorage[n, s, b] + (I_nt + inflow_up - outflow_dn - use_turb - spill - irr_e))
        else:
            return I_nt + inflow_up - outflow_dn - use_turb - spill - irr_e == 0.0

    m.HMassBalance = Constraint(m.HN, m.SB, rule=_mass_balance_rule)
    log.info("[hydro_balance] restricciones de balance creadas")

    # --- 8. Límites y consistencias ----------------------------------------
    def _storage_bounds_rule(m, n, s, b):
        return (m.HVmin[n], m.HStorage[n, s, b], m.HVmax[n])
    m.HStorageBounds = Constraint(m.HNodesWithStorage, m.SB, rule=_storage_bounds_rule)

    def _initial_storage_rule(m, n):
        s0, b0 = next(iter(m.SB.data()))
        return m.HStorage[n, s0, b0] == m.HVini[n]
    m.HStorageInitial = Constraint(m.HNodesWithStorage, rule=_initial_storage_rule)

    def _irr_req_rule(m, n, s, b):
        return m.HIrr[n, s, b] <= m.HIrrReq[n, s, b]
    m.HIrrCap = Constraint(m.HN, m.SB, rule=_irr_req_rule)

    def _turb_link_rule(m, n, s, b):
        gens = m._gens_by_node.get(n, [])
        if not gens:
            return m.HRTurb[n, s, b] >= 0.0
        return m.HRTurb[n, s, b] >= sum(m.HDischarge[g, s, b] for g in gens)
    m.HTurbToGen = Constraint(m.HN, m.SB, rule=_turb_link_rule)

    def _no_turb_without_storage(m, n, s, b):
        if n not in m.HNodesWithStorage:
            return m.HRTurb[n, s, b] == 0.0
        return Constraint.Skip
    m.HNoTurbAtRunOfRiver = Constraint(m.HN, m.SB, rule=_no_turb_without_storage)

    def _no_spill_without_storage(m, n, s, b):
        if n not in m.HNodesWithStorage:
            return m.HSpill[n, s, b] == 0.0
        return Constraint.Skip
    m.HNoSpillAtRunOfRiver = Constraint(m.HN, m.SB, rule=_no_spill_without_storage)

    log.info("[hydro_balance] restricciones adicionales y límites creados")
    log.info("[hydro_balance] módulo hídrico inicializado correctamente ✅")
    return m