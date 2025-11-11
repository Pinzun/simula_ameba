# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

def main():
    root = Path(__file__).parent.parent
    raw_hg = root / "data" / "raw" / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGroup.csv"
    proc_hg = root / "data" / "processed" / "HydroGroup.csv"
    proc_hgen = root / "data" / "processed" / "HydroGenerator.csv"

    if raw_hg.exists():
        df = pd.read_csv(raw_hg)
        need = {"name", "hg_sp_min", "hg_sp_max"}
        if not need.issubset(df.columns):
            # normaliza si viene con otras columnas
            cols = [c for c in df.columns if c.lower() in {"name","hg_sp_min","hg_sp_max"}]
            if not {"name"}.issubset(set(cols)):
                raise ValueError("HydroGroup.csv (raw) debe contener al menos 'name' y límites min/max.")
            df = df.rename(columns={
                "HG_MIN":"hg_sp_min", "HG_MAX":"hg_sp_max",
                "hg_min":"hg_sp_min", "hg_max":"hg_sp_max"
            })
            for c,defv in (("hg_sp_min",0.0),("hg_sp_max",99999.0)):
                if c not in df.columns: df[c]=defv
        out = df[["name","hg_sp_min","hg_sp_max"]].drop_duplicates().copy()
    else:
        # Deriva desde HydroGenerator.csv
        if not proc_hgen.exists():
            raise FileNotFoundError("No existe data/processed/HydroGenerator.csv para derivar grupos.")
        hg = pd.read_csv(proc_hgen)
        grp_col = "hydro_group_name" if "hydro_group_name" in hg.columns else None
        if not grp_col:
            # no hay grupos; crea un placeholder vacío
            out = pd.DataFrame(columns=["name","hg_sp_min","hg_sp_max"])
        else:
            groups = (
                hg[[grp_col]]
                .dropna()
                .assign(name=lambda d: d[grp_col].astype(str).str.strip())
                .query("name != ''")
                .drop_duplicates(subset=["name"])
            )
            if groups.empty:
                out = pd.DataFrame(columns=["name","hg_sp_min","hg_sp_max"])
            else:
                out = groups[["name"]].copy()
                out["hg_sp_min"] = 0.0
                out["hg_sp_max"] = 99999.0

    proc_hg.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(proc_hg, encoding="utf-8", index=False)
    print(f"INFO | HydroGroup.csv escrito en {proc_hg} (filas={len(out)})")

if __name__ == "__main__":
    main()