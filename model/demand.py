# model/demand.py
from pyomo.environ import Set, Param, NonNegativeReals

def build_demand(m, demand_data):
    """
    Registra demanda energética por bloque:
      - Si no existe m.NODES, lo crea a partir de demand_data["nodes"].
      - Crea m.DemandMWh[node, (stage,block)] con default=0.0.
    Espera demand_data = {"nodes": set[str], "demand_mwh": dict[(node,s,b)->float], ...}
    """

    # 1) Set de nodos (defensivo)
    if not hasattr(m, "NODES"):
        m.NODES = Set(initialize=sorted(demand_data["nodes"]))

    # 2) Param de demanda en MWh por bloque
    m.DemandMWh = Param(
        m.NODES, m.SB,
        initialize=demand_data["demand_mwh"],
        within=NonNegativeReals,
        default=0.0
    )

    return m
