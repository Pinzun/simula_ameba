# carga_hydrogroup.py
import pandas as pd
from pathlib import Path

def load_hydrogroup(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df[df["name"].astype(str).str.startswith("HG_")].copy()
    # Tipos
    df["start_time"] = pd.to_datetime(df["start_time"], format="%Y-%m-%d-%H:%M", errors="coerce")
    df["end_time"]   = pd.to_datetime(df["end_time"],   format="%Y-%m-%d-%H:%M", errors="coerce")
    df["hg_sp_min"]  = pd.to_numeric(df["hg_sp_min"], errors="coerce").fillna(0.0)
    df["hg_sp_max"]  = pd.to_numeric(df["hg_sp_max"], errors="coerce")
    # 99999 → “sin tope” (infinito)
    df["hg_sp_max"]  = df["hg_sp_max"].fillna(float("inf"))
    return df[["name","start_time","end_time","hg_sp_min","hg_sp_max"]]