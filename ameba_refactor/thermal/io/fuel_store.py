"""Gestor de combustibles para unidades térmicas con comentarios extensos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List

import math
import pandas as pd


def _require_columns(df: pd.DataFrame, cols: List[str], tag: str) -> None:
    """Verifica que ``df`` contenga las columnas ``cols`` y lanza error descriptivo."""

    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"[{tag}] faltan columnas: {missing}. Presentes: {list(df.columns)}")


def _to_bool(value: Any, default: bool = False) -> bool:
    """Normaliza valores ambiguos (texto/número) a booleanos explícitos."""

    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    normalized = str(value).strip().lower()
    return normalized in {"true", "1", "t", "yes", "y", "si", "sí"}


def _to_dt_strict(value: Any, tag: str, column: str) -> pd.Timestamp:
    """Convierte ``value`` a ``Timestamp`` validando el formato ``%Y-%m-%d-%H:%M``."""

    ts = pd.to_datetime(value, format="%Y-%m-%d-%H:%M", errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"[{tag}] {column} inválido: {value!r} (esperado '%Y-%m-%d-%H:%M')")
    return ts


@dataclass(frozen=True)
class FuelSpec:
    """Describe un combustible individual tal como aparece en ``Fuel.csv``."""

    name: str
    fuel_type: str
    base_price: float  # Precio de respaldo si no existe serie temporal
    consider_avail: bool


class FuelStore:
    """Mantiene catálogos de combustibles y precios promedio por bloque."""

    def __init__(self, specs: Dict[str, FuelSpec], price_by_t: Dict[Tuple[int, int, str], float]):
        self.specs = specs
        self.price_by_t = price_by_t

    @classmethod
    def from_csv(
        cls,
        path_fuel_csv: Path,
        path_price_csv: Path,
        calendar_blocks: pd.DataFrame,
    ) -> "FuelStore":
        """Construye ``FuelStore`` a partir de los archivos estándar del modelo."""

        # ---------------------------- Fuel.csv ----------------------------
        tag_fuel = "Fuel.csv"
        fuel_df = pd.read_csv(path_fuel_csv)
        fuel_df.columns = [c.strip().lower() for c in fuel_df.columns]
        _require_columns(fuel_df, ["name"], tag_fuel)

        specs: Dict[str, FuelSpec] = {}
        for _, row in fuel_df.iterrows():
            name = str(row["name"])
            specs[name] = FuelSpec(
                name=name,
                fuel_type=str(row.get("fuel_type", "")),
                base_price=float(row.get("fuel_price", 0.0) or 0.0),
                consider_avail=_to_bool(row.get("consider_availability"), False),
            )

        # ------------------------- fuel_price.csv -------------------------
        tag_price = "fuel_price.csv"
        price_df = pd.read_csv(path_price_csv)
        price_df.columns = [c.strip() for c in price_df.columns]
        _require_columns(price_df, ["time"], tag_price)

        price_df["time_ts"] = price_df["time"].map(lambda val: _to_dt_strict(val, tag_price, "time"))

        price_columns = [c for c in price_df.columns if c not in {"time", "time_ts", "scenario"}]
        if not price_columns:
            raise ValueError(f"[{tag_price}] se esperaban columnas de precio (ej. 'Fuel_Gas').")

        melted = price_df.melt(
            id_vars=["time_ts"],
            value_vars=price_columns,
            var_name="fuel",
            value_name="price",
        ).dropna(subset=["price"])

        # ---------------------- Calendar Blocks ---------------------------
        tag_cal = "calendar_blocks"
        cb = calendar_blocks.copy()
        if "time_str" in cb.columns:
            cb["time_ts"] = cb["time_str"].map(lambda val: _to_dt_strict(val, tag_cal, "time_str"))
        elif "time" in cb.columns:
            cb["time_ts"] = cb["time"].map(lambda val: _to_dt_strict(val, tag_cal, "time"))
        else:
            raise ValueError(f"[{tag_cal}] falta 'time_str' o 'time'.")

        _require_columns(cb, ["y", "t", "time_ts"], tag_cal)
        cb = cb[["time_ts", "y", "t"]].drop_duplicates()

        merged = melted.merge(cb, on="time_ts", how="left")
        merged = merged.loc[merged["y"].notna() & merged["t"].notna()].copy()
        merged["y"] = merged["y"].astype(int)
        merged["t"] = merged["t"].astype(int)
        merged["fuel"] = merged["fuel"].astype(str)
        merged["price"] = merged["price"].astype(float)

        aggregated = merged.groupby(["y", "t", "fuel"], as_index=False)["price"].mean()

        price_by_t: Dict[Tuple[int, int, str], float] = {}
        for _, row in aggregated.iterrows():
            price_by_t[(int(row["y"]), int(row["t"]), str(row["fuel"]))] = float(row["price"])

        return cls(specs=specs, price_by_t=price_by_t)

    def price(self, fuel: str, y: int, t: int) -> float:
        """Devuelve el precio del combustible ``fuel`` en el bloque ``(y, t)``."""

        value = self.price_by_t.get((y, t, fuel))
        if value is not None:
            return float(value)

        spec: Optional[FuelSpec] = self.specs.get(fuel)
        return float(spec.base_price if spec else 0.0)
