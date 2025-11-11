# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

def main():
    root = Path(__file__).parent.parent
    raw_cat = root / "data" / "raw" / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Irrigation.csv"      # catálogo original
    out_cat = root / "data" / "processed" / "Irrigation.csv"

    if raw_cat.exists():
        df = pd.read_csv(raw_cat)
        # Normaliza y deja sólo lo que usamos ahora: name, voli
        need = {"name", "voli"}
        if not need.issubset(df.columns):
            raise ValueError(f"Irrigation.csv (raw) debe contener columnas {need}")
        out = df[["name", "voli"]].copy()
    else:
        # No hay catálogo raw: construimos uno placeholder a partir de IrrigationPoint
        ip = root / "data" / "processed" / "IrrigationPoint.csv"
        if not ip.exists():
            raise FileNotFoundError("No existe data/processed/IrrigationPoint.csv para generar placeholder de VOLI.")
        pts = pd.read_csv(ip)
        if "name" not in pts.columns:
            raise ValueError("IrrigationPoint.csv debe tener columna 'name'")
        out = pts[["name"]].drop_duplicates().copy()
        out["voli"] = 0.0

    out_cat.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_cat, encoding="utf-8", index=False)
    print(f"INFO | Irrigation.csv escrito en {out_cat} (filas={len(out)})")

if __name__ == "__main__":
    main()