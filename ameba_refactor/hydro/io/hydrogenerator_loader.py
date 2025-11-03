# hydro/io/hydrogenerator_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import math

from hydro.core.types import HydroGeneratorRow, GeneratorsCatalog

# ------------------- Helpers -------------------
def _require_columns(df: pd.DataFrame, cols: List[str], tag: str) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"[{tag}] faltan columnas: {miss}. Presentes: {list(df.columns)}")

def _assert_unique(df: pd.DataFrame, col: str, tag: str) -> None:
    if df[col].duplicated().any():
        dups = df.loc[df[col].duplicated(), col].tolist()
        raise ValueError(f"[{tag}] valores duplicados en '{col}': {sorted(set(dups))[:10]}")

def _to_dt_strict(s: Any, tag: str, col: str) -> pd.Timestamp:
    dt = pd.to_datetime(s, format="%Y-%m-%d-%H:%M", errors="coerce")
    if pd.isna(dt):
        raise ValueError(f"[{tag}] {col} inválido: {s!r} (esperado '%Y-%m-%d-%H:%M')")
    return dt

def _to_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    s = str(x).strip().lower()
    return s in {"true","1","t","yes","y","si","sí"}

def _to_float(x: Any, default: float = 0.0) -> float:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    try:
        return float(x)
    except Exception:
        return default

# ------------------- Loader -------------------
def load_hydrogenerator(
    path: Path,
    r_names: Optional[List[str]] = None,   # reservado para validaciones cruzadas futuras
    ror_prefix: str = "HG_"
) -> Tuple[List[HydroGeneratorRow], GeneratorsCatalog]:
    """
    Lee HydroGenerator.csv y devuelve:
      - Lista de HydroGeneratorRow (uno por fila de entrada)
      - GeneratorsCatalog agregado a nivel de 'hydro_group_name'

    Requeridas:
      name,start_time,end_time,report,connected,hydro_group_name,pmax,pmin,eff,vomc_avg
    Opcionales:
      busbar,use_pump_mode,pmax_pump,pmin_pump
    """
    tag = "HydroGenerator"
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    _require_columns(df,
        ["name","start_time","end_time","report","connected",
         "hydro_group_name","pmax","pmin","eff","vomc_avg"], tag)
    _assert_unique(df, "name", tag)

    # Parseo estricto de fechas
    df["start_time"] = df["start_time"].map(lambda s: _to_dt_strict(s, tag, "start_time"))
    df["end_time"]   = df["end_time"].map(lambda s: _to_dt_strict(s, tag, "end_time"))

    # Normalizaciones de tipos/campos
    df["report"]         = df["report"].map(lambda x: _to_bool(x, True))
    df["connected"]      = df["connected"].map(lambda x: _to_bool(x, True))
    if "use_pump_mode" in df.columns:
        df["use_pump_mode"] = df["use_pump_mode"].map(lambda x: _to_bool(x, False))
    else:
        df["use_pump_mode"] = False

    # Opcionales numéricos
    for opt in ("pmax_pump","pmin_pump","vomc_avg","eff","pmax","pmin"):
        if opt in df.columns:
            df[opt] = df[opt].map(lambda x: _to_float(x, 0.0))
        else:
            df[opt] = 0.0

    # Opcional texto
    if "busbar" not in df.columns:
        df["busbar"] = None

    # --------- Rows (uno por unidad declarada) ---------
    rows: List[HydroGeneratorRow] = []
    for _, r in df.iterrows():
        rows.append(HydroGeneratorRow(
            name=str(r["name"]),
            start_time=r["start_time"].to_pydatetime(),
            end_time=r["end_time"].to_pydatetime(),
            report=bool(r["report"]),
            connected=bool(r["connected"]),
            busbar=(None if pd.isna(r["busbar"]) else str(r["busbar"])),
            hydro_group_name=(None if pd.isna(r["hydro_group_name"]) else str(r["hydro_group_name"])),
            use_pump_mode=bool(r["use_pump_mode"]),
            pmax=float(r["pmax"]),
            pmin=float(r["pmin"]),
            pmax_pump=float(r.get("pmax_pump", 0.0)),
            pmin_pump=float(r.get("pmin_pump", 0.0)),
            eff=float(r.get("eff", 1.0)),
            vomc_avg=float(r.get("vomc_avg", 0.0)),
        ))

    # --------- Catálogo agregado por 'hydro_group_name' ---------
    # Filtra filas con grupo válido
    grp_df = df.loc[df["hydro_group_name"].notna()].copy()
    grp_df["hydro_group_name"] = grp_df["hydro_group_name"].astype(str)

    # Sumar pmax/pmin por grupo; usar promedio de eff como kappa_hg (MVP)
    agg = grp_df.groupby("hydro_group_name").agg(
        pmax=("pmax","sum"),
        pmin=("pmin","sum"),
        kappa=("eff","mean")
    ).reset_index()

    HG_all: List[str] = agg["hydro_group_name"].tolist()
    PmaxHG: Dict[str, float] = dict(zip(agg["hydro_group_name"], agg["pmax"]))
    PminHG: Dict[str, float] = dict(zip(agg["hydro_group_name"], agg["pmin"]))
    kappa_hg: Dict[str, float] = dict(zip(agg["hydro_group_name"], agg["kappa"]))

    # ROR por prefijo (ajústalo si cambias convención)
    ROR: List[str] = sorted([g for g in HG_all if g.startswith(ror_prefix)])

    cat = GeneratorsCatalog(
        HG_all=sorted(HG_all),
        PmaxHG=PmaxHG,
        PminHG=PminHG,
        kappa_hg=kappa_hg,
        ROR=ROR
    )
    return rows, cat