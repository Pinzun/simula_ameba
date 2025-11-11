#!/usr/bin/env python3
# scripts/crea_inflow_map.py
from __future__ import annotations
import re
import logging
import argparse
from pathlib import Path
import pandas as pd

def guess_node_for_inflow(inflow: str, nodes: list[str]) -> str | None:
    base = inflow.removeprefix("Afl_").lower()
    base = re.sub(r"[^a-z0-9]+", "", base)
    # heurística simple: subcadena
    candidates = []
    for n in nodes:
        nn = re.sub(r"[^a-z0-9]+", "", n.lower())
        if base in nn or nn in base:
            candidates.append(n)
    if len(candidates) == 1:
        return candidates[0]
    # si hay más de 1 (ambiguo) o 0, no sugerimos
    return None

def main():
    ap = argparse.ArgumentParser(description="Construye skeleton InflowMap.csv desde inflows_qm3.csv (Afl_*)")
    ap.add_argument("--project-root", default=".", help="Raíz del proyecto")
    ap.add_argument("--inflows", default="data/raw/inflows_qm3.csv")
    ap.add_argument("--hydro-nodes", default="data/raw/PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroNode.csv")
    ap.add_argument("--out", default="data/processed/InflowMap.csv")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    lg = logging.getLogger("build_inflow_map")

    root = Path(args.project_root)
    inflows_csv = root / args.inflows
    nodes_csv   = root / args.hydro_nodes
    out_csv     = root / args.out

    df = pd.read_csv(inflows_csv, nrows=2)
    afl_cols = [c for c in df.columns if c.startswith("Afl_")]
    if not afl_cols:
        raise SystemExit("No se encontraron columnas 'Afl_*' en inflows_qm3.csv")

    nodes = pd.read_csv(nodes_csv)["name"].astype(str).tolist()

    # si ya existe, lo leemos para preservar mapeos previos
    existing = {}
    if out_csv.exists():
        prev = pd.read_csv(out_csv)
        if {"inflow_name","node","dam"}.issubset(prev.columns):
            existing = {r.inflow_name: (r.node, r.dam if isinstance(r.dam, str) else "")
                        for r in prev.itertuples(index=False)}

    rows = []
    missing_guess = 0
    for afl in sorted(afl_cols):
        if afl in existing:
            node, dam = existing[afl]
        else:
            node = guess_node_for_inflow(afl, nodes) or ""
            dam  = ""
            if node == "":
                missing_guess += 1
        rows.append({"inflow_name": afl, "node": node, "dam": dam})

    out = pd.DataFrame(rows, columns=["inflow_name","node","dam"])
    out.to_csv(out_csv, index=False, encoding="utf-8")
    lg.info("InflowMap.csv escrito en %s (total inflows=%d, sin sugerencia=%d)", out_csv, len(rows), missing_guess)

if __name__ == "__main__":
    main()