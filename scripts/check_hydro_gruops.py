#!/usr/bin/env python3
# scripts/check_hydro_groups.py
from __future__ import annotations
import logging
import argparse
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser(description="Chequeos de consistencia de HydroGroup vs HydroGenerator")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--hydro-groups", default="data/raw/PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGroup.csv")
    ap.add_argument("--hydro-gens", default="data/raw/PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGenerator.csv")
    ap.add_argument("--export-map", action="store_true", help="Exporta GenToGroup.csv en processed/")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    lg = logging.getLogger("check_hydro_groups")

    root = Path(args.project_root)
    hg = pd.read_csv(root / args.hydro_groups)
    gn = pd.read_csv(root / args.hydro_gens)

    assert {"name","hg_sp_min","hg_sp_max"}.issubset(hg.columns)
    groups = set(hg["name"].astype(str))

    col_group = "group" if "group" in gn.columns else ("hydro_group_name" if "hydro_group_name" in gn.columns else None)
    if not col_group:
        lg.warning("HydroGenerator.csv no contiene columna 'group' ni 'hydro_group_name'.")
        col_group = "group"
        gn[col_group] = None

    gens = gn["name"].astype(str).tolist()
    gmap = {str(r.name): (None if (pd.isna(getattr(r, col_group)) or str(getattr(r, col_group))=="") else str(getattr(r, col_group)))
            for r in gn.itertuples(index=False)}

    no_group = [g for g in gens if gmap.get(g) in (None, "")]
    if no_group:
        lg.warning("Generadores SIN grupo: %d (ej.): %s", len(no_group), no_group[:5])

    unknown = sorted({g for g, gr in gmap.items() if gr and gr not in groups})
    if unknown:
        lg.error("Generadores con grupo NO declarado (%d). Ej.: %s", len(unknown), unknown[:5])

    gens_by_group = {}
    for g, gr in gmap.items():
        if gr:
            gens_by_group.setdefault(gr, []).append(g)
    empty_groups = [gr for gr in groups if gr not in gens_by_group]
    if empty_groups:
        lg.warning("Grupos sin generadores asignados: %d (ej.): %s", len(empty_groups), empty_groups[:5])

    # Límites absolutos plausibles
    bad_limits = hg[(hg["hg_sp_min"] > hg["hg_sp_max"]) | (hg["hg_sp_min"] < 0)]
    if not bad_limits.empty:
        lg.error("Filas con límites inválidos (min>max o min<0):\n%s", bad_limits.head())

    if args.export_map:
        out = pd.DataFrame({"gen": list(gmap.keys()), "group": [gmap[g] or "" for g in gmap]})
        outp = root / "data" / "processed" / "GenToGroup.csv"
        outp.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(outp, index=False, encoding="utf-8")
        lg.info("Exportado %s", outp)

    lg.info("Chequeo finalizado.")

if __name__ == "__main__":
    main()