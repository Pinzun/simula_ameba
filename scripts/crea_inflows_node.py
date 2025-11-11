#!/usr/bin/env python3
# scripts/crea_inflows_node.py
from __future__ import annotations
import logging
import argparse
from pathlib import Path
import pandas as pd

def load_inflow_catalog(csv_path: Path):
    cat = pd.read_csv(csv_path)
    assert {"name","inflows_qm3"}.issubset(cat.columns)
    return {str(r.name): float(r.inflows_qm3) for r in cat.itertuples(index=False)}

def main():
    ap = argparse.ArgumentParser(description="Genera inflows_node_long.csv (node,stage,block,inflow_hm3)")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--inflows-wide", default="data/raw/inflows_qm3.csv")
    ap.add_argument("--inflow-catalog", default="data/raw/PNCP 2 - 2025 ESC-C  - PET 2024 V2_Inflow.csv")
    ap.add_argument("--inflow-map", default="data/processed/InflowMap.csv")
    ap.add_argument("--blocks", default="data/processed/blocks.csv")
    ap.add_argument("--out", default="data/processed/inflows_node_long.csv")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    lg = logging.getLogger("make_inflows_node")

    root = Path(args.project_root)
    inflow_wide_csv = root / args.inflows_wide
    inflow_cat_csv  = root / args.inflow_catalog
    inflow_map_csv  = root / args.inflow_map
    blocks_csv      = root / args.blocks
    out_csv         = root / args.out

    # Leer datos
    wide = pd.read_csv(inflow_wide_csv)
    afl_cols = [c for c in wide.columns if c.startswith("Afl_")]
    if not afl_cols:
        raise SystemExit("No se encontraron columnas Afl_* en inflows_qm3.csv")

    mcat = load_inflow_catalog(inflow_cat_csv)
    mp = pd.read_csv(inflow_map_csv)
    assert {"inflow_name","node"}.issubset(mp.columns)
    inflow_to_node = {r.inflow_name: str(r.node) for r in mp.itertuples(index=False)}

    blocks = pd.read_csv(blocks_csv)
    assert {"stage","block","start_time"}.issubset(blocks.columns)
    blocks["stage"] = blocks["stage"].astype(int)
    blocks["block"] = blocks["block"].astype(int)
    blocks["_start_dt"] = pd.to_datetime(blocks["start_time"], format="%Y-%m-%d-%H:%M", errors="coerce")

    wide["_time_dt"] = pd.to_datetime(wide["time"], format="%Y-%m-%d-%H:%M", errors="coerce")
    mrg = blocks.merge(wide, left_on="_start_dt", right_on="_time_dt", how="left")

    long = mrg.melt(id_vars=["stage","block"], value_vars=afl_cols,
                    var_name="inflow_name", value_name="hm3_raw").fillna(0.0)

    long["scale"] = long["inflow_name"].map(mcat).fillna(1.0)
    long["hm3"]   = long["hm3_raw"] * long["scale"]
    long["node"]  = long["inflow_name"].map(inflow_to_node)

    missing = sorted(long.loc[long["node"].isna(),"inflow_name"].unique().tolist())
    if missing:
        lg.warning("Afl_* sin mapeo en InflowMap.csv (%d). Ej.: %s", len(missing), missing[:5])
        long = long.dropna(subset=["node"]).copy()

    agg = (
        long.groupby(["node","stage","block"], as_index=False)["hm3"]
            .sum()
            .rename(columns={"hm3":"inflow_hm3"})
            .sort_values(["node","stage","block"])
    )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(out_csv, index=False, encoding="utf-8")
    lg.info("Escrito %s (filas=%d, nodos=%d, stages~%d)", out_csv, len(agg), agg["node"].nunique(), agg["stage"].nunique())

if __name__ == "__main__":
    main()