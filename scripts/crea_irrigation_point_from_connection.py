# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

def main():
    root = Path(__file__).parent.parent
    raw_conn = root / "data" / "raw" / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroConnection.csv"
    out_points = root / "data" / "processed" / "IrrigationPoint.csv"

    df = pd.read_csv(raw_conn)
    req = {"h_type","ini","end"}
    if not req.issubset(df.columns):
        raise ValueError(f"HydroConnection.csv debe contener {req}")

    irr = df[df["h_type"].str.lower()=="irrigation"].copy()
    if irr.empty:
        print("WARN | No hay conexiones de riego en HydroConnection.csv")
        out_points.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["name","node"]).to_csv(out_points, index=False, encoding="utf-8")
        return

    # ‘end’ es el punto de riego; mapeamos ‘name=end’, ‘node=ini’ (el nodo hídrico donde se extrae)
    pts = irr[["ini","end"]].drop_duplicates().rename(columns={"end":"name","ini":"node"})
    pts["name"] = pts["name"].astype(str).str.strip()
    pts["node"] = pts["node"].astype(str).str.strip()

    out_points.parent.mkdir(parents=True, exist_ok=True)
    pts.to_csv(out_points, index=False, encoding="utf-8",)
    print(f"INFO | IrrigationPoint.csv escrito en {out_points} ({len(pts)} puntos)")

if __name__ == "__main__":
    main()