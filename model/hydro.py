# model/hydro.py
from pyomo.environ import Set, Param, Var, NonNegativeReals, Reals, Constraint

def build_hydro(m, tb, hd, inflow_node, irr_data, storage_targets="expected"):
    """
    m: ConcreteModel con m.SB, m.Duration ya creados.
    tb: dict del loader de blocks (stage_year, etc.)
    hd: dict de load_hydro_structures(...)
    inflow_node: dict[(node,s,b)] -> Hm3
    irr_data: dict con 'irr_required_node' -> dict[(node,s,b)]->Hm3
    storage_targets: "expected"|"fixed"|"none"
    """

    # --- Sets
    m.HNODES = Set(initialize=sorted(hd["hydro_nodes"]))
    m.DAMS   = Set(initialize=sorted(hd["dams"]))
    m.HGENS  = Set(initialize=sorted(hd["gens"]))
    m.HARCS  = Set(initialize=sorted(hd["arcs"]), dimen=2)

    # --- Mappings/Params estáticos
    m.DamNode = Param(m.DAMS, initialize=hd["dam_node"], within=m.HNODES)
    m.GenNode = Param(m.HGENS, initialize=hd["gen_node"], within=m.HNODES)
    # Generadores con o sin embalse asociado (None/"" -> no embalse)
    m.GenDam  = Param(m.HGENS, initialize={g:(hd["gen_dam"][g] if hd["gen_dam"][g] is not None else "") for g in hd["gens"]},
                      within=Reals, default=None, mutable=True)  # solo para referencia

    # Conversiones y límites
    m.Rho  = Param(m.HGENS, initialize=hd["Rho"])   # MWh/Hm3
    m.Pmax = Param(m.HGENS, initialize=hd["Pmax"])  # MW

    m.Vmax = Param(m.DAMS, initialize=hd["Vmax"])
    m.Vmin = Param(m.DAMS, initialize=hd["Vmin"])
    m.Vini = Param(m.DAMS, initialize=hd["Vini"])
    m.Vend = Param(m.DAMS, initialize=hd["Vend"])

    m.Fmax = Param(m.HARCS, initialize=hd["Fmax"])
    m.Fmin = Param(m.HARCS, initialize=hd["Fmin"])

    # Inflows e irrigación (Hm3 por bloque)
    m.Inflow = Param(m.HNODES, m.SB, initialize=inflow_node, default=0.0)
    m.Qirr   = Param(m.HNODES, m.SB, initialize=irr_data["irr_required_node"], default=0.0)

    # --- Variables (Hm3 por bloque, salvo EHydro)
    m.S      = Var(m.DAMS, m.SB, within=NonNegativeReals)     # almacenamiento
    m.Rel    = Var(m.DAMS, m.SB, within=NonNegativeReals)     # descarga a turbinas
    m.Spill  = Var(m.DAMS, m.SB, within=NonNegativeReals)     # vertimiento
    m.Flow   = Var(m.HARCS, m.SB, bounds=lambda m, i, j, sb: (m.Fmin[i,j], m.Fmax[i,j]))  # i->j

    m.d_g    = Var(m.HGENS, m.SB, within=NonNegativeReals)    # Hm3 asignados a gen g
    m.EHydro = Var(m.HGENS, m.SB, within=NonNegativeReals)    # MWh generados por g

    # --- Auxiliares por nodo
    def DamsOf(n):   return [d for d, nd in hd["dam_node"].items() if nd == n]
    def GensOf(n):   return hd["gens_by_node"].get(n, [])
    def Succ(sb):    # sucesor local ya lo tienes; útil si luego impones Vend en t_final
        return tb["succ_stage"].get(sb, None), tb["succ_block"].get(sb, None)

    # --- Balance de agua por nodo (sin retardo todavía)
    # sum_d S_{d,t+1} = sum_d S_{d,t} + Inflow_n,t + sum_i Flow_{i->n,t} - sum_k Flow_{n->k,t}
    #                   - sum_d Rel_{d,t} - sum_d Spill_{d,t} - Qirr_{n,t}
    def node_balance_rule(m, n, s, b):
        dams = DamsOf(n)
        # LHS: stock en t+1
        if (s, b) in tb["succ_stage"]:
            s1 = tb["succ_stage"][(s, b)]; b1 = tb["succ_block"][(s, b)]
            lhs = sum(m.S[d, (s1, b1)] for d in dams)
        else:
            # último bloque; dejamos continuidad libre (o igualamos a Vend via otro constraint)
            lhs = sum(m.S[d, (s, b)] for d in dams)

        inflow = m.Inflow[n, (s, b)]
        inflow_in  = sum(m.Flow[(i, n), (s, b)] for (i, j) in m.HARCS if j == n)
        outflow    = sum(m.Flow[(n, k), (s, b)] for (i, k) in m.HARCS if i == n)
        release    = sum(m.Rel[d, (s, b)]   for d in dams)
        spill      = sum(m.Spill[d, (s, b)] for d in dams)
        irr        = m.Qirr[n, (s, b)]

        rhs = sum(m.S[d, (s, b)] for d in dams) + inflow + inflow_in - outflow - release - spill - irr
        return lhs == rhs

    m.NodeWaterBal = Constraint(m.HNODES, m.SB, rule=node_balance_rule)

    # --- Enlace descarga a generadores del nodo
    # sum_g d_g = sum_d Rel_d   (por nodo y bloque)
    def release_split_rule(m, n, s, b):
        return sum(m.d_g[g, (s, b)] for g in GensOf(n)) == \
               sum(m.Rel[d, (s, b)] for d in DamsOf(n))
    m.SplitRelease = Constraint(m.HNODES, m.SB, rule=release_split_rule)

    # --- Potencia/energía por generador
    # E_g <= Rho_g * d_g            (conversión agua->energía)
    def hydro_conv_rule(m, g, s, b):
        return m.EHydro[g, (s, b)] <= m.Rho[g] * m.d_g[g, (s, b)]
    m.HydroConversion = Constraint(m.HGENS, m.SB, rule=hydro_conv_rule)

    # Límite por capacidad: E_g <= Pmax_g * Duration[s,b]
    def hydro_cap_rule(m, g, s, b):
        return m.EHydro[g, (s, b)] <= m.Pmax[g] * m.Duration[(s, b)]
    m.HydroCap = Constraint(m.HGENS, m.SB, rule=hydro_cap_rule)

    # --- Acotaciones de almacenamiento por dam
    def storage_bounds_rule(m, d, s, b):
        return (m.Vmin[d], m.S[d, (s, b)], m.Vmax[d])
    m.StorageBounds = Constraint(m.DAMS, m.SB, rule=storage_bounds_rule)

    # Inicial (t0) y final (según política)
    first_sb = next(iter(m.SB.data()))
    def init_storage_rule(m, d):
        return m.S[d, first_sb] == m.Vini[d]
    m.StorageInit = Constraint(m.DAMS, rule=init_storage_rule)

    if storage_targets == "fixed":
        last_sb = list(m.SB.data())[-1]
        def final_storage_rule(m, d):
            return m.S[d, last_sb] == m.Vend[d]
        m.StorageFinal = Constraint(m.DAMS, rule=final_storage_rule)
    # "expected": lo dejaremos para una iteración donde se imponga Vend en expectativa (promedio mensual, etc.)

    return m