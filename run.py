# run.py
from __future__ import annotations
import logging
from pathlib import Path

from pyomo.environ import ConcreteModel

# io_utils
from io_utils import load_blocks_structures, log_blocks_info
from io_utils import (
    load_hydro_structures,
    load_inflows_node,  # si quisieras usar el loader simple por nodo
    load_irrigation,
    log_hydro_info,
    load_hydro_groups,
    build_node_inflows_from_wide_inflows_qm3,
    load_irrigation_catalog,
    project_voli_to_nodes,
)

# model
from model.time import build_time
from model.hydro_balance import build_hydro_balance  # aún no usado, pero lo dejamos importado
from io_utils import load_demand, log_demand_info
from model.demand import build_demand

# --- logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log_time = logging.getLogger("time")
log_hydro = logging.getLogger("hydro")

DATA_DIR = Path("data/processed")

def main():
    # ----- Calendario -----
    blocks_csv = DATA_DIR / "blocks.csv"
    tb = load_blocks_structures(blocks_csv)
    log_blocks_info(tb, log_time, sample=3)

    m = ConcreteModel()
    build_time(m, tb)

    # Sanidad mínima de sucesores
    sb_first = next(iter(m.SB))
    log_time.info("SB tamaño: %d; primer índice: %s", len(list(m.SB.data())), sb_first)
    if sb_first in m.SB_SUCC:
        s, b = sb_first
        log_time.info("Sucesor de %s -> (%s,%s)", (s, b), int(m.SuccStage[s, b]), int(m.SuccBlock[s, b]))
    else:
        log_time.info("El primer bloque no tiene sucesor (caso raro).")

    # ----- Demanda (MWh por bloque) -----
    dmd = load_demand(DATA_DIR / "demand.csv")  # ya ajustado a energía
    log_demand_info(dmd, tb, log_time, sample=3)
    build_demand(m, dmd)

    # ----- Hidro: estructuras base -----
    hd = load_hydro_structures(
        DATA_DIR / "HydroNode.csv",
        DATA_DIR / "Dam.csv",
        DATA_DIR / "HydroConnection.csv",
        DATA_DIR / "HydroGenerator.csv",
    )

    # Inflows: armar por nodo desde wide + mapa (coherente con lo que generaste)
    inflow_node, missing_afl = build_node_inflows_from_wide_inflows_qm3(
        DATA_DIR / "inflows_qm3.csv",   # wide por afluente
        DATA_DIR / "inflows.csv",       # catálogo de inflows (Afl_*)
        DATA_DIR / "InflowMap.csv",    # mapeo Afl_* -> node (puede tener vacíos)
        DATA_DIR / "blocks.csv",
    )
    if missing_afl:
        log_hydro.info("Afl:* sin mapeo en inflow_map.csv (%d). Ejemplos: %s",
                       len(missing_afl), missing_afl[:5])

    # Riego: punto->nodo derivado desde HydroConnection (si no hay IrrigationPoint.csv)
    irr = load_irrigation(
        DATA_DIR / "IrrigationPoint.csv",  # si no existe, el loader derivará desde HydroConnection
        DATA_DIR / "Irrigation_qm3.csv",
    )

    # VOLI por nodo (límite absoluto): proyectar desde catálogo
    voli_by_point = load_irrigation_catalog(DATA_DIR / "Irrigation.csv")  # <- catálogo correcto
    voli_by_node = project_voli_to_nodes(voli_by_point, irr["point_node"], reduce="max")
    log_hydro.info("VOLI por nodo calculado (nodos=%d).", len(voli_by_node))

    # Grupos hídricos
    hgrp = load_hydro_groups(DATA_DIR / "HydroGroup.csv", DATA_DIR / "HydroGenerator.csv")
    log_hydro.info("hydro groups: %d", len(hgrp["groups"]))
    no_group = [g for g in hd["gens"] if hgrp["gen_to_group"].get(g) in (None, "")]
    if no_group:
        log_hydro.info("generadores sin grupo: %d (ej.): %s", len(no_group), no_group[:5])

    # Logs + diagrama de cuencas
    log_hydro_info(
        hd, inflow_node, irr, log_hydro,
        project_root=Path("."),
        png_relpath="outputs/diagrams/hydro_basins.png",
        html_relpath="outputs/diagrams/hydro_basins.html"
    )
    build_hydro_balance(m, tb, hd, inflow_node, irr)
    # (Próximo paso) build_hydro(m, hd, inflow_node, irr, hgrp, voli_by_node, tb)
    # Lo dejamos para cuando ya fijemos las ecuaciones del módulo hídrico.

if __name__ == "__main__":
    main()