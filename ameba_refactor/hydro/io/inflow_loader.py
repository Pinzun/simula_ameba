# hydro/io/inflow_loader.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Tuple, Any
import math
import pandas as pd

from hydro.core.types import InflowRow, IrrigationRow, InflowSeries
from hydro.core.calendar_types import CalendarData, TimeIndex  # CalendarData.blocks tiene: stage, block, time (str o datetime), duration_h

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


# --- helper: detectar y convertir formato ancho a largo ---
def _wide_to_long_inflows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte un DataFrame ancho (time, [scenario?], afl_*) a largo con columnas:
      time, name, flow_m3s
    - Detecta columnas que empiezan con afl_ (en cualquier casing)
    - Normaliza name a minúsculas
    """
    cols = [str(c) for c in df.columns]
    # columnas inflow: prefijos típicos
    inflow_cols = [c for c in cols if c.lower().startswith("afl_")]
    if not inflow_cols:
        # no hay columnas afl_*, no podemos convertir
        return df

    id_vars = [c for c in cols if c not in inflow_cols]
    long = df.melt(id_vars=id_vars, value_vars=inflow_cols,
                   var_name="name", value_name="flow_m3s")

    # normalización
    long["name"] = long["name"].astype(str).str.strip().str.lower()
    # coerce numérico
    long["flow_m3s"] = pd.to_numeric(long["flow_m3s"], errors="coerce")

    # aseguremos columnas mínimas y orden
    keep = ["time", "name", "flow_m3s"]
    # si 'time' no existe porque venía con otro nombre, ahí sí fallamos de forma explícita
    if "time" not in long.columns:
        raise ValueError("[InflowSeries] No se encontró columna 'time' al convertir ancho→largo.")

    return long[keep]


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
    Acepta:
      1) Formato largo: columnas = time, name, flow_m3s
      2) Formato ancho: columnas = time, [scenario], afl_* (una por nodo)

    Devuelve lista de InflowSeries (name→serie horaria en hm3/h).
    """
    tag = "InflowSeries"
    df = pd.read_csv(path_ts)
    df.columns = [c.strip() for c in df.columns]

    cols = set(df.columns)
    # Si falta largo, intentamos ancho→largo
    if not ({"time", "name", "flow_m3s"} <= cols):
        df = _wide_to_long_inflows(df)
        cols = set(df.columns)

    # Validación final
    need = {"time", "name", "flow_m3s"}
    miss = [c for c in need if c not in cols]
    if miss:
        raise ValueError(f"[{tag}] faltan columnas: {miss}. Presentes: {list(df.columns)}")

    # Parseo de tiempo y normalización de nombre
    df["time"] = pd.to_datetime(df["time"], errors="raise")
    df["name"] = df["name"].astype(str).str.strip().str.lower()
    df["flow_m3s"] = pd.to_numeric(df["flow_m3s"], errors="coerce").fillna(0.0)

    # m3/s → hm3/h
    df["hm3_per_h"] = df["flow_m3s"] * 3600.0 / 1_000_000.0

    out: List[InflowSeries] = []
    for name, g in df.groupby("name", sort=False):
        out.append(InflowSeries(
            name=str(name),
            times=g["time"].tolist(),
            flow_hm3_per_hour=g["hm3_per_h"].astype(float).tolist()
        ))
    return out


# ===================== Agregación a bloques =====================
def aggregate_inflows_to_blocks(calendar, series, verbose: bool = True) -> Dict[Tuple[str, Tuple[int, int]], float]:
    """
    Agrega inflows a (y,t) en Hm3/bloque.
    Soporta ambos formatos de 'series':
      A) punto a punto:   s.name, s.time, s.flow_m3s  (m3/s por hora)
      B) serie por nodo:  s.name, s.times, s.flow_hm3_per_hour  (Hm3/h)
    """

    # --- 1) Horas del calendario: aceptar DataFrame o lista de objetos ---
    B = calendar.blocks
    if isinstance(B, pd.DataFrame):
        A = B.copy()
    else:
        # Asumimos lista de objetos con atributos: stage, block, time (y opcional duration_h)
        A = pd.DataFrame(
            {
                "stage": [getattr(b, "stage") for b in B],
                "block": [getattr(b, "block") for b in B],
                "time":  [getattr(b, "time")  for b in B],
                "duration_h": [getattr(b, "duration_h", 2.0) for b in B],
            }
        )

    # Normalización de tiempo a granularidad horaria
    A["time"] = pd.to_datetime(A["time"], errors="coerce")
    A = A.dropna(subset=["time"])
    A["time"] = A["time"].dt.floor("h")

    t_min = A["time"].min()
    t_max = A["time"].max()

    # --- 2) Aplanar series (el resto de tu función sigue igual) ---
    if not series:
        return {}

    rows: List[Dict[str, Any]] = []
    for s in series:
        if hasattr(s, "times") and hasattr(s, "flow_hm3_per_hour"):  # formato B
            for t, q_hm3h in zip(getattr(s, "times"), getattr(s, "flow_hm3_per_hour")):
                rows.append({"name": s.name, "time": t, "hm3_h": float(q_hm3h)})
        else:  # formato A
            t = getattr(s, "time", None)
            if t is None:
                continue
            if hasattr(s, "flow_m3s"):  # m3/s -> Hm3/h
                q_hm3h = float(getattr(s, "flow_m3s")) * 3600.0 / 1e6
            else:
                q_hm3h = float(getattr(s, "hm3_per_h", 0.0))
            rows.append({"name": s.name, "time": t, "hm3_h": q_hm3h})

    if not rows:
        return {}

    df = pd.DataFrame(rows)
    df["name"] = df["name"].astype(str).str.strip().str.lower()
    df["time"] = pd.to_datetime(df["time"], errors="coerce").dt.floor("h")
    df = df.dropna(subset=["time"])

    pre_len = len(df)
    df = df[(df["time"] >= t_min) & (df["time"] <= t_max)]
    cut_len = pre_len - len(df)

    joined = df.merge(A[["stage", "block", "time"]], on="time", how="inner")

    gb = (joined.groupby(["name", "stage", "block"], as_index=False)["hm3_h"]
                 .sum()
                 .rename(columns={"hm3_h": "hm3_block"}))

    out = { (str(r.name), (int(r.stage), int(r.block))) : float(r.hm3_block)
            for r in gb.itertuples(index=False) }

    if verbose:
        n_in = pre_len
        n_joined = len(joined)
        n_dropped_by_join = n_in - n_joined - cut_len
        print(f"[aggregate_inflows_to_blocks] "
              f"input={n_in:,}  recortados_por_rango={cut_len:,}  "
              f"no_coinciden_con_grilla={max(n_dropped_by_join,0):,}  "
              f"salida_pairs={(len(out)):,}")

    return out