# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

def main():
    root = Path(__file__).parent.parent
    blocks = pd.read_csv(root / "data" / "processed" / "blocks.csv")
    pts    = pd.read_csv(root / "data" / "processed" / "IrrigationPoint.csv")

    for col in ["stage","block"]:
        if col not in blocks.columns:
            raise ValueError("blocks.csv debe tener columnas stage y block")
    if "name" not in pts.columns:
        raise ValueError("IrrigationPoint.csv debe tener columna name")

    blocks = blocks[["stage","block"]].drop_duplicates()
    blocks["stage"] = blocks["stage"].astype(int)
    blocks["block"] = blocks["block"].astype(int)

    if pts.empty:
        print("WARN | IrrigationPoint.csv vacío; genero archivo de riego vacío.")
        out = pd.DataFrame(columns=["name","stage","block","irr_hm3"])
    else:
        pts = pts[["name"]].drop_duplicates()
        pts["key"] = 1
        blocks["key"] = 1
        out = pts.merge(blocks, on="key").drop(columns="key")
        out["irr_hm3"] = 0.0  # placeholder: sin requerimiento (lo ajustaremos luego)

    out_path = root / "data" / "processed" / "Irrigation_qm3.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8")
    print(f"INFO | Irrigation_qm3.csv escrito en {out_path} ({len(out)} filas)")

if __name__ == "__main__":
    main()