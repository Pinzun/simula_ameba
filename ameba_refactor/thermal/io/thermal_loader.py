# -*- coding: utf-8 -*-
# thermal/io/thermal_loader.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, TypedDict, Optional, Tuple
import pandas as pd
import math

from .fuel_store import FuelStore  # usa la clase centralizada

# --- Representación KISS para el modelador DC/UC ---
@dataclass(frozen=True)
class ThermalUnit:
    name: str
    busbar: str
    connected: bool
    pmax: float
    pmin: float
    heatrate_avg: float      # (p. ej. GJ/MWh_e o MMBtu/MWh_e según tu convención)
    vomc_avg: float          # $/MWh_e
    rampup: float            # MW/hora
    rampdn: float            # MW/hora
    minuptime: int           # horas
    mindntime: int           # horas
    startcost: float         # $
    shutdncost: float        # $
    uc_linear: bool
    faststart: bool
    fuel_name: str
    co2_emission: float      # tCO2/MWh_e (si la columna existe)
    unavailability: float    # fracción [0..1] (si aplica)
    is_ncre: bool
    forced_commit: bool
    initialstate: str        # "on"/"off"
    initialtime: float       # horas

class ThermalPackage(TypedDict):
    units_df: pd.DataFrame     # tabla plana de unidades térmicas
    fuel_store: FuelStore      # para consulta de precios por bloque

# ----------------- helpers simples -----------------
def _to_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    s = str(x).strip().lower()
    return s in {"true", "1", "t", "yes", "y", "on", "si", "sí"}

def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v):
            return float(default)
        return v
    except Exception:
        return float(default)

def _to_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return int(default)

def _require_unique(series: pd.Series, where: str) -> None:
    dups = series[series.duplicated()].unique().tolist()
    if dups:
        raise ValueError(f"[{where}] nombres duplicados: {dups}")

# ----------------- loader principal -----------------
def load_thermal_generators(path_csv: Path, fuel_store: FuelStore) -> ThermalPackage:
    """
    Lee ThermalGenerator.csv y devuelve:
      - units_df: DataFrame normalizado para el modelador
      - fuel_store: tienda de combustibles (inyectada)
    Columnas toleradas (faltantes se rellenan con defaults razonables):
      name,busbar,connected,pmax,pmin,heatrate_avg|heatrate,vomc_avg,
      rampup,rampdn,minuptime,mindntime,startcost,shutdncost,
      uc_linear,faststart,fuel_name,co2_emission,unavailability,
      is_ncre,forced_commit,initialstate,initialtime
    """
    df = pd.read_csv(path_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        rows.append({
            "name":           str(r.get("name")),
            "busbar":         str(r.get("busbar", "")),
            "connected":      _to_bool(r.get("connected", True)),
            "pmax":           _to_float(r.get("pmax", 0.0)),
            "pmin":           _to_float(r.get("pmin", 0.0)),
            "heatrate_avg":   _to_float(r.get("heatrate_avg", r.get("heatrate", 0.0))),
            "vomc_avg":       _to_float(r.get("vomc_avg", 0.0)),
            "rampup":         _to_float(r.get("rampup", 1e9)),
            "rampdn":         _to_float(r.get("rampdn", 1e9)),
            "minuptime":      _to_int(r.get("minuptime", 0)),
            "mindntime":      _to_int(r.get("mindntime", 0)),
            "startcost":      _to_float(r.get("startcost", 0.0)),
            "shutdncost":     _to_float(r.get("shutdncost", 0.0)),
            "uc_linear":      _to_bool(r.get("uc_linear", False)),
            "faststart":      _to_bool(r.get("faststart", False)),
            "fuel_name":      str(r.get("fuel_name", "") or "").strip(),
            "co2_emission":   _to_float(r.get("co2_emission", 0.0)),
            "unavailability": _to_float(r.get("unavailability", 0.0)),
            "is_ncre":        _to_bool(r.get("is_ncre", False)),
            "forced_commit":  _to_bool(r.get("forced_commit", False)),
            "initialstate":   str(r.get("initialstate", "off") or "off").strip().lower(),
            "initialtime":    _to_float(r.get("initialtime", 0.0)),
            # opcionales que a futuro podrías usar:
            "control_areas":  str(r.get("control_areas", "")),
            "auxserv":        str(r.get("auxserv", "")),
            "voltage":        _to_float(r.get("voltage", 0.0)),
        })

    units_df = pd.DataFrame(rows)

    # Chequeos suaves
    _require_unique(units_df["name"], "ThermalGenerator")
    bad_bounds = units_df["pmax"] < units_df["pmin"]
    if bad_bounds.any():
        print("[thermal_loader] WARNING: pmax < pmin en:\n",
              units_df.loc[bad_bounds, ["name", "pmin", "pmax"]])
    missing_fuel = (units_df["fuel_name"].str.len() == 0).sum()
    if missing_fuel:
        print(f"[thermal_loader] WARNING: {missing_fuel} unidades sin 'fuel_name' definido.")

    return {"units_df": units_df, "fuel_store": fuel_store}

# ----------------- helper opcional -----------------
def build_variable_cost_by_block(
    units_df: pd.DataFrame,
    fuel_store: FuelStore,
    calendar_blocks_unique: pd.DataFrame,
    *,
    include_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Devuelve un DF largo con el costo variable ($/MWh_e) por bloque (y,t) de cada unidad:
      columnas: ['name','y','t','fuel_price','var_cost', ...opcionales]
    Fórmula básica (sin inventar extras): var_cost = vomc_avg + heatrate_avg * fuel_price(y,t)
    - 'calendar_blocks_unique' debe traer las combinaciones únicas (y,t). Ej.: blocks_df[['y','t']].drop_duplicates()
    """
    if include_columns is None:
        include_columns = []

    # Combina (producto cartesiano) unidades x (y,t)
    yt = calendar_blocks_unique[["y", "t"]].drop_duplicates().astype(int)
    yt["key"] = 1
    uu = units_df.copy()
    uu["key"] = 1
    m = uu.merge(yt, on="key").drop(columns="key")

    # Precio por bloque usando FuelStore
    def _price(row: pd.Series) -> float:
        fuel = row["fuel_name"]
        if not fuel:
            return 0.0
        return float(fuel_store.price(fuel, int(row["y"]), int(row["t"])))

    m["fuel_price"] = m.apply(_price, axis=1)
    m["var_cost"] = m["vomc_avg"] + m["heatrate_avg"] * m["fuel_price"]

    cols = ["name", "y", "t", "fuel_price", "var_cost"]
    for c in include_columns:
        if c in m.columns and c not in cols:
            cols.append(c)

    return m[cols].sort_values(["name", "y", "t"]).reset_index(drop=True)