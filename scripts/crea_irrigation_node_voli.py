#!/usr/bin/env python3
# scripts/crea_irrigation_node_voli.py
from __future__ import annotations
import logging
import argparse
from pathlib import Path
import pandas as pd
from collections import defaultdict

def main():
    ap = argparse.ArgumentParser(description="Proyecta VOLI por nodo desde Irrigation.csv + IrrigationPoint.csv")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--irrigation-catalog", default="data/raw/PNCP 2 - 2025 ESC-C  - PET 2024 V2_Irrigation.csv")
    ap.add_argument("--irrigation-points", default="data/processed/IrrigationPoint.csv")
    ap.add_argument("--out", default="data/processed/IrrigationNodeVoli.csv")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    lg = logging.getLogger("make_irrigation_node_voli")

    root = Path(args.project_root)
    ic = pd.read_csv(root / args.irrigation_catalog)
    ip = pd.read_csv(root / args.irrigation_points)

    assert {"name","voli"}.issubset(ic.columns)
    assert {"name","node"}.issubset(ip.columns)

    voli_point = {str(r.name): float(r.voli) for r in ic.itertuples(index=False)}
    point_node = {str(r.name): str(r.node) for r in ip.itertuples(index=False)}

    bucket = defaultdict(list)
    for p, v in voli_point.items():
        n = point_node.get(p)
        if n:
            bucket[n].append(v)

    rows = []
    for n, vs in bucket.items():
        rows.append({"node": n, "voli": max(vs)})  # conservador: máximo
    out = pd.DataFrame(rows, columns=["node","voli"]).sort_values("node")

    out_csv = root / args.out
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False, encoding="utf-8")
    lg.info("Escrito %s (nodos=%d)", out_csv, len(out))

if __name__ == "__main__":
    main()