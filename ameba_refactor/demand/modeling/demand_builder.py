# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Iterable, Optional

import pandas as pd
from core import ModelCalendar  # calendar.blocks_df (DataFrame con: stage, block, start_time, end_time, duration_h)

# Tipos
TimeKey = Tuple[int, int]  # (stage, block)


# ============================================================
# Proyección horaria a años del calendario + aplicación de factores
# ============================================================
def _project_hourly_with_factors_to_calendar_years(
    demand_series_df: pd.DataFrame,   # columnas: time (YYYY-mm-dd-HH:MM), L_* (MW)
    factors_df: pd.DataFrame,         # columnas: time (YYYY-01-01-00:00 por año), Proj_* (escala por barra)
    calendar_blocks_df: pd.DataFrame, # columnas: stage, block, start_time, end_time, duration_h
    time_format: str = "%Y-%m-%d-%H:%M",
) -> pd.DataFrame:
    """
    - Toma una serie horaria base (un año típico) con columnas L_* en MW.
    - Toma factores anuales por barra (Proj_*).
    - Repite la forma horaria para cada año visto en el calendario y aplica el factor del año (último <= 01-01 de ese año).
    - Devuelve DataFrame horario con 'time' + L_* ya escaladas para todos los años requeridos.
    """
    # 1) Normaliza entradas
    dfH = demand_series_df.copy()
    dfH.columns = [c.strip() for c in dfH.columns]
    if "time" not in dfH.columns:
        raise AssertionError("[project_hourly] falta columna 'time' en demand_series_df")
    dfH["time"] = pd.to_datetime(dfH["time"], format=time_format, errors="raise")
    dfH = dfH.sort_values("time").reset_index(drop=True)

    load_cols = [c for c in dfH.columns if c.startswith("L_")]
    if not load_cols:
        raise AssertionError("[project_hourly] no hay columnas L_* en demanda base")

    # 2) Tail del timestamp (mes-día-hora:min)
    tail = dfH["time"].dt.strftime("%m-%d-%H:%M")

    # 3) Años objetivo desde el calendario
    B = calendar_blocks_df.copy()
    B["start_time"] = pd.to_datetime(B["start_time"], errors="raise")
    years = sorted(B["start_time"].dt.year.unique().tolist())
    if not years:
        raise AssertionError("[project_hourly] no se detectaron años en calendar_blocks_df")

    # 4) Prepara factores (indexados por time, columnas Proj_*)
    F = factors_df.copy()
    F.columns = [c.strip() for c in F.columns]
    if "time" not in F.columns:
        raise AssertionError("[project_hourly] falta columna 'time' en factors_df")
    F["time"] = pd.to_datetime(F["time"], format=time_format, errors="raise")
    F = F.sort_values("time").set_index("time")

    proj_cols = [c for c in F.columns if c.startswith("Proj_")]
    if not proj_cols:
        raise AssertionError("[project_hourly] no se encontraron columnas Proj_* en factors_df")

    # 5) Mapeo L_<BUS> -> Proj_<BUS>
    def _factor_col_for_load(lcol: str) -> Optional[str]:
        suffix = lcol[2:]  # quita 'L_'
        cand = f"Proj_{suffix}"
        return cand if cand in F.columns else None

    # 6) Genera la serie horaria proyectada para cada año del calendario
    pieces = []
    for y in years:
        # Timestamp objetivo del año (reemplaza año, conserva mm-dd-HH:MM)
        tproj = pd.to_datetime(f"{y}-" + tail, format=time_format, errors="coerce")

        # Descarta filas inválidas (p.ej. 29-feb en año no bisiesto)
        mask = ~pd.isna(tproj)
        if not mask.any():
            continue

        block = pd.DataFrame({"time": tproj[mask]})
        # Copia las columnas L_* válidas
        for lcol in load_cols:
            block[lcol] = dfH.loc[mask, lcol].to_numpy()

        # Factor vigente para el año: último registro <= 01-01 de ese año
        year_ref_ts = pd.Timestamp(year=y, month=1, day=1, hour=0, minute=0)
        ix = F.index.searchsorted(year_ref_ts, side="right") - 1
        if ix < 0:
            ix = 0  # si no hay pasado, usa primera fila
        factor_row = F.iloc[ix]

        # Aplica factor por columna L_* correspondiente
        for lcol in load_cols:
            fcol = _factor_col_for_load(lcol)
            scale = float(factor_row[fcol]) if fcol is not None else 1.0
            block[lcol] = block[lcol].astype(float) * scale

        pieces.append(block)

    if not pieces:
        # si no hubo años válidos, devuelve base tal cual
        return dfH[["time"] + load_cols].copy()

    out = pd.concat(pieces, ignore_index=True)
    out = out.sort_values("time").reset_index(drop=True)
    return out[["time"] + load_cols]


