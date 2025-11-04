# scripts/diagnose_model_inputs.py
from pathlib import Path
import pandas as pd

MI = Path("/home/pablo/projects/simula_ameba/data/model_inputs")

FILES = {
    "branches": "branches.csv",
    "busbars": "busbars.csv",
    "system": "system.csv",
    "blocks": "calendar_blocks.csv",       # <-- en tu carpeta
    "hours": "calendar_hours.csv",         # <-- en tu carpeta
    "demand_wide_block": "demand_by_block_wide.csv",
    "pv_units": "plants_pv.csv",
    "wind_units": "plants_wind.csv",
    "thermal_units": "thermal_units_df.csv",
    "inflow_block_hm3": "inflow_block_hm3.csv",
    "ess_assets": "ess_assets.csv",
}

def quick_stats(name, fname):
    p = MI / fname
    if not p.exists():
        print(f"✗ {name}: NO FILE ({fname})")
        return None
    try:
        df = pd.read_csv(p)
    except Exception as e:
        print(f"✗ {name}: error leyendo {fname}: {e}")
        return None
    n, m = df.shape
    print(f"✓ {name}: {fname} -> {n} filas, {m} cols")
    print("  columnas:", list(df.columns)[:8], "..." if m>8 else "")
    if n>0:
        for c in df.columns[:5]:
            if pd.api.types.is_numeric_dtype(df[c]):
                print(f"  {c}: min={df[c].min()} max={df[c].max()} sum={df[c].sum()}")
                break
    return df

def main():
    dfs = {}
    for k, f in FILES.items():
        dfs[k] = quick_stats(k, f)

    # chequeos específicos
    dm = dfs.get("demand_wide_block")
    if dm is not None and not dm.empty:
        id_cols = [c for c in ("stage_id","block_id") if c in dm.columns]
        bus_cols = [c for c in dm.columns if c not in id_cols]
        if bus_cols:
            total = dm[bus_cols].sum(numeric_only=True).sum()
            print(f"\n∑ Demanda total (todas las columnas bus): {total}")
            # mira algunos bloques
            if id_cols:
                sample = dm[id_cols + bus_cols[:5]].head(3)
                print("\nMuestra demanda (primeros 3 registros, 5 buses):")
                print(sample.to_string(index=False))

if __name__ == "__main__":
    main()
