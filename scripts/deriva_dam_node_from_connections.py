# -*- coding: utf-8 -*-
"""
Crea data/processed/Dam.csv a partir de:
- data/raw/Dam.csv                (sin 'node')
- data/raw/HydroConnection.csv    (para fallback)
- data/raw/HydroNode.csv          (PRIORIDAD: Dam es un nodo!)

Reglas:
1) Si Dam.name (normalizado) existe como nodo hídrico (normalizado), node = ese HydroNode.
2) Si no existe, busca en HydroConnection filas con end == Dam.name y toma ini como candidato de node
   SOLO si hay un candidato único; si hay múltiples o ninguno, deja node="".

Uso:
    python scripts/deriva_dam_node_from_connections.py
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
PROC = Path("data/processed")

DAM_RAW = RAW / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Dam.csv"
HC_RAW  = RAW / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroConnection.csv"
HN_RAW  = RAW / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroNode.csv"
DAM_OUT = PROC / "Dam.csv"

# Prefijos a ignorar al comparar nombres
PREFIXES = ("Emb_", "Dam_", "EMB_", "DAM_")

def _norm(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip()
    for p in PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    return s.casefold().strip().replace('"', '').replace("'", "")

def main():
    PROC.mkdir(parents=True, exist_ok=True)

    # --- Dam raw ---
    dm = pd.read_csv(DAM_RAW)
    need_dm = {"name","vmax","vmin","vini","vend"}
    miss = [c for c in need_dm if c not in dm.columns]
    if miss:
        raise ValueError(f"Dam.csv (raw) debe contener {need_dm}. Faltan: {miss}")
    dm["name"] = dm["name"].astype(str).str.strip()

    # --- HydroNode raw ---
    hn = pd.read_csv(HN_RAW)
    if "name" not in hn.columns:
        raise ValueError("HydroNode.csv debe contener columna 'name'.")
    hn["name"] = hn["name"].astype(str).str.strip()

    # Mapa de normalizados -> nombre real del nodo (conserva casing original)
    node_norm_to_real: dict[str, str] = {}
    for n in hn["name"]:
        node_norm_to_real[_norm(n)] = n

    # --- HydroConnection raw (fallback sólo si no hay match en nodos) ---
    hc = pd.read_csv(HC_RAW)
    need_hc = {"h_type","ini","end"}
    miss = [c for c in need_hc if c not in hc.columns]
    if miss:
        raise ValueError(f"HydroConnection.csv debe contener {need_hc}. Faltan: {miss}")

    hc["ini"] = hc["ini"].astype(str).str.strip()
    hc["end"] = hc["end"].astype(str).str.strip()

    # Construye índice end_norm -> lista de ini (respetando orden) para fallback
    end_to_inis: dict[str, list[str]] = {}
    for _, r in hc.iterrows():
        end_norm = _norm(r["end"])
        if not end_norm:
            continue
        end_to_inis.setdefault(end_norm, []).append(r["ini"])

    out_rows = []
    warn_multi, warn_missing, used_fallback = [], [], 0

    for _, r in dm.iterrows():
        dam_name = r["name"]
        dam_norm = _norm(dam_name)
        # 1) PRIORIDAD: el embalse es un nodo hídrico
        if dam_norm in node_norm_to_real:
            node_real = node_norm_to_real[dam_norm]
        else:
            # 2) FALLBACK: inferir desde conexiones end==dam
            inis = end_to_inis.get(dam_norm, [])
            if len(inis) == 1:
                node_real = inis[0]
                used_fallback += 1
            elif len(inis) > 1:
                node_real = ""
                warn_multi.append({"dam": dam_name, "candidates": inis[:5]})
            else:
                node_real = ""
                warn_missing.append(dam_name)

        out = dict(r)
        out["node"] = node_real
        out_rows.append(out)

    dm_out = pd.DataFrame(out_rows)

    # --- Logs
    print(f"[INFO] Embalses totales: {len(dm_out)}")
    matched = dm_out["node"].ne("").sum()
    print(f"[INFO] Dam→node por HydroNode directo: {matched - used_fallback}")
    print(f"[INFO] Dam→node por fallback (conexiones): {used_fallback}")
    if warn_multi:
        print(f"[WARN] {len(warn_multi)} embalses con múltiples candidatos por conexiones. Ej: {warn_multi[:3]}")
    if warn_missing:
        print(f"[WARN] {len(warn_missing)} embalses sin nodo en HydroNode y sin fallback por conexiones. Ej: {warn_missing[:5]}")

    # --- Guardar
    dm_out.to_csv(DAM_OUT, index=False, encoding="utf-8")
    print(f"[OK] Escrito {DAM_OUT}")

if __name__ == "__main__":
    main()