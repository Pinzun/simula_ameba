# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Tuple, Dict, List
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

TIME_FMT = "%Y-%m-%d-%H:%M"
TZ = "America/Santiago"

# ---- Helpers básicos ---------------------------------------------------------
def require_columns(df: pd.DataFrame, cols: List[str], name: str = "DataFrame") -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise AssertionError(f"[{name}] Faltan columnas: {missing}. Presentes: {list(df.columns)}")

def assert_unique(df: pd.DataFrame, cols: List[str], name: str = "DataFrame") -> None:
    if df.duplicated(subset=cols).any():
        raise AssertionError(f"[{name}] Filas duplicadas en claves {cols}.")

def _parse_dt_strict(s: str, tz: str) -> datetime:
    for fmt in ("%Y-%m-%d-%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=ZoneInfo(tz))
        except ValueError:
            pass
    dt = pd.to_datetime(s)
    if dt.tzinfo is None:
        dt = dt.tz_localize(ZoneInfo(tz))
    return dt.to_pydatetime()

# ---- Stages ------------------------------------------------------------------
def load_stages(path: str | Path, tz: str = TZ) -> pd.DataFrame:
    """
    Lee Stages.csv con encabezado:
      s_id,start_time,end_time,num_blocks
    Devuelve: ['s_id','start_time','end_time','num_blocks','start_ts','end_ts']
    """
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    require_columns(df, ["s_id", "start_time", "end_time", "num_blocks"], name="Stages")

    df["s_id"] = df["s_id"].astype(int)
    df["start_time"] = df["start_time"].astype(str)
    df["end_time"]   = df["end_time"].astype(str)
    df["num_blocks"] = df["num_blocks"].astype(int)

    start = df["start_time"].map(lambda s: _parse_dt_strict(s, tz))
    end   = df["end_time"].map(lambda s: _parse_dt_strict(s, tz))

    if (end <= start).any():
        bad = df.loc[end <= start, "s_id"].tolist()
        raise AssertionError(f"[Stages] Hay stages con end<=start: {bad}")

    out = df.copy()
    out["start_ts"] = start.map(lambda x: int(x.timestamp()))
    out["end_ts"]   = end.map(lambda x: int(x.timestamp()))
    assert_unique(out, ["s_id"], name="Stages")
    return out.sort_values("s_id").reset_index(drop=True)

# ---- Blocks (detalle horario + agregación a bloque 2h) -----------------------
def load_blocks(stages_df: pd.DataFrame, blocks_csv: str | Path) -> pd.DataFrame:
    import pandas as pd

    raw = pd.read_csv(blocks_csv)
    raw.columns = [c.strip() for c in raw.columns]

    # Normaliza nombres mínimos
    if "y" in raw.columns and "stage" not in raw.columns:
        raw = raw.rename(columns={"y": "stage"})
    if "t" in raw.columns and "block" not in raw.columns:
        raw = raw.rename(columns={"t": "block"})
    if "time_str" not in raw.columns and "time" in raw.columns:
        raw["time_str"] = raw["time"].astype(str)
    elif "time_str" not in raw.columns:
        raise AssertionError("[Blocks] Falta columna time/time_str")

    # Limpia y parsea tiempo
    raw["time_str"] = raw["time_str"].astype(str).str.strip()
    raw["time"] = pd.to_datetime(raw["time_str"], format="%Y-%m-%d-%H:%M", errors="raise")

    # Chequea unicidad por hora (opcional pero útil)
    # Cada hora debería aparecer una sola vez por (stage,block)
    if raw.duplicated(subset=["stage","block","time"]).any():
        # Si ocurre aquí, el CSV sí trae duplicados (en mi revisión no fue el caso)
        dups = raw[raw.duplicated(subset=["stage","block","time"], keep=False)] \
                 .sort_values(["stage","block","time"])
        raise AssertionError("[Blocks] El CSV trae duplicados por (stage,block,time). Revísalos:\n"
                             + dups.head(20).to_string())

    # (Si tu flujo hace algún merge para inferir stage/block desde 'time',
    #  usa validate='m:1' para asegurar que cada hora mapea a un único (stage,block))
    # ejemplo:
    # mapa = ...  # columnas: time_str, stage, block (único por time_str)
    # assert not mapa.duplicated("time_str").any(), "mapa time_str no unívoco"
    # raw = raw.merge(mapa[["time_str","stage","block"]], on="time_str", how="left", validate="m:1")

    # Ordena y devuelve solo lo necesario
    out = raw[["stage","block","time","time_str"]].drop_duplicates()
    out = out.sort_values(["stage","block","time"]).reset_index(drop=True)
    return out