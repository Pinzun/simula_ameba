# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Iterable, Optional, Any

import pandas as pd

from core import ModelCalendar

# Tipos
TimeKey = Tuple[int, int]  # (stage, block)

@dataclass
class DemandStore:
    """
    Mantiene demanda horaria (wide) y el mapping de cargas L_* -> busbar.
    Permite agregar por bloque (suma de horas del bloque).
    """
    # DataFrame index=time (Timestamp, sin tz), cols = sólo columnas L_*
    hourly_wide: pd.DataFrame
    # Mapa L_* -> busbar (string exacto como en network)
    load_to_bus: Dict[str, str]

    # -------------------- Constructores --------------------

    @classmethod
    def from_csvs(
        cls,
        demand_series_csv: Path,
        load_csv: Path,
        time_format: str = "%Y-%m-%d-%H:%M",
    ) -> "DemandStore":
        """
        - demand_series_csv: columnas = time, scenario, L_*
        - load_csv:          columnas = name (L_*), busbar, ...
        """
        df = pd.read_csv(demand_series_csv)
        df["time"] = pd.to_datetime(df["time"], format=time_format, errors="raise")
        l_cols = [c for c in df.columns if c.startswith("L_")]
        hourly = (
            df.drop(columns=[c for c in ["scenario"] if c in df.columns])
              .set_index("time")
              .sort_index()
        )
        hourly = hourly[l_cols].copy()

        meta = pd.read_csv(load_csv)
        meta.columns = [c.strip() for c in meta.columns]
        need = {"name", "busbar"}
        miss = [c for c in need if c not in set(meta.columns)]
        if miss:
            raise AssertionError(f"[load.csv] faltan columnas {miss} (se requieren {sorted(need)}).")

        present = set(l_cols)
        meta = meta[meta["name"].astype(str).isin(present)].copy()
        meta = meta.drop_duplicates(subset=["name"], keep="first")
        l2b: Dict[str, str] = dict(zip(meta["name"].astype(str), meta["busbar"].astype(str)))

        return cls(hourly_wide=hourly, load_to_bus=l2b)

    @classmethod
    def from_frames(
        cls,
        demand_series_df: pd.DataFrame,
        load_df: pd.DataFrame,
        time_format: str = "%Y-%m-%d-%H:%M",
    ) -> "DemandStore":
        """
        Igual que from_csvs pero recibiendo DataFrames ya cargados:
        - demand_series_df: columnas = time, scenario, L_*
        - load_df:          columnas = name (L_*), busbar, ...
        """
        if "time" not in demand_series_df.columns:
            raise AssertionError("[DemandStore.from_frames] falta columna 'time' en demand_series_df")

        df = demand_series_df.copy()
        df["time"] = pd.to_datetime(df["time"], format=time_format, errors="raise")
        l_cols = [c for c in df.columns if c.startswith("L_")]
        if not l_cols:
            raise AssertionError("[DemandStore.from_frames] no hay columnas L_* en demand_series_df")

        hourly = (
            df.drop(columns=[c for c in ["scenario"] if c in df.columns])
              .set_index("time")
              .sort_index()
        )
        hourly = hourly[l_cols].copy()

        meta = load_df.copy()
        meta.columns = [c.strip() for c in meta.columns]
        need = {"name", "busbar"}
        miss = [c for c in need if c not in set(meta.columns)]
        if miss:
            raise AssertionError(f"[load_df] faltan columnas {miss} (se requieren {sorted(need)}).")

        present = set(l_cols)
        meta = meta[meta["name"].astype(str).isin(present)].copy()
        meta = meta.drop_duplicates(subset=["name"], keep="first")
        l2b: Dict[str, str] = dict(zip(meta["name"].astype(str), meta["busbar"].astype(str)))

        return cls(hourly_wide=hourly, load_to_bus=l2b)

    # -------------------- Agregaciones por bloque --------------------

    def _calendar_hours_df(self, calendar) -> pd.DataFrame:
        A = calendar.hours_df().copy()  # ← trae ['stage','block','time','time_str']
        # Asegura tipos (por si el calendar cambiara en otra rama)
        A["time"] = pd.to_datetime(A["time"], errors="raise")
        return A[["stage", "block", "time"]]

    def build_by_block(
        self,
        calendar: ModelCalendar,
        fill_missing_as_zero: bool = True,
    ) -> Dict[TimeKey, Dict[str, float]]:
        """
        Agrega demanda por bloque (suma de las horas que caen en ese bloque).
        Devuelve: {(stage, block): {busbar: MW_sum}}
        """
        # 1) Horas del calendario con (stage, block)
        A = self._calendar_hours_df(calendar)  # ← debe devolver ['stage','block','time'] con time=Timestamp

        # 2) Join con la matriz horaria L_* (index=time)
        H = self.hourly_wide
        joined = A.merge(H.reset_index(), on="time", how="left")

        # 3) Mapeo L_* → busbar
        mapped_cols = [c for c in H.columns if c in self.load_to_bus]
        if not mapped_cols:
            raise AssertionError("[DemandStore] No hay columnas L_* mapeadas a busbar en load.csv")

        bus_to_lcols: Dict[str, list] = {}
        for lcol in mapped_cols:
            bus = self.load_to_bus.get(lcol)
            if bus is None:
                continue
            bus_to_lcols.setdefault(bus, []).append(lcol)

        # 4) Para cada bus, suma de sus L_* por hora (con coerción numérica) y luego suma por (stage,block)
        pieces = []
        for bus, cols in bus_to_lcols.items():
            # Por si alguna vez cols viniera como string
            if isinstance(cols, str):
                cols = [cols]

            # Mantén solo las columnas que realmente están en el join
            cols = [c for c in cols if c in joined.columns]
            if not cols:
                # Si no hay ninguna columna L_* para este bus en el join, saltamos
                continue

            sub = joined[["stage", "block"] + cols].copy()

            # Conversión numérica columna a columna (DataFrame → aplicar por Series)
            sub_num = sub[cols].apply(pd.to_numeric, errors="coerce")

            # Si falta algún dato horario:
            if fill_missing_as_zero:
                sub_num = sub_num.fillna(0.0)

            # Suma por fila (misma hora) de todas las L_* que alimentan ese bus
            # min_count=1 evita que todo NaN dé 0 silenciosamente cuando fill_missing_as_zero=False
            sub["MW_bus"] = sub_num.sum(axis=1, min_count=1)

            if fill_missing_as_zero:
                sub["MW_bus"] = sub["MW_bus"].fillna(0.0)

            # Agrega por bloque (suma de horas del bloque, NO promedio)
            sub = sub.groupby(["stage", "block"], as_index=False)["MW_bus"].sum()

            # Renombra a bus para el merge horizontal posterior
            sub = sub.rename(columns={"MW_bus": bus})
            pieces.append(sub)

        if not pieces:
            return {}

        # 5) Unimos todos los buses en una tabla ancha por (stage,block)
        agg = pieces[0]
        for p in pieces[1:]:
            agg = agg.merge(p, on=["stage", "block"], how="outer")

        agg = agg.fillna(0.0) if fill_missing_as_zero else agg

        # 6) A dict {(stage,block) -> {bus: MW}}
        out: Dict[TimeKey, Dict[str, float]] = {}
        bus_cols = [c for c in agg.columns if c not in {"stage", "block"}]
        for r in agg.itertuples(index=False):
            y, t = int(getattr(r, "stage")), int(getattr(r, "block"))
            values = {bus: float(getattr(r, bus)) for bus in bus_cols}
            out[(y, t)] = values

        return out
    # -------------------- Utilidades --------------------

    def buses(self) -> Iterable[str]:
        """Buses con al menos una L_* mapeada."""
        return sorted(set(self.load_to_bus.values()))

    def loads(self) -> Iterable[str]:
        """Nombres L_* disponibles en la serie."""
        return list(self.hourly_wide.columns)

    def to_dataframe_by_block(
        self,
        calendar: ModelCalendar,
        fill_missing_as_zero: bool = True,
    ) -> pd.DataFrame:
        """
        Igual que build_by_block, pero devuelve un DataFrame ancho:
        columnas = buses, índice MultiIndex=(stage, block)
        """
        data = self.build_by_block(calendar, fill_missing_as_zero=fill_missing_as_zero)
        if not data:
            return pd.DataFrame(columns=["stage", "block"]).set_index(["stage", "block"])

        rows = []
        for (y, t), mp in data.items():
            row = {"stage": y, "block": t}
            row.update(mp)
            rows.append(row)
        wide = pd.DataFrame(rows).set_index(["stage", "block"]).sort_index()
        return wide


# -------------------- Facade para main.py --------------------

@dataclass
class DemandPackage:
    """Contenedor simple para consumir en el main/modelador."""
    store: DemandStore
    by_block_df: pd.DataFrame  # filas=(stage,block), cols=buses (MW sumados por bloque)

def build_demand(
    calendar: ModelCalendar,
    loads_df: pd.DataFrame,
    demand_series_df: pd.DataFrame,
    demand_factors_df: Optional[pd.DataFrame] = None,  # reservado
) -> DemandPackage:
    """
    Mantiene la firma que estás usando en main.py.
    - Suma por bloque (2 horas) usando el calendario nuevo (stage, block, time).
    - Mapea L_* → busbar con load_df.
    - Por ahora, demand_factors_df no se aplica (queda reservado).
    """
    store = DemandStore.from_frames(demand_series_df=demand_series_df, load_df=loads_df)
    by_block_df = store.to_dataframe_by_block(calendar)
    return DemandPackage(store=store, by_block_df=by_block_df)