# ============================================================
# DemandStore: horario -> (stage,block) con promedio MW
# ============================================================
@dataclass
class DemandStore:
    # DataFrame index=time (Timestamp), cols = sólo columnas L_*
    hourly_wide: pd.DataFrame
    # Mapa L_* -> busbar (string exacto como en network)
    load_to_bus: Dict[str, str]

    @classmethod
    def from_frames(
        cls,
        demand_series_df: pd.DataFrame,
        load_df: pd.DataFrame,
        time_format: str = "%Y-%m-%d-%H:%M",
    ) -> "DemandStore":
        """
        - demand_series_df: columnas = time, (scenario opcional), L_*
        - load_df:          columnas = name (L_*), busbar, ...
        """
        if "time" not in demand_series_df.columns:
            raise AssertionError("[DemandStore.from_frames] falta columna 'time' en demand_series_df")

        df = demand_series_df.copy()
        df.columns = [c.strip() for c in df.columns]
        df["time"] = pd.to_datetime(df["time"], format=time_format, errors="raise")

        l_cols = [c for c in df.columns if c.startswith("L_")]
        if not l_cols:
            raise AssertionError("[DemandStore.from_frames] no hay columnas L_* en demand_series_df")

        hourly = (
            df.drop(columns=[c for c in ["scenario"] if c in df.columns])
              .set_index("time")
              .sort_index()
        )[l_cols].copy()

        meta = load_df.copy()
        meta.columns = [c.strip() for c in meta.columns]
        need = {"name", "busbar"}
        miss = [c for c in need if c not in set(meta.columns)]
        if miss:
            raise AssertionError(f"[load_df] faltan columnas {miss} (se requieren {sorted(need)}).")

        present = set(l_cols)
        meta = meta[meta["name"].astype(str).isin(present)].drop_duplicates(subset=["name"], keep="first")
        l2b: Dict[str, str] = dict(zip(meta["name"].astype(str), meta["busbar"].astype(str)))

        return cls(hourly_wide=hourly, load_to_bus=l2b)

    def _calendar_blocks_df(self, calendar: ModelCalendar) -> pd.DataFrame:
        """Devuelve ['stage','block','start_time','end_time','duration_h'] con tipos correctos."""
        B = calendar.blocks_df.copy()  # calendar.blocks_df es atributo DataFrame
        B["start_time"] = pd.to_datetime(B["start_time"], errors="raise")
        B["end_time"]   = pd.to_datetime(B["end_time"],   errors="raise")
        B["duration_h"] = pd.to_numeric(B["duration_h"], errors="raise")
        return B[["stage", "block", "start_time", "end_time", "duration_h"]].sort_values("start_time")

    def build_by_block(
        self,
        calendar: ModelCalendar,
        fill_missing_as_zero: bool = True,
    ) -> Dict[TimeKey, Dict[str, float]]:
        """
        Mapea cada registro horario al bloque [start_time, end_time) y calcula
        la DEMANDA MEDIA (MW) por bloque para cada bus.
        Devuelve: {(stage, block): {busbar: MW_promedio_en_bloque}}
        """
        # 1) Bloques con [start_time, end_time)
        B = self._calendar_blocks_df(calendar)

        # 2) Serie horaria L_* (index=time horas exactas)
        H = self.hourly_wide.reset_index().copy()   # columnas: time, L_*
        H["time"] = pd.to_datetime(H["time"], errors="raise")
        H = H.sort_values("time")

        # 3) merge_asof: asigna el bloque cuyo start_time <= time; luego filtra time < end_time
        M = pd.merge_asof(
            H, B[["stage", "block", "start_time", "end_time", "duration_h"]],
            left_on="time",
            right_on="start_time",
            direction="backward",
            allow_exact_matches=True,
        )
        M = M[M["time"] < M["end_time"]].copy()  # descarta tiempos fuera de cualquier bloque

        # 4) columnas L_* realmente presentes y mapeadas a bus
        mapped_cols = [c for c in self.hourly_wide.columns if c in self.load_to_bus]
        if not mapped_cols:
            raise AssertionError("[DemandStore] No hay columnas L_* mapeadas a busbar en load.csv")

        # 5) Para cada bus, suma L_* por hora y luego PROMEDIO por bloque (MW medios)
        bus_to_lcols: Dict[str, list] = {}
        for lcol in mapped_cols:
            bus = self.load_to_bus.get(lcol)
            if bus is None:
                continue
            bus_to_lcols.setdefault(bus, []).append(lcol)

        pieces = []
        for bus, cols in bus_to_lcols.items():
            cols = [c for c in cols if c in M.columns]
            if not cols:
                continue

            sub = M[["stage", "block"] + cols].copy()
            sub_num = sub[cols].apply(pd.to_numeric, errors="coerce")
            if fill_missing_as_zero:
                sub_num = sub_num.fillna(0.0)

            sub["MW_bus"] = sub_num.sum(axis=1, min_count=1)
            if fill_missing_as_zero:
                sub["MW_bus"] = sub["MW_bus"].fillna(0.0)

            sub_blk = (
                sub.groupby(["stage", "block"], as_index=False)["MW_bus"]
                   .mean()  # promedio (MW medios del bloque)
                   .rename(columns={"MW_bus": bus})
            )
            pieces.append(sub_blk)

        if not pieces:
            return {}

        agg = pieces[0]
        for p in pieces[1:]:
            agg = agg.merge(p, on=["stage", "block"], how="outer")

        if fill_missing_as_zero:
            value_cols = [c for c in agg.columns if c not in {"stage", "block"}]
            agg[value_cols] = agg[value_cols].fillna(0.0)

        out: Dict[TimeKey, Dict[str, float]] = {}
        bus_cols = [c for c in agg.columns if c not in {"stage", "block"}]
        for r in agg.itertuples(index=False):
            y, t = int(getattr(r, "stage")), int(getattr(r, "block"))
            values = {bus: float(getattr(r, bus)) for bus in bus_cols}
            out[(y, t)] = values
        return out

    def to_dataframe_by_block(
        self,
        calendar: ModelCalendar,
        fill_missing_as_zero: bool = True,
    ) -> pd.DataFrame:
        """
        Igual que build_by_block, pero devuelve un DataFrame ancho:
        columnas = buses, índice MultiIndex=(stage, block) (valores = MW medios).
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


# ============================================================
# Facade para main.py
# ============================================================
@dataclass
class DemandPackage:
    """Contenedor simple para consumir en el main/modelador."""
    store: DemandStore
    by_block_df: pd.DataFrame  # filas=(stage,block), cols=buses (MW medios por bloque)


def build_demand(
    calendar: ModelCalendar,
    loads_df: pd.DataFrame,
    demand_series_df: pd.DataFrame,
    demand_factors_df: Optional[pd.DataFrame] = None,
) -> DemandPackage:
    """
    Flujo:
      1) Si hay factores, proyecta la serie horaria base a los años del calendario y aplica Proj_*.
      2) Crea DemandStore (L_* y mapping a bus).
      3) Agrega a bloques por promedio (MW).
    """
    # 1) Calendario (para obtener años)
    B = calendar.blocks_df.copy()
    B["start_time"] = pd.to_datetime(B["start_time"], errors="raise")
    B["end_time"]   = pd.to_datetime(B["end_time"], errors="raise")

    # 2) Proyección con factores si corresponde
    if demand_factors_df is not None and not demand_factors_df.empty:
        demand_series_df = _project_hourly_with_factors_to_calendar_years(
            demand_series_df=demand_series_df,
            factors_df=demand_factors_df,
            calendar_blocks_df=B,
            time_format="%Y-%m-%d-%H:%M",
        )

    # 3) Construcción y agregado
    store = DemandStore.from_frames(demand_series_df=demand_series_df, load_df=loads_df)
    by_block_df = store.to_dataframe_by_block(calendar)
    return DemandPackage(store=store, by_block_df=by_block_df)
