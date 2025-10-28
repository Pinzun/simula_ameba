# -*- coding: utf-8 -*-
"""
MVP expansión (1 zona) con etapas/bloques + demanda proyectada + HIDRO
----------------------------------------------------------------------
- Calendario: stages.csv (s_id,start_time,end_time,num_blocks), blocks.csv (stage,block,time)
- Demanda: demanda_proyectada -> agregado a bloque por SUMA (MWh por bloque)
- Hidro:
   * Dam (embalses): parámetros y costos de overflow/slack, κ por embalse
   * HydroConnection: mapeos Afl_*→Emb_*, arcos Emb→Emb y Emb→HG (turbinado/derrame)
   * HydroGenerator: unidades HG_* ROR (sin almacenamiento) con Pmax y κ_ror
   * HydroGroup: mínimos/máximos (MW) por HG_* → traducidos a MWh por bloque
Ejecutar:
    python mvp_expansion.py
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals, Objective, Constraint, minimize, value
)
from pyomo.opt import SolverFactory

# ---- rutas base del repo/proyecto ----
RUTA_BASE      = Path(__file__).parent.parent.parent
STAGES_CSV     = RUTA_BASE / "data" / "demanda" / "stages.csv"
BLOCKS_CSV     = RUTA_BASE / "data" / "demanda" / "blocks.csv"
DEMANDA_BASE   = RUTA_BASE / "data" / "demanda" / "demand.csv"
DEMANDA_FACTOR = RUTA_BASE / "data" / "demanda" / "factor.csv"

# HIDRO
RESERVOIRS_CSV    = RUTA_BASE / "data" / "generacion" / "hidro_sys" /  "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Dam.csv"
RUTA_INFLOWS_QM3  = RUTA_BASE / "data" / "generacion" / "recursos" / "inflows_qm3_pelp.csv"
HYDRO_CONN        = RUTA_BASE / "data" / "generacion" / "hidro_sys" / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroConnection.csv"
HYDRO_GENERATOR   = RUTA_BASE / "data" / "generacion" /  "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGenerator.csv"
HYDRO_GROUP       = RUTA_BASE / "data" / "generacion" / "hidro_sys" / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGroup.csv"

# módulos externos
from demanda_proyectada import project_demanda
from construye_inflows_qm3 import build_inflows_df
from carga_hydroconnection import load_hydro_connection
from carga_hydrogenerator import load_hydro_generator
from carga_hydrogroup import load_hydrogroup

# ===== CONFIG =====
TECHS         = ["cc_gas", "eolica", "solar"]     # térmicas/renovables "no-hidro"
DISCOUNT_R    = 0.08
SOLVER_NAME   = "appsi_highs"                     # HiGHS
BIGM_SLACK    = 1e9                               # para bloquear Slack si no se permite
KAPPA_DEFAULT = 1.0                               # MWh/hm3 (conv turbinado -> energía)

def build_costs(techs: List[str], Y_list: List[int]):
    cinv, cfix, cvar, knew = {}, {}, {}, {}
    for g in techs:
        for y in Y_list:
            if g == "cc_gas":
                cinv[(g, y)] = 900000.0
                cfix[(g, y)] = 20000.0
                cvar[(g, y)] = 55.0 + 3.0*(y-1)
                knew[(g, y)] = 600.0
            elif "eol" in g:
                cinv[(g, y)] = max(0.0, 1200000.0 - 100000.0*(y-1))
                cfix[(g, y)] = 15000.0
                cvar[(g, y)] = 0.0
                knew[(g, y)] = 400.0
            elif "sol" in g:
                cinv[(g, y)] = max(0.0, 800000.0 - 50000.0*(y-1))
                cfix[(g, y)] = 10000.0
                cvar[(g, y)] = 0.0
                knew[(g, y)] = 500.0
            else:
                cinv[(g, y)] = 1_000_000.0
                cfix[(g, y)] = 12_000.0
                cvar[(g, y)] = 30.0
                knew[(g, y)] = 300.0
    return cinv, cfix, cvar, knew

# ===== Util =====
def parse_time(s: str):
    return pd.to_datetime(s, format="%Y-%m-%d-%H:%M")

@dataclass
class InputData:
    stages: pd.DataFrame
    blocks: pd.DataFrame
    demand_total: pd.DataFrame  # columnas: time, MW_total (datetime, float)
    reservoirs: pd.DataFrame    # catálogo de embalses
    inflows: pd.DataFrame       # columnas: time, name, inflow (hm3/h), time como datetime

def load_inputs(registro: bool=False):
    # 1) Demanda proyectada (por timestamp y barra) -> sumatoria barras
    demanda_df = project_demanda(DEMANDA_BASE, DEMANDA_FACTOR, registro)
    all_cols = [c for c in demanda_df.columns if c != "time"]
    demanda_df["MW_total"] = demanda_df[all_cols].sum(axis=1, skipna=True)
    demanda_total = demanda_df[["time", "MW_total"]].copy()
    demanda_total["time"] = parse_time(demanda_total["time"])

    # 2) Calendario
    stages = pd.read_csv(STAGES_CSV)
    blocks = pd.read_csv(BLOCKS_CSV)
    stages.columns = [c.strip().lower() for c in stages.columns]
    blocks.columns = [c.strip().lower() for c in blocks.columns]
    for col in ["start_time", "end_time"]:
        stages[col] = parse_time(stages[col])
    blocks["time"] = parse_time(blocks["time"])

    # 3) Hidro: catálogo + inflows
    reservoirs = pd.read_csv(RESERVOIRS_CSV)
    inflows = build_inflows_df(RUTA_INFLOWS_QM3, escenario="H_1960", units="m3s")
    inflows["time"] = parse_time(inflows["time"])

    # 4) Red hidro (HydroConnection)
    (inflow_to_res, inflow_to_hg,
     arcs_spill_res, arcs_turb_res, arcs_spill_to_hg, arcs_turb_to_hg,
     arcs_spill_res_d, arcs_turb_res_d, arcs_spill_to_hg_d, arcs_turb_to_hg_d) = load_hydro_connection(HYDRO_CONN)

    # 5) Generadores hidro (HydroGenerator) -> ROR, PmaxROR, kappa_ror
    ROR, PmaxROR, kappa_ror = load_hydro_generator(HYDRO_GENERATOR, reservoirs, kappa_default=KAPPA_DEFAULT)

    # 6) Límites HydroGroup (min/max en MW)
    hg_df = load_hydrogroup(HYDRO_GROUP)  # DF: name,start_time,end_time,hg_sp_min,hg_sp_max
    hg_sp_min = {row["name"]: float(row["hg_sp_min"]) for _, row in hg_df.iterrows()}
    hg_sp_max = {row["name"]: float(row["hg_sp_max"]) for _, row in hg_df.iterrows()}

    input_extras = dict(
        inflow_to_res=inflow_to_res,
        inflow_to_hg=inflow_to_hg,
        arcs_spill_res=arcs_spill_res,           # SIN delay por ahora
        arcs_turb_res=arcs_turb_res,
        arcs_spill_to_hg=arcs_spill_to_hg,
        arcs_turb_to_hg=arcs_turb_to_hg,

        # (con delay para futuro)
        arcs_spill_res_d=arcs_spill_res_d,
        arcs_turb_res_d=arcs_turb_res_d,
        arcs_spill_to_hg_d=arcs_spill_to_hg_d,
        arcs_turb_to_hg_d=arcs_turb_to_hg_d,

        # ROR
        ROR=ROR, PmaxROR=PmaxROR, kappa_ror=kappa_ror,

        # HydroGroup (MW)
        hg_sp_min=hg_sp_min, hg_sp_max=hg_sp_max,
    )

    return InputData(
        stages=stages, blocks=blocks, demand_total=demanda_total,
        reservoirs=reservoirs, inflows=inflows
    ), input_extras


def aggregate_stage_block(inputs: InputData, techs: List[str], ex: dict):
    """
    Agrega calendario a bloques, demanda y parámetros hidro (Embalses + ROR).
    Devuelve: Y_list, T_by_Y, alpha, D, AF, K0, hydro
    """
    stages = inputs.stages.copy()
    blocks = inputs.blocks.copy()

    # === Conjuntos Y y T_by_Y ===
    Y_list = list(stages["s_id"].astype(int).sort_values().unique())
    T_by_Y: Dict[int, List[int]] = {}
    for y in Y_list:
        t_list = sorted(blocks.loc[blocks["stage"] == y, "block"].unique().tolist())
        if not t_list:
            nb = int(stages.loc[stages["s_id"] == y, "num_blocks"].iloc[0])
            t_list = list(range(1, nb + 1))
        T_by_Y[y] = t_list

    # === Horas por bloque (alpha) ===
    alpha: Dict[tuple, float] = {}
    for y in Y_list:
        for t in T_by_Y[y]:
            alpha[(y, t)] = float(len(blocks[(blocks["stage"] == y) & (blocks["block"] == t)]))

    # === Demanda por bloque (SUMA) ===
    D: Dict[tuple, float] = {}
    merged_D = blocks.merge(inputs.demand_total, how="left", on="time")
    grpD = merged_D.groupby(["stage", "block"], as_index=False)["MW_total"].sum()
    for _, r in grpD.iterrows():
        D[(int(r["stage"]), int(r["block"]))] = float(r["MW_total"])

    # === Embalses: parámetros ===
    reservoirs_df = inputs.reservoirs.copy()
    R_names = reservoirs_df["name"].astype(str).tolist()

    def _take_num(name: str, col: str, default: float = 0.0) -> float:
        sub = reservoirs_df.loc[reservoirs_df["name"] == name, col]
        return float(sub.iloc[0]) if len(sub) and pd.notna(sub.iloc[0]) else float(default)

    vmax   = {r: _take_num(r, "vmax") for r in R_names}
    vmin   = {r: _take_num(r, "vmin") for r in R_names}
    vini   = {r: _take_num(r, "vini") for r in R_names}
    vend   = {r: _take_num(r, "vend") for r in R_names}
    scale  = {r: _take_num(r, "scale", 1.0) for r in R_names}
    val_ovf= {r: _take_num(r, "val_ovf", 0.0) for r in R_names}

    non_phys, non_phys_pen = {}, {}
    for r in R_names:
        raw_np  = reservoirs_df.loc[reservoirs_df["name"] == r, "non_physical_inflow"]
        raw_pen = reservoirs_df.loc[reservoirs_df["name"] == r, "non_physical_inflow_penalty"]
        non_phys[r]     = bool(raw_np.iloc[0]) if len(raw_np) and pd.notna(raw_np.iloc[0]) else False
        non_phys_pen[r] = float(raw_pen.iloc[0]) if len(raw_pen) and pd.notna(raw_pen.iloc[0]) else 0.0

    kappa = {r: KAPPA_DEFAULT for r in R_names}

    # === Inflows por bloque hacia Embalses (Afl_* -> Emb_*) ===
    inflow_to_res = ex.get("inflow_to_res", {}) or ex.get("inflow_to_reservoir", {})
    merged_I = blocks.merge(inputs.inflows, how="left", on="time")
    merged_I["reservoir_dst"] = merged_I["name"].map(inflow_to_res)
    merged_I = merged_I[merged_I["reservoir_dst"].notna()].copy()
    grpI = merged_I.groupby(["reservoir_dst", "stage", "block"], as_index=False)["inflow"].sum()
    I_nat: Dict[tuple, float] = {}
    for _, r in grpI.iterrows():
        rr, yy, tt = str(r["reservoir_dst"]), int(r["stage"]), int(r["block"])
        I_nat[(rr, yy, tt)] = float(r["inflow"]) * scale.get(rr, 1.0)

    # === Inflows por bloque hacia HG ROR (Afl_* -> HG_*) ===
    inflow_to_hg = ex.get("inflow_to_hg", {})
    merged_I_hg = blocks.merge(inputs.inflows, how="left", on="time")
    merged_I_hg["hg_dst"] = merged_I_hg["name"].map(inflow_to_hg)
    merged_I_hg = merged_I_hg[merged_I_hg["hg_dst"].notna()].copy()
    grpI_hg = merged_I_hg.groupby(["hg_dst", "stage", "block"], as_index=False)["inflow"].sum()
    I_nat_ror: Dict[tuple, float] = {}
    for _, r in grpI_hg.iterrows():
        gg, yy, tt = str(r["hg_dst"]), int(r["stage"]), int(r["block"])
        I_nat_ror[(gg, yy, tt)] = float(r["inflow"])  # hm3/h sumado por horas del bloque

    # === Arcos filtrados ===
    # Emb→Emb
    arcs_spill_res = [(u, d) for (u, d) in (ex.get("arcs_spill_res") or []) if (u in R_names and d in R_names)]
    arcs_turb_res  = [(u, d) for (u, d) in (ex.get("arcs_turb_res")  or []) if (u in R_names and d in R_names)]
    # Emb→HG (origen debe ser Emb_*)
    arcs_spill_to_hg = [(u, gg) for (u, gg) in (ex.get("arcs_spill_to_hg") or []) if u in R_names]
    arcs_turb_to_hg  = [(u, gg) for (u, gg) in (ex.get("arcs_turb_to_hg")  or []) if u in R_names]

    # === Perfiles no-hidro (placeholder) ===
    AF: Dict[str, Dict[tuple, float]] = {g: {} for g in techs}
    for g in techs:
        for y in Y_list:
            for t in T_by_Y[y]:
                if "eol" in g:   val = 0.40 + 0.05*((t % 4) - 1)
                elif "sol" in g: val = [0.10, 0.50, 0.60, 0.15][(t-1) % 4]
                else:            val = 1.0
                AF[g][(y, t)] = float(max(0.0, min(1.0, val)))

    # === Capacidad existente (no-hidro) ===
    K0: Dict[str, float] = {}
    for g in techs:
        if "cc_gas" in g: K0[g] = 600.0
        elif "eol" in g:  K0[g] = 200.0
        elif "sol" in g:  K0[g] = 150.0
        else:             K0[g] = 0.0

    # === ROR desde HydroGenerator & límites HydroGroup ===
    ROR        = ex["ROR"]
    PmaxROR    = ex["PmaxROR"]
    kappa_ror  = ex["kappa_ror"]
    hg_sp_min  = ex.get("hg_sp_min", {})
    hg_sp_max  = ex.get("hg_sp_max", {})

    hydro = {
        # Embalses
        "R": R_names,
        "vmax": vmax, "vmin": vmin, "vini": vini, "vend": vend,
        "kappa": kappa, "val_ovf": val_ovf,
        "non_phys": non_phys, "non_phys_pen": non_phys_pen,
        "I_nat": I_nat,
        "arcs_spill_res": arcs_spill_res, "arcs_turb_res": arcs_turb_res,
        # ROR
        "ROR": ROR,
        "PmaxROR": PmaxROR,
        "kappa_ror": kappa_ror,
        "I_nat_ror": I_nat_ror,
        "arcs_spill_to_hg": arcs_spill_to_hg,
        "arcs_turb_to_hg": arcs_turb_to_hg,
        # HydroGroup (MW)
        "hg_sp_min": hg_sp_min,
        "hg_sp_max": hg_sp_max,
    }

    return Y_list, T_by_Y, alpha, D, AF, K0, hydro


# ===== Modelo =====
def build_model(Y_list, T_by_Y, alpha, D, techs, AF, K0,
                cinv, cfix, cvar, Knew_bar, hydro, r=DISCOUNT_R):
    m = ConcreteModel(name="Expansion_1Z_StagesBlocks_Hydro")

    # --- Conjuntos de tiempo/tecnologías ---
    TY = [(y, t) for y in Y_list for t in T_by_Y[y]]
    m.Y  = Set(initialize=Y_list, ordered=True)
    m.TY = Set(dimen=2, initialize=TY, ordered=True)
    m.G  = Set(initialize=techs, ordered=True)

    # --- Parámetros de demanda/tiempo ---
    m.df    = Param(m.Y, initialize={y: (1.0/((1.0+r)**(y-1))) for y in Y_list}, within=NonNegativeReals)
    m.alpha = Param(m.TY, initialize=alpha, within=NonNegativeReals)     # horas por bloque
    m.D     = Param(m.TY, initialize=D, within=NonNegativeReals)

    # --- Costos y disponibilidad no-hidro ---
    m.cinv = Param(m.G, m.Y, initialize=lambda m,g,y: cinv[(g,y)], within=NonNegativeReals)
    m.cfix = Param(m.G, m.Y, initialize=lambda m,g,y: cfix[(g,y)], within=NonNegativeReals)
    m.cvar = Param(m.G, m.Y, initialize=lambda m,g,y: cvar[(g,y)], within=NonNegativeReals)
    m.af   = Param(m.G, m.TY, initialize=lambda m,g,y,t: AF[g][(y,t)], within=NonNegativeReals)
    m.kbar = Param(m.G, m.Y, initialize=lambda m,g,y: Knew_bar[(g,y)], within=NonNegativeReals)
    m.C_ENS = Param(initialize=4000.0)

    # ==========================
    #       HIDRO: Embalses
    # ==========================
    m.R = Set(initialize=hydro["R"], ordered=True)

    m.vmax      = Param(m.R, initialize=lambda m,r: hydro["vmax"][r], within=NonNegativeReals)
    m.vmin      = Param(m.R, initialize=lambda m,r: hydro["vmin"][r], within=NonNegativeReals)
    m.vini      = Param(m.R, initialize=lambda m,r: hydro["vini"][r], within=NonNegativeReals)
    m.vend      = Param(m.R, initialize=lambda m,r: hydro["vend"][r], within=NonNegativeReals)
    m.kappa     = Param(m.R, initialize=lambda m,r: hydro["kappa"][r], within=NonNegativeReals)
    m.val_ovf   = Param(m.R, initialize=lambda m,r: hydro["val_ovf"][r], within=NonNegativeReals)
    m.slack_pen = Param(m.R, initialize=lambda m,r: hydro["non_phys_pen"][r], within=NonNegativeReals)
    m.allow_slack = Param(m.R, initialize=lambda m,r: 1 if hydro["non_phys"][r] else 0, within=NonNegativeReals)

    # Inflows naturales por bloque (hm3/bloque)
    m.I_nat = Param(
        m.R, m.TY,
        initialize=lambda m,r,y,t: hydro["I_nat"].get((r,y,t), 0.0),
        within=NonNegativeReals
    )

    # Arcos Emb->Emb (sin delay)
    m.ArcSpillRes = Set(dimen=2, initialize=hydro.get("arcs_spill_res", []))
    m.ArcTurbRes  = Set(dimen=2, initialize=hydro.get("arcs_turb_res",  []))

    # ==========================
    #   HIDRO: Unidades ROR (HG)
    # ==========================
    m.ROR = Set(initialize=hydro.get("ROR", []), ordered=True)

    m.PmaxROR   = Param(m.ROR, initialize=lambda m,g: float(hydro["PmaxROR"].get(g, 0.0)), within=NonNegativeReals)
    m.kappa_ror = Param(m.ROR, initialize=lambda m,g: float(hydro["kappa_ror"].get(g, KAPPA_DEFAULT)), within=NonNegativeReals)

    m.I_nat_ror = Param(
        m.ROR, m.TY,
        initialize=lambda m,g,y,t: float(hydro.get("I_nat_ror", {}).get((g,y,t), 0.0)),
        within=NonNegativeReals
    )

    # Arcos Emb->HG (sin delay)
    m.ArcTurbToHG  = Set(dimen=2, initialize=hydro.get("arcs_turb_to_hg", []))   # (Emb, HG)
    m.ArcSpillToHG = Set(dimen=2, initialize=hydro.get("arcs_spill_to_hg", []))  # (Emb, HG)

    # Límites HydroGroup (MW) por HG → se multiplican por horas del bloque
    m.hg_sp_min = Param(m.ROR, initialize=lambda m,g: float(hydro.get("hg_sp_min", {}).get(g, 0.0)))
    m.hg_sp_max = Param(m.ROR, initialize=lambda m,g: float(hydro.get("hg_sp_max", {}).get(g, 99999.0)))

    # ==========================
    #         Variables
    # ==========================
    # No-hidro
    m.x   = Var(m.G, m.Y, within=NonNegativeReals)     # inversión (MW)
    m.K   = Var(m.G, m.Y, within=NonNegativeReals)     # capacidad (MW)
    m.p   = Var(m.G, m.TY, within=NonNegativeReals)    # energía (MWh/bloque)
    m.ens = Var(m.TY,      within=NonNegativeReals)    # energía (MWh/bloque)

    # Embalses
    m.V     = Var(m.R, m.TY, within=NonNegativeReals)  # volumen (hm3)
    m.Turb  = Var(m.R, m.TY, within=NonNegativeReals)  # turbinado (hm3/bloque)
    m.Spill = Var(m.R, m.TY, within=NonNegativeReals)  # derrame (hm3/bloque)
    m.Slack = Var(m.R, m.TY, within=NonNegativeReals)  # afluencia no física (hm3/bloque)
    m.Ph    = Var(m.R, m.TY, within=NonNegativeReals)  # energía hidro de embalses (MWh/bloque)

    # ROR (energía MWh/bloque)
    m.P_ror = Var(m.ROR, m.TY, within=NonNegativeReals)

    # ==========================
    #       Restricciones
    # ==========================
    # Dinámica capacidad no-hidro
    def cap_evol(m, g, y):
        if y == min(Y_list):
            return m.K[g, y] == K0[g] + m.x[g, y]
        else:
            return m.K[g, y] == m.K[g, y-1] + m.x[g, y]
    m.CapEvol = Constraint(m.G, m.Y, rule=cap_evol)

    # Límite de inversión anual
    m.InvestCap = Constraint(m.G, m.Y, rule=lambda m,g,y: m.x[g,y] <= m.kbar[g,y])

    # Límite de energía no-hidro por bloque
    m.GenCap   = Constraint(m.G, m.TY, rule=lambda m,g,y,t: m.p[g,(y,t)] <= m.K[g,y] * m.alpha[(y,t)])
    m.GenAvail = Constraint(m.G, m.TY, rule=lambda m,g,y,t: m.p[g,(y,t)] <= m.af[g,(y,t)] * m.K[g,y] * m.alpha[(y,t)])

    # Embalses: conversión energía
    m.HydroConv = Constraint(m.R, m.TY, rule=lambda m,r,y,t: m.Ph[r,(y,t)] == m.kappa[r] * m.Turb[r,(y,t)])

    # Embalses: balance de volumen por bloque
    def vol_bal(m, r, y, t):
        if t == min(T_by_Y[y]):
            if y == min(Y_list):
                Vprev = m.vini[r]
            else:
                tprev = max(T_by_Y[y-1])
                Vprev = m.V[r, (y-1, tprev)]
        else:
            Vprev = m.V[r, (y, t-1)]

        # Ingresos desde otros embalses (derrame/turbinado) que lleguen a r
        spill_in = sum(m.Spill[ru, (y,t)] for (ru, rd) in m.ArcSpillRes if rd == r)
        turb_in  = sum(m.Turb[ru, (y,t)]  for (ru, rd) in m.ArcTurbRes  if rd == r)

        return m.V[r,(y,t)] == Vprev + m.I_nat[r,(y,t)] + spill_in + turb_in \
                               - m.Turb[r,(y,t)] - m.Spill[r,(y,t)] + m.Slack[r,(y,t)]
    m.VolBalance = Constraint(m.R, m.TY, rule=vol_bal)

    # Embalses: cotas y terminal
    m.VolMin = Constraint(m.R, m.TY, rule=lambda m,r,y,t: m.V[r,(y,t)] >= m.vmin[r])
    m.VolMax = Constraint(m.R, m.TY, rule=lambda m,r,y,t: m.V[r,(y,t)] <= m.vmax[r])

    last_y = max(Y_list)
    last_t = max(T_by_Y[last_y])
    m.VolTerminal = Constraint(m.R, rule=lambda m,r: m.V[r,(last_y, last_t)] == m.vend[r])

    # Embalses: bloquear Slack si no se permite
    m.SlackAllow = Constraint(m.R, m.TY, rule=lambda m,r,y,t: m.Slack[r,(y,t)] <= m.allow_slack[r] * BIGM_SLACK)

    # -------------- ROR --------------
    # (i) Límite de potencia por bloque (MW * horas → MWh/bloque)
    m.ROR_Capacity = Constraint(
        m.ROR, m.TY,
        rule=lambda m,g,y,t: m.P_ror[g,(y,t)] <= m.PmaxROR[g] * m.alpha[(y,t)]
    )

    # (ii) Límite hídrico (energía ≤ κ * (agua disponible))
    def ror_water_limit(m, g, y, t):
        # Agua turbinada/derramada desde embalses que llega a este HG en el mismo bloque
        turb_from_res  = sum(m.Turb[r,(y,t)]  for (r, gg) in m.ArcTurbToHG  if gg == g)
        spill_from_res = sum(m.Spill[r,(y,t)] for (r, gg) in m.ArcSpillToHG if gg == g)
        water_available = turb_from_res + spill_from_res + m.I_nat_ror[g,(y,t)]  # hm3/bloque
        return m.P_ror[g,(y,t)] <= m.kappa_ror[g] * water_available
    m.ROR_Water = Constraint(m.ROR, m.TY, rule=ror_water_limit)

    # (iii) Límites HydroGroup (MW) → energía por bloque (MWh)
    m.ROR_MinHG = Constraint(
        m.ROR, m.TY,
        rule=lambda m,g,y,t: m.P_ror[g,(y,t)] >= m.hg_sp_min[g] * m.alpha[(y,t)]
    )
    m.ROR_MaxHG = Constraint(
        m.ROR, m.TY,
        rule=lambda m,g,y,t: m.P_ror[g,(y,t)] <= m.hg_sp_max[g] * m.alpha[(y,t)]
    )

    # --- Balance de energía por bloque (MWh) ---
    def balance(m, y, t):
        gen_no_hidro = sum(m.p[g,(y,t)] for g in m.G)
        gen_h_emb    = sum(m.Ph[r,(y,t)] for r in m.R)
        gen_h_ror    = sum(m.P_ror[g,(y,t)] for g in m.ROR)
        return gen_no_hidro + gen_h_emb + gen_h_ror + m.ens[(y,t)] == m.D[(y,t)]
    m.Balance = Constraint(m.TY, rule=lambda m,y,t: balance(m,y,t))

    # ==========================
    #         Objetivo
    # ==========================
    def obj_rule(m):
        inv_fix = sum(m.df[y] * (m.cinv[g,y]*m.x[g,y] + m.cfix[g,y]*m.K[g,y])
                      for g in m.G for y in m.Y)

        oper_no_hidro = sum(m.df[y] * (
                                sum(m.cvar[g,y]*m.p[g,(y,t)] for g in m.G) +
                                m.C_ENS*m.ens[(y,t)]
                            ) for (y,t) in m.TY)

        oper_hidro = sum(m.df[y] * (
                            sum(m.val_ovf[r]*m.Spill[r,(y,t)] + m.slack_pen[r]*m.Slack[r,(y,t)]
                                for r in m.R)
                         ) for (y,t) in m.TY)

        return inv_fix + oper_no_hidro + oper_hidro

    m.TotalCost = Objective(rule=obj_rule, sense=minimize)
    return m

def main():
    inputs, ex = load_inputs(False)
    Y_list, T_by_Y, alpha, D, AF, K0, hydro = aggregate_stage_block(inputs, TECHS, ex)
    cinv, cfix, cvar, knew = build_costs(TECHS, Y_list)
    m = build_model(Y_list, T_by_Y, alpha, D, TECHS, AF, K0, cinv, cfix, cvar, knew, hydro)

    opt = SolverFactory(SOLVER_NAME)
    if not (opt and opt.available(exception_flag=False)):
        print(f"Solver '{SOLVER_NAME}' no disponible. Instala highspy (HiGHS) o usa CBC/GLPK.")
        return

    opt.solve(m, tee=False)

    print("=== Resultado de optimización ===")
    print(f"Costo total: {value(m.TotalCost):,.0f} $")

    print("\n-- Capacidad instalada por stage (MW) --")
    for y in m.Y:
        print(f"Stage {int(y)}:", {g: round(value(m.K[g,y]),2) for g in m.G})

    print("\n-- Inversión nueva por stage (MW) --")
    for y in m.Y:
        print(f"Stage {int(y)}:", {g: round(value(m.x[g,y]),2) for g in m.G})

    print("\n-- ENS total por stage (MWh) --")
    for y in m.Y:
        ens_MWh = sum(value(m.ens[(y,t)]) for t in T_by_Y[y])
        print(f"Stage {int(y)}: {ens_MWh:,.1f}")

    print("\n-- Generación no-hidro por tecno y stage (MWh) --")
    for y in m.Y:
        for g in m.G:
            gen_MWh = sum(value(m.p[g,(y,t)]) for t in T_by_Y[y])
            print(f"Stage {int(y)} - {g}: {gen_MWh:,.1f}")

    print("\n-- Generación hidro (Embalses+ROR) por stage (MWh) --")
    for y in m.Y:
        gen_emb = sum(sum(value(m.Ph[r,(y,t)]) for r in m.R) for t in T_by_Y[y])
        gen_ror = sum(sum(value(m.P_ror[g,(y,t)]) for g in m.ROR) for t in T_by_Y[y])
        print(f"Stage {int(y)}: Emb={gen_emb:,.1f} | ROR={gen_ror:,.1f} | Total={gen_emb+gen_ror:,.1f}")

if __name__ == "__main__":
    main()