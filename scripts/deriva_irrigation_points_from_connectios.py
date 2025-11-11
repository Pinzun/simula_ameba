#!/usr/bin/env python3
#scripts/deriva_irrgations_points_from_connections.py
from __future__ import annotations
import argparse, logging
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser(description="Deriva IrrigationPoint.csv desde HydroConnection (h_type=irrigation)")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--hydro-connection", default=None, help="Ruta a HydroConnection.csv")
    ap.add_argument("--irrigation-catalog", default=None, help="Ruta a Irrigation.csv (para validar 'end' y VOLI)")
    ap.add_argument("--out-points", default="data/processed/IrrigationPoint.csv")
    ap.add_argument("--out-node-voli", default=None, help="Si se pasa, escribe data/processed/IrrigationNodeVoli.csv")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    lg = logging.getLogger("derive_irrigation_points")

    root = Path(args.project_root)
    def resolve_csv(user_arg, processed_rel, raw_rel, label):
        p = root / user_arg if user_arg else (root/processed_rel if (root/processed_rel).exists() else root/raw_rel)
        if not p.exists():
            raise FileNotFoundError(
                f"No encontré {label}. Probé:\n - {root/processed_rel}\n - {root/raw_rel}\n"
                f"Sugerencia: usa --{label.replace('.csv','').lower().replace(' ','-')}"
            )
        lg.info("Usando %s: %s", label, p)
        return p

    conn_csv = resolve_csv(args.hydro_connection, "data/raw/PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroConnection.csv", "data/raw/HydroConnection.csv", "HydroConnection.csv")
    irr_csv  = resolve_csv(args.irrigation_catalog, "data/raw/PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroConnection.csv", "data/raw/Irrigation.csv", "Irrigation.csv")

    out_pts = root / args.out_points
    out_pts.parent.mkdir(parents=True, exist_ok=True)

    # Cargar
    conn = pd.read_csv(conn_csv)
    irr  = pd.read_csv(irr_csv)

    # columnas mínimas
    need_conn = {"h_type","ini","end"}
    if not need_conn.issubset(conn.columns):
        raise SystemExit(f"HydroConnection.csv debe contener {need_conn}")
    if "name" not in irr.columns:
        raise SystemExit("Irrigation.csv debe contener columna 'name'")

    # Filtrar conexiones de riego
    irrc = conn[conn["h_type"].astype(str).str.lower().eq("irrigation")].copy()
    if irrc.empty:
        raise SystemExit("No hay filas h_type=irrigation en HydroConnection.csv")

    # end = nombre de activo de riego; ini = nodo hídrico donde se extrae
    irrc["name"] = irrc["end"].astype(str)
    irrc["node"] = irrc["ini"].astype(str)

    # Validar que todos los 'end' existan en catálogo de riego
    missing = sorted(set(irrc["name"]) - set(irr["name"].astype(str)))
    if missing:
        logging.warning("Puntos de riego en conexiones no presentes en Irrigation.csv (%d): %s",
                        len(missing), missing[:10])

    # Construir IrrigationPoint.csv (deduplicado)
    pts = irrc[["name","node"]].drop_duplicates().sort_values(["name","node"])
    pts.to_csv(out_pts, index=False, encoding="utf-8")
    lg.info("IrrigationPoint.csv escrito: %s (filas=%d)", out_pts, len(pts))

    # (Opcional) VOLI por nodo (conservador: máximo por nodo)
    if args.out_node_voli:
        out_nv = root / args.out_node_voli
        out_nv.parent.mkdir(parents=True, exist_ok=True)
        if "voli" not in irr.columns:
            raise SystemExit("Irrigation.csv no tiene columna 'voli' (requerida para VOLI por nodo)")

        merged = pts.merge(irr[["name","voli"]], on="name", how="left")
        merged = merged.dropna(subset=["voli"])
        if merged.empty:
            lg.warning("No hay VOLI asociable (¿falta 'voli' o mapeos?). Omito salida.")
        else:
            out = (merged.assign(voli=lambda d: d["voli"].astype(float))
                         .groupby("node", as_index=False)["voli"].max()
                         .sort_values("node"))
            out.to_csv(out_nv, index=False, encoding="utf-8")
            lg.info("IrrigationNodeVoli.csv escrito: %s (nodos=%d)", out_nv, len(out))

if __name__ == "__main__":
    main()