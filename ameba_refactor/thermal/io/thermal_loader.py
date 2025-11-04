"""Carga de unidades térmicas con explicación detallada en español."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, TypedDict, Optional

import math
import pandas as pd

from .fuel_store import FuelStore


@dataclass(frozen=True)
class ThermalUnit:
    """Representa los parámetros operativos clave de una unidad térmica."""

    name: str
    busbar: str
    connected: bool
    pmax: float
    pmin: float
    heatrate_avg: float
    vomc_avg: float
    rampup: float
    rampdn: float
    minuptime: int
    mindntime: int
    startcost: float
    shutdncost: float
    uc_linear: bool
    faststart: bool
    fuel_name: str
    co2_emission: float
    unavailability: float
    is_ncre: bool
    forced_commit: bool
    initialstate: str
    initialtime: float


class ThermalPackage(TypedDict):
    """Estructura retornada por :func:`load_thermal_generators`."""

    units_df: pd.DataFrame
    fuel_store: FuelStore


def _to_bool(value: Any, default: bool = False) -> bool:
    """Convierte valores ambiguos a booleanos explícitos."""

    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    return str(value).strip().lower() in {"true", "1", "t", "yes", "y", "on", "si", "sí"}


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convierte a ``float`` con manejo de errores y ``NaN``."""

    try:
        result = float(value)
        return float(default) if math.isnan(result) else result
    except Exception:
        return float(default)


def _to_int(value: Any, default: int = 0) -> int:
    """Convierte a ``int`` devolviendo ``default`` ante errores."""

    try:
        return int(value)
    except Exception:
        return int(default)


def _require_unique(series: pd.Series, context: str) -> None:
    """Asegura que ``series`` no contenga nombres duplicados."""

    duplicates = series[series.duplicated()].unique().tolist()
    if duplicates:
        raise ValueError(f"[{context}] nombres duplicados: {duplicates}")


def load_thermal_generators(path_csv: Path, fuel_store: FuelStore) -> ThermalPackage:
    """Carga el catálogo térmico y lo devuelve como ``ThermalPackage``."""

    df = pd.read_csv(path_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "name": str(row.get("name")),
                "busbar": str(row.get("busbar", "")),
                "connected": _to_bool(row.get("connected", True)),
                "pmax": _to_float(row.get("pmax", 0.0)),
                "pmin": _to_float(row.get("pmin", 0.0)),
                "heatrate_avg": _to_float(row.get("heatrate_avg", row.get("heatrate", 0.0))),
                "vomc_avg": _to_float(row.get("vomc_avg", 0.0)),
                "rampup": _to_float(row.get("rampup", 1e9)),
                "rampdn": _to_float(row.get("rampdn", 1e9)),
                "minuptime": _to_int(row.get("minuptime", 0)),
                "mindntime": _to_int(row.get("mindntime", 0)),
                "startcost": _to_float(row.get("startcost", 0.0)),
                "shutdncost": _to_float(row.get("shutdncost", 0.0)),
                "uc_linear": _to_bool(row.get("uc_linear", False)),
                "faststart": _to_bool(row.get("faststart", False)),
                "fuel_name": str(row.get("fuel_name", "") or "").strip(),
                "co2_emission": _to_float(row.get("co2_emission", 0.0)),
                "unavailability": _to_float(row.get("unavailability", 0.0)),
                "is_ncre": _to_bool(row.get("is_ncre", False)),
                "forced_commit": _to_bool(row.get("forced_commit", False)),
                "initialstate": str(row.get("initialstate", "off") or "off").strip().lower(),
                "initialtime": _to_float(row.get("initialtime", 0.0)),
                "control_areas": str(row.get("control_areas", "")),
                "auxserv": str(row.get("auxserv", "")),
                "voltage": _to_float(row.get("voltage", 0.0)),
            }
        )

    units_df = pd.DataFrame(rows)

    _require_unique(units_df["name"], "ThermalGenerator")

    bad_bounds = units_df["pmax"] < units_df["pmin"]
    if bad_bounds.any():
        print(
            "[thermal_loader] WARNING: pmax < pmin en:\n",
            units_df.loc[bad_bounds, ["name", "pmin", "pmax"]],
        )

    missing_fuel = (units_df["fuel_name"].str.len() == 0).sum()
    if missing_fuel:
        print(f"[thermal_loader] WARNING: {missing_fuel} unidades sin 'fuel_name' definido.")

    return {"units_df": units_df, "fuel_store": fuel_store}


def build_variable_cost_by_block(
    units_df: pd.DataFrame,
    fuel_store: FuelStore,
    calendar_blocks_unique: pd.DataFrame,
    *,
    include_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Calcula costos variables por bloque ``(y, t)`` para cada unidad térmica."""

    include_columns = include_columns or []

    yt = calendar_blocks_unique[["y", "t"]].drop_duplicates().astype(int)
    yt["key"] = 1

    units = units_df.copy()
    units["key"] = 1

    merged = units.merge(yt, on="key").drop(columns="key")

    def _price(row: pd.Series) -> float:
        fuel = row["fuel_name"]
        if not fuel:
            return 0.0
        return float(fuel_store.price(fuel, int(row["y"]), int(row["t"])))

    merged["fuel_price"] = merged.apply(_price, axis=1)
    merged["var_cost"] = merged["vomc_avg"] + merged["heatrate_avg"] * merged["fuel_price"]

    columns = ["name", "y", "t", "fuel_price", "var_cost"]
    for column in include_columns:
        if column in merged.columns and column not in columns:
            columns.append(column)

    return merged[columns].sort_values(["name", "y", "t"]).reset_index(drop=True)
