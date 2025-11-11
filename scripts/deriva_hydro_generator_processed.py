# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
from pathlib import Path

RAW_DIR  = Path("data/raw")
PROC_DIR = Path("data/processed")

def _load_nodes():
    hn = pd.read_csv(PROC_DIR / "HydroNode.csv")
    assert {"name"}.issubset(hn.columns), "HydroNode.csv debe tener 'name'"
    return set(hn["name"].astype(str))

def _load_dams():
    dm = pd.read_csv(PROC_DIR / "Dam.csv")
    assert {"name"}.issubset(dm.columns), "Dam.csv debe tener 'name'"
    return set(dm["name"].astype(str))

def _load_connections():
    cn = pd.read_csv(PROC_DIR / "HydroConnection.csv") if (PROC_DIR/"HydroConnection.csv").exists() else pd.read_csv(RAW_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroConnection.csv")
    cols = set(cn.columns)
    # Soporta esquema raw (h_type,ini,end,...) o normalizado (ini_node,end_node,...)
    if {"h_type","ini","end"}.issubset(cols):
        cn = cn.rename(columns={"ini":"ini_node","end":"end_node"})
    assert {"ini_node","end_node"}.issubset(cn.columns), "HydroConnection(.csv) debe tener ini/end (o ini_node/end_node)"
    # nos quedamos con todas; el filtrado lo hacemos por pertenencia a sets
    cn["ini_node"] = cn["ini_node"].astype(str).str.strip()
    cn["end_node"] = cn["end_node"].astype(str).str.strip()
    return cn

def _load_hg_raw():
    hg = pd.read_csv(RAW_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGenerator.csv")
    assert "name" in hg.columns and "pmax" in hg.columns and "candidate" in hg.columns, \
        "HydroGenerator(raw) debe tener al menos name,pmax,candidate"
    out = hg[["name","pmax","candidate"]].copy()
    out["name"] = out["name"].astype(str)
    return out

def _load_rho_optional():
    rho_path = PROC_DIR / "HydroRho.csv"
    if not rho_path.exists():
        return {}
    df = pd.read_csv(rho_path)
    assert {"name","rho_mwh_per_hm3"}.issubset(df.columns), "HydroRho.csv debe tener name,rho_mwh_per_hm3"
    mp = {str(r.name): float(r.rho_mwh_per_hm3) for r in df.itertuples(index=False)}
    return mp

def main():
    nodes = _load_nodes()
    dams  = _load_dams()
    cn    = _load_connections()
    hg    = _load_hg_raw()
    rho_mp= _load_rho_optional()

    # Índices auxiliares
    # conexiones que involucran cada generador
    cn_by_ini = {}
    cn_by_end = {}
    for r in cn.itertuples(index=False):
        cn_by_ini.setdefault(r.ini_node, []).append(r.end_node)
        cn_by_end.setdefault(r.end_node, []).append(r.ini_node)

    rows = []
    warn_multi_node = []
    warn_multi_dam  = []
    warn_missing_rho= []

    for r in hg.itertuples(index=False):
        g = str(r.name)
        # ---- node
        candidates_node = []
        for end in cn_by_ini.get(g, []):
            if end in nodes:
                candidates_node.append(end)
        if not candidates_node:
            for ini in cn_by_end.get(g, []):
                if ini in nodes:
                    candidates_node.append(ini)
        node = None
        if candidates_node:
            node = candidates_node[0]
            if len(candidates_node) > 1:
                warn_multi_node.append({"gen": g, "candidates": candidates_node})

        # ---- dam (opcional)
        candidates_dam = []
        for end in cn_by_ini.get(g, []):
            if end in dams:
                candidates_dam.append(end)
        for ini in cn_by_end.get(g, []):
            if ini in dams:
                candidates_dam.append(ini)
        dam = None
        if candidates_dam:
            dam = candidates_dam[0]
            if len(candidates_dam) > 1:
                warn_multi_dam.append({"gen": g, "candidates": candidates_dam})

# ---- rho
        rho = rho_mp.get(g, None)
        if rho is None:
            rho = 1.0
            warn_missing_rho.append(g)

        # ---- candidate
        cand_val = getattr(r, "candidate", 0)
        try:
            if pd.isna(cand_val):
                cand = 0
            else:
                s = str(cand_val).strip().lower()
                if s in {"1","true","t","yes","y"}:
                    cand = 1
                elif s in {"0","false","f","no","n"}:
                    cand = 0
                else:
                    cand = int(float(cand_val)) if str(cand_val).replace('.','',1).isdigit() else 0
        except Exception:
            cand = 0

        rows.append({
            "name": g,
            "node": node if node is not None else "",
            "dam":  dam if dam  is not None else "",
            "rho_mwh_per_hm3": float(rho),
            "pmax": float(r.pmax),
            "candidate": cand
        })

    out = pd.DataFrame(rows, columns=["name","node","dam","rho_mwh_per_hm3","pmax","candidate"])
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROC_DIR / "HydroGenerator.csv", index=False, encoding="utf-8")

    print(f"[OK] HydroGenerator.csv escrito en {PROC_DIR/'HydroGenerator.csv'} ({len(out)} filas)")
    if warn_multi_node:
        print(f"[WARN] Generadores con múltiples posibles 'node': {len(warn_multi_node)}. Ej: {warn_multi_node[:3]}")
    if warn_multi_dam:
        print(f"[WARN] Generadores con múltiples posibles 'dam': {len(warn_multi_dam)}. Ej: {warn_multi_dam[:3]}")
    if warn_missing_rho:
        print(f"[WARN] {len(warn_missing_rho)} generadores sin rho definido. Se usó 1.0. Ej: {warn_missing_rho[:5]}")
        print("       Puedes crear data/processed/HydroRho.csv con columnas name,rho_mwh_per_hm3 para sobreescribir.")

if __name__ == "__main__":
    main()