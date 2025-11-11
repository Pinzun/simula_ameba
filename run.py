# run.py
from __future__ import annotations
import logging
from pathlib import Path

from pyomo.environ import ConcreteModel
from io_utils import load_blocks_structures, log_blocks_info
from model.time import build_time

# Mantienes los nombres originales:
from io_utils import load_demand, log_demand_info
from model.demand import build_demand

# --- logging simple
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log_time = logging.getLogger("time")

DATA_DIR = Path("data/processed")

def main():
    # ----- Calendario -----
    blocks_csv = DATA_DIR / "blocks.csv"
    tb = load_blocks_structures(blocks_csv)
    log_blocks_info(tb, log_time, sample=3)

    m = ConcreteModel()
    build_time(m, tb)

    # (opcional) sanity
    sb_first = next(iter(m.SB))
    log_time.info("SB tamaño: %d; primer índice: %s", len(list(m.SB.data())), sb_first)
    if sb_first in m.SB_SUCC:
        s, b = sb_first
        log_time.info("Sucesor de %s -> (%s,%s)", (s, b), int(m.SuccStage[s, b]), int(m.SuccBlock[s, b]))
    else:
        log_time.info("El primer bloque no tiene sucesor (caso raro).")

    # ----- Demanda (MWh por bloque) -----
    # OJO: si demand.csv ya viene en energía (MWh) por (node, stage, block),
    # el loader no requiere tb["duration"].
    dmd = load_demand(DATA_DIR / "demand.csv")
    log_demand_info(dmd, tb, log_time, sample=3)  # <-- coma corregida
    build_demand(m, dmd)  # build_demand debería crear m.DemandMWh y, si no existe, m.NODES

if __name__ == "__main__":
    main()
