# scripts/repair_hydro_nodes.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

def read_conn(path: Path) -> pd.DataFrame:
    cn = pd.read_csv(path)
    if {"ini_node","end_node"}.issubset(cn.columns):
        cn = cn.rename(columns={"ini_node":"ini", "end_node":"end"})
    elif {"ini","end"}.issubset(cn.columns):
        pass
    else:
        raise ValueError("HydroConnection.csv sin columnas ini/end ni ini_node/end_node")
    cn["ini"] = cn["ini"].astype(str).str.strip()
    cn["end"] = cn["end"].astype(str).str.strip()
    return cn[["ini","end"]]

def main():
    base = Path(__file__).parent.parent
    proc = base / "data" / "processed"

    hn_path  = proc / "HydroNode.csv"
    dm_path  = proc / "Dam.csv"
    hg_path  = proc / "HydroGenerator.csv"          # el 'processed' que generaste
    cn_path  = proc / "HydroConnection.csv"

    # 1) nodos actuales
    if hn_path.exists():
        hn = pd.read_csv(hn_path)
        if "name" not in hn.columns:
            raise ValueError("HydroNode.csv debe tener columna 'name'")
        current = set(hn["name"].astype(str).str.strip())
    else:
        hn = pd.DataFrame(columns=["name"])
        current = set()

    # 2) dam.node
    add = set()
    if dm_path.exists():
        dm = pd.read_csv(dm_path)
        if "node" in dm.columns:
            add |= set(dm["node"].astype(str).str.strip())

        # si decides que cada embalse también debe ser un nodo (útil para diagramas):
        if "name" in dm.columns:
            add |= set(dm["name"].astype(str).str.strip())

    # 3) hydro generators -> node
    if hg_path.exists():
        hg = pd.read_csv(hg_path)
        if "node" in hg.columns:
            add |= set(hg["node"].astype(str).str.strip())

    # 4) conexiones ini/end
    if cn_path.exists():
        cn = read_conn(cn_path)
        add |= set(cn["ini"])
        add |= set(cn["end"])

    # 5) limpia vacíos y duplicados
    add = {x for x in add if x and x.lower() != "nan"}
    missing = sorted(add - current)

    if missing:
        out = pd.concat([hn, pd.DataFrame({"name": missing})], ignore_index=True)
        out = out.drop_duplicates(subset=["name"]).sort_values("name").reset_index(drop=True)
        hn_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(hn_path, index=False, encoding="utf-8")
        print(f"[OK] HydroNode.csv actualizado (+{len(missing)} nuevos).")
    else:
        print("[OK] HydroNode.csv ya estaba completo (no se agregaron nodos).")

if __name__ == "__main__":
    main()