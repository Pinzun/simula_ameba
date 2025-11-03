# -*- coding: utf-8 -*-
# thermal/io/fuel_store.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List
import math
import pandas as pd

# ================= Helpers =================
def _require_columns(df: pd.DataFrame, cols: List[str], tag: str) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"[{tag}] faltan columnas: {miss}. Presentes: {list(df.columns)}")

def _to_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return default
    s = str(x).strip().lower()
    return s in {"true", "1", "t", "yes", "y", "si", "sí"}

def _to_dt_strict(s: Any, tag: str, col: str) -> pd.Timestamp:
    dt = pd.to_datetime(s, format="%Y-%m-%d-%H:%M", errors="coerce")
    if pd.isna(dt):
        raise ValueError(f"[{tag}] {col} inválido: {s!r} (esperado '%Y-%m-%d-%H:%M')")
    return dt

# ================= Tipos =================
@dataclass(frozen=True)
class FuelSpec:
    name: str
    fuel_type: str
    base_price: float        # fallback si no hay serie de precios
    consider_avail: bool

class FuelStore:
    """
    Mantiene:
      - catálogo de combustibles (Fuel.csv)
      - precios por bloque (fuel_price.csv) mapeados a (y, t, fuel_name)
    Donde (y,t) provienen del calendario extendido (cada bloque puede cubrir 2 horas).
    """
    def __init__(self, specs: Dict[str, FuelSpec], price_by_t: Dict[Tuple[int, int, str], float]):
        self.specs = specs
        self.price_by_t = price_by_t

    @classmethod
    def from_csv(cls, path_fuel_csv: Path, path_price_csv: Path, calendar_blocks: pd.DataFrame):
        """
        Requisitos:
          - Fuel.csv: columnas mínimas: name, fuel_price (opcionales: fuel_type, consider_availability)
          - fuel_price.csv: columnas: time, (opcional) scenario, Fuel_*
          - calendar_blocks: columnas: time_str, y, t  (una fila por HORA del calendario)
        Comportamiento:
          - Mapea cada 'time' horario a su (y,t) y agrega por bloque (promedio por (y,t,fuel)).
        """
        # ---------- Fuel.csv ----------
        tag_fuel = "Fuel.csv"
        f = pd.read_csv(path_fuel_csv)
        f.columns = [c.strip().lower() for c in f.columns]
        _require_columns(f, ["name"], tag_fuel)  # fuel_price puede faltar → usa base 0.0
        specs: Dict[str, FuelSpec] = {}
        for _, r in f.iterrows():
            name = str(r["name"])
            specs[name] = FuelSpec(
                name=name,
                fuel_type=str(r.get("fuel_type", "")),
                base_price=float(r.get("fuel_price", 0.0) or 0.0),
                consider_avail=_to_bool(r.get("consider_availability"), False),
            )

        # ---------- fuel_price.csv ----------
        tag_price = "fuel_price.csv"
        p = pd.read_csv(path_price_csv)
        p.columns = [c.strip() for c in p.columns]
        _require_columns(p, ["time"], tag_price)
        # Parseo estricto de la hora
        p["time_ts"] = p["time"].map(lambda s: _to_dt_strict(s, tag_price, "time"))

        # Detecta columnas de precio (todas excepto time, scenario si existe)
        price_cols = [c for c in p.columns if c not in {"time", "time_ts", "scenario"}]
        if not price_cols:
            raise ValueError(f"[{tag_price}] no se encontraron columnas de precios (ej. 'Fuel_Gas').")

        # Pivot largo: (time_ts, fuel, price)
        pp = p.melt(id_vars=["time_ts"], value_vars=price_cols, var_name="fuel", value_name="price")
        # Limpia NaN
        pp = pp.loc[pp["price"].notna()].copy()

        # ---------- calendar_blocks ----------
        tag_cal = "calendar_blocks"
        cb = calendar_blocks.copy()
        # Acepta 'time_str' o 'time'; normaliza a 'time_ts'
        if "time_str" in cb.columns:
            cb["time_ts"] = cb["time_str"].map(lambda s: _to_dt_strict(s, tag_cal, "time_str"))
        elif "time" in cb.columns:
            # si ya viene como str con formato esperado
            cb["time_ts"] = cb["time"].map(lambda s: _to_dt_strict(s, tag_cal, "time"))
        else:
            raise ValueError(f"[{tag_cal}] falta 'time_str' o 'time'.")

        _require_columns(cb, ["y", "t", "time_ts"], tag_cal)
        cb = cb[["time_ts", "y", "t"]].drop_duplicates()

        # Join horario → (y,t)
        pp2 = pp.merge(cb, on="time_ts", how="left")

        # Si hay horas sin match, las dejamos fuera (p.ej., fuera del horizonte)
        pp2 = pp2.loc[pp2["y"].notna() & pp2["t"].notna()].copy()
        pp2["y"] = pp2["y"].astype(int)
        pp2["t"] = pp2["t"].astype(int)
        pp2["fuel"] = pp2["fuel"].astype(str)
        pp2["price"] = pp2["price"].astype(float)

        # ---------- Agregación por bloque ----------
        # Para bloques de 2h: promedio de precios horarios dentro del bloque
        agg = pp2.groupby(["y", "t", "fuel"], as_index=False)["price"].mean()

        price_by_t: Dict[Tuple[int, int, str], float] = {}
        for _, r in agg.iterrows():
            price_by_t[(int(r["y"]), int(r["t"]), str(r["fuel"]))] = float(r["price"])

        return cls(specs=specs, price_by_t=price_by_t)

    def price(self, fuel: str, y: int, t: int) -> float:
        """Precio del combustible `fuel` en (y,t); si no hay serie usa base_price."""
        val = self.price_by_t.get((y, t, fuel))
        if val is not None:
            return float(val)
        spec: Optional[FuelSpec] = self.specs.get(fuel)
        return float(spec.base_price if spec else 0.0)