import pandas as pd
from pathlib import Path

def load_system(path_csv: Path) -> pd.DataFrame:
    """
    Carga el archivo CSV de configuración del sistema eléctrico
    y devuelve un DataFrame con una sola fila.
    """
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]

    # Seleccionar y renombrar columnas relevantes (si es necesario)
    req_cols = ["sbase", "busbar_ref", "interest_rate"]
    for col in req_cols:
        if col not in df.columns:
            df[col] = None  # Completar si faltan columnas

    # Aseguramos que hay sólo una fila válida
    return df[req_cols].head(1).copy()
