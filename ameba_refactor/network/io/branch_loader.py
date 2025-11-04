import pandas as pd
from pathlib import Path

def load_branches(path_csv: Path) -> pd.DataFrame:
    """
    Carga el CSV de ramas y devuelve un DataFrame limpio con las columnas mínimas:
    name, bus_i, bus_j, x, fmax_ab, fmax_ba, dc, losses
    """
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]

    # Filtrar ramas conectadas, si existe la columna
    if "connected" in df.columns:
        df = df[df["connected"] == True].copy()

    # Renombrar columnas si es necesario, según lo que usa tu modelo
    rename_map = {
        "busbari": "bus_i",
        "busbarf": "bus_j",
        "max_flow": "fmax_ab",
        "max_flow_reverse": "fmax_ba"
    }
    df = df.rename(columns=rename_map)

    # Seleccionar solo las columnas requeridas (agregamos valores por defecto si faltan)
    req_cols = ['name', 'bus_i', 'bus_j', 'x', 'fmax_ab', 'fmax_ba', 'dc', 'losses']
    for col in req_cols:
        if col not in df.columns:
            df[col] = 0 if col in ['fmax_ab', 'fmax_ba', 'x'] else False

    # Ordenar y devolver
    return df[req_cols].copy()
