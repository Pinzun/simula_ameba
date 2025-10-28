# carga_hydrogenerator.py
from pathlib import Path
import pandas as pd

def load_hydro_generator(path: Path, reservoirs_df: pd.DataFrame, kappa_default: float = 1.0):
    """
    Identifica generadores hidro ROR (sin almacenamiento).
    Usa 'hydro_group_name' como nombre de la unidad (HG_*).

    Devuelve:
      - ROR: lista de HG_*
      - PmaxROR: dict HG_* -> MWh/h de potencia máxima *por hora*
      - kappa_ror: dict HG_* -> MWh/hm3 (eficiencia hidráulica)
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    # catálogo de embalses (Emb_*)
    emb_names = set(reservoirs_df["name"].astype(str).tolist())

    # tomar HG_* de HydroGenerator
    # si existe col 'hydro_group_name' úsala; si no, usa 'name'
    hg_col = "hydro_group_name" if "hydro_group_name" in df.columns else "name"
    df[hg_col] = df[hg_col].astype(str)

    # Consideraremos ROR los HG_* que NO sean embalses (Dam no lista generadores)
    # y que sean "connected == true" (si existe)
    if "connected" in df.columns:
        df = df[df["connected"].astype(str).str.lower().isin(["true", "1"])].copy()

    # Pmax por hora (MW). En el bloque multiplicarás por horas del bloque si lo deseas acotar por potencia.
    PmaxROR = {}
    kappa_ror = {}

    for _, r in df.iterrows():
        gname = r[hg_col]
        if not gname.startswith("HG_"):
            continue
        pmax = float(r.get("pmax", 0) or 0.0)  # MW
        eff  = float(r.get("eff", 1) or 1.0)   # sin unidad, factor
        PmaxROR[gname] = max(0.0, pmax)        # potencia tope
        # κ: MWh/hm3. MVP: usa kappa_default y opcionalmente ajusta por eff.
        kappa_ror[gname] = max(0.0, kappa_default * eff)

    ROR = sorted(PmaxROR.keys())
    return ROR, PmaxROR, kappa_ror