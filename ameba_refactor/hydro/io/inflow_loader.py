# hydro/io/inflow_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Tuple, Any
import math
import pandas as pd

from hydro.core.types import InflowRow, IrrigationRow, InflowSeries
from core.types import CalendarData, TimeIndex  # CalendarData.blocks tiene: stage, block, time (str o datetime), duration_h

# ===================== Helpers =====================
def _require_columns(df: pd.DataFrame, cols: List[str], tag: str) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"[{tag}] faltan columnas: {miss}. Presentes: {list(df.columns)}")

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
    return s in {"true", "1", "t", "yes", "y", "si", "sí"}

# ===================== Metadatos (tablas cortas) =====================
def load_inflow_nodes(path: Path) -> List[InflowRow]:
    tag = "Inflow"
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    _require_columns(df, ["name", "start_time", "end_time", "report", "inflows_qm3", "plp_indep_hydro"], tag)

    df["start_time"] = df["start_time"].map(lambda s: _to_dt_strict(s, tag, "start_time"))
    df["end_time"]   = df["end_time"].map(lambda s: _to_dt_strict(s, tag, "end_time"))
    df["report"]     = df["report"].map(lambda x: _to_bool(x, True))
    df["plp_indep_hydro"] = df["plp_indep_hydro"].map(lambda x: _to_bool(x, False))

    out: List[InflowRow] = []
    for _, r in df.iterrows():
        out.append(InflowRow(
            name=str(r["name"]),
            start_time=r["start_time"].to_pydatetime(),
            end_time=r["end_time"].to_pydatetime(),
            report=bool(r["report"]),
            inflows_qm3=float(r["inflows_qm3"]),
            plp_indep_hydro=bool(r["plp_indep_hydro"]),
        ))
    return out

def load_irrigation_nodes(path: Path) -> List[IrrigationRow]:
    tag = "Irrigation"
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    _require_columns(df, ["name", "start_time", "end_time", "report", "irrigations_qm3", "voli"], tag)

    df["start_time"] = df["start_time"].map(lambda s: _to_dt_strict(s, tag, "start_time"))
    df["end_time"]   = df["end_time"].map(lambda s: _to_dt_strict(s, tag, "end_time"))
    df["report"]     = df["report"].map(lambda x: _to_bool(x, True))

    out: List[IrrigationRow] = []
    for _, r in df.iterrows():
        out.append(IrrigationRow(
            name=str(r["name"]),
            start_time=r["start_time"].to_pydatetime(),
            end_time=r["end_time"].to_pydatetime(),
            report=bool(r["report"]),
            irrigations_qm3=float(r["irrigations_qm3"]),
            voli=float(r["voli"]),
        ))
    return out

# ===================== Serie horaria larga =====================
def load_inflow_series_long(path_ts: Path) -> List[InflowSeries]:
    """
    Espera un CSV con columnas: time,name,flow_m3s
    Convierte a hm3/h y entrega una lista de series por 'name'.
    """
    tag = "InflowSeries"
    df = pd.read_csv(path_ts)
    df.columns = [c.strip().lower() for c in df.columns]
    _require_columns(df, ["time", "name", "flow_m3s"], tag)

    # Parseo estricto de la columna de tiempo
    df["time"] = df["time"].map(lambda s: _to_dt_strict(s, tag, "time"))
    # Convertir m3/s → hm3/h  (1 m3/s = 3600 m3/h = 3.6e-3 hm3/h)
    df["hm3_per_h"] = df["flow_m3s"].astype(float) * 3600.0 / 1_000_000.0

    out: List[InflowSeries] = []
    for name, g in df.groupby("name", sort=False):
        out.append(InflowSeries(
            name=str(name),
            times=g["time"].tolist(),
            flow_hm3_per_hour=g["hm3_per_h"].astype(float).tolist()
        ))
    return out

# ===================== Agregación a bloques =====================
def aggregate_inflows_to_blocks(calendar: CalendarData,
                                series: List[InflowSeries]) -> Dict[Tuple[str, TimeIndex], float]:
    """
    Suma hm3/h de cada serie a nivel de bloque (y,t) usando el calendario extendido.
    Importante:
      - El calendario provee filas por cada hora con su (stage, block) ya asignado.
      - Si un bloque dura 2 horas, la suma por (stage,block) acumula las 2 filas/horas.
    Retorna: {(node, (stage, block)) -> hm3/bloque}
    """
    # Mapa de timestamp exacto → (stage, block)
    # calendar.blocks puede tener 'time' como str o datetime; normalizamos a Timestamp
    times_to_yt: Dict[pd.Timestamp, TimeIndex] = {}
    for b in calendar.blocks:
        bt = pd.to_datetime(getattr(b, "time"), format="%Y-%m-%d-%H:%M", errors="coerce")
        if pd.isna(bt):
            # Si ya viene como datetime, reintenta sin formato
            bt = pd.to_datetime(getattr(b, "time"), errors="coerce")
        if pd.isna(bt):
            raise ValueError(f"[CalendarData] bloque con 'time' inválido: {getattr(b, 'time')!r}")
        times_to_yt[pd.Timestamp(bt)] = (int(getattr(b, "stage")), int(getattr(b, "block")))

    agg: Dict[Tuple[str, TimeIndex], float] = {}
    missed = 0

    for s in series:
        for tm, q in zip(s.times, s.flow_hm3_per_hour):
            tm = pd.Timestamp(tm)
            yt = times_to_yt.get(tm)
            if yt is None:
                # La hora de la serie no existe en el calendario (distinta granularidad o ventana).
                # No abortamos; solo contamos para diagnóstico.
                missed += 1
                continue
            key = (s.name, yt)
            agg[key] = agg.get(key, 0.0) + float(q)

    if missed:
        # Mensaje suave para depurar desalineaciones (p.ej., horas fuera de stages)
        print(f"[aggregate_inflows_to_blocks] Advertencia: {missed} timestamps de inflow no calzaron con el calendario.")

    return agg