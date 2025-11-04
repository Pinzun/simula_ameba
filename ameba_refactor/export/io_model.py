# ameba_refactor/export/io_model.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, Optional, Dict, List, Tuple
import pandas as pd
import numpy as np


def _to_df(obj: Any, *, expected_columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """
    Convierte 'obj' en DataFrame de manera tolerante:
      - DataFrame -> retorna tal cual
      - objeto con .to_df() -> usa esa salida
      - dict -> si los valores son secuencias del mismo largo => DataFrame por columnas,
                si son escalares -> dos columnas [key, value]
      - list/tuple -> si son dicts => DataFrame(records),
                      si son tuplas/secuencias homogéneas => DataFrame directo
    """
    # 1) Atajos directos
    if isinstance(obj, pd.DataFrame):
        df = obj.copy()
    elif hasattr(obj, "to_df") and callable(getattr(obj, "to_df")):
        df = obj.to_df()  # se asume que retorna DataFrame
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
    elif isinstance(obj, Mapping):  # dict-like
        d = dict(obj)
        if len(d) == 0:
            df = pd.DataFrame()
        else:
            vals = list(d.values())
            # ¿columnas con series/listas del mismo largo?
            if all(isinstance(v, (list, tuple, np.ndarray, pd.Series)) for v in vals):
                try:
                    df = pd.DataFrame(d)
                except Exception:
                    # fallback a rows: [{"key": k, "value": v}, ...]
                    rows = [{"key": k, "value": v} for k, v in d.items()]
                    df = pd.DataFrame(rows)
            else:
                # mapping escalar -> filas [key,value]
                rows = [{"key": k, "value": v} for k, v in d.items()]
                df = pd.DataFrame(rows)
    elif isinstance(obj, (list, tuple)):
        seq = list(obj)
        if len(seq) == 0:
            df = pd.DataFrame()
        else:
            first = seq[0]
            if isinstance(first, Mapping):
                df = pd.DataFrame(seq)  # list[dict]
            else:
                # list[tuple] o list[escalares]; sin columnas explícitas
                df = pd.DataFrame(seq)
    else:
        # último recurso: intentar construir DataFrame directamente
        try:
            df = pd.DataFrame(obj)
        except Exception:
            df = pd.DataFrame([{"value": obj}])

    # Normaliza columnas esperadas si se proporcionan
    if expected_columns is not None:
        cols = list(expected_columns)
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
        df = df.loc[:, cols]

    # Indices fuera: siempre index=False al exportar
    return df.reset_index(drop=True)


def _safe_to_csv(obj: Any, path: Path, *, expected_columns: Optional[Iterable[str]] = None) -> None:
    df = _to_df(obj, expected_columns=expected_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def export_model_inputs(
    out_dir: Path,
    *,
    # Red
    busbars: Any,
    branches: Any,
    system: Any = None,
    # Demanda
    demand_wide_block: Any = None,
    # Renovables
    pv_units: Any = None,
    pv_profile_block: Any = None,
    wind_units: Any = None,
    wind_profile_block: Any = None,
    # Térmica
    thermal_units: Any = None,
    thermal_costs: Any = None,
    thermal_limits: Any = None,
    # ESS
    ess_units: Any = None,
    ess_limits: Any = None,
    # Hidro (catálogos + inflows agregados a bloque)
    dam_catalog: Any = None,
    hydro_groups: Any = None,
    hydro_generators: Any = None,
    hydro_connections: Any = None,
    hydro_nodes: Any = None,
    inflow_block_hm3: Any = None,
    # Calendario
    stages: Any = None,
    blocks: Any = None,
) -> None:
    """
    Exporta todos los insumos del modelo a CSV en out_dir.
    Acepta DataFrames, dicts, listas de dicts u objetos con .to_df().
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Red
    _safe_to_csv(busbars, out_dir / "busbars.csv")
    _safe_to_csv(branches, out_dir / "branches.csv")
    if system is not None:
        _safe_to_csv(system, out_dir / "system.csv")

    # --- Calendario
    if stages is not None:
        _safe_to_csv(stages, out_dir / "stages.csv")
    if blocks is not None:
        _safe_to_csv(blocks, out_dir / "blocks.csv")

    # --- Demanda
    if demand_wide_block is not None:
        _safe_to_csv(demand_wide_block, out_dir / "demand_wide_block.csv")

    # --- PV/Wind
    if pv_units is not None:
        _safe_to_csv(pv_units, out_dir / "pv_units.csv")
    if pv_profile_block is not None:
        _safe_to_csv(pv_profile_block, out_dir / "pv_profile_block.csv")

    if wind_units is not None:
        _safe_to_csv(wind_units, out_dir / "wind_units.csv")
    if wind_profile_block is not None:
        _safe_to_csv(wind_profile_block, out_dir / "wind_profile_block.csv")

    # --- Térmica
    if thermal_units is not None:
        _safe_to_csv(thermal_units, out_dir / "thermal_units.csv")
    if thermal_costs is not None:
        _safe_to_csv(thermal_costs, out_dir / "thermal_costs.csv")
    if thermal_limits is not None:
        _safe_to_csv(thermal_limits, out_dir / "thermal_limits.csv")

    # --- ESS
    if ess_units is not None:
        _safe_to_csv(ess_units, out_dir / "ess_units.csv")
    if ess_limits is not None:
        _safe_to_csv(ess_limits, out_dir / "ess_limits.csv")

    # --- Hidro
    if dam_catalog is not None:
        _safe_to_csv(dam_catalog, out_dir / "dam_catalog.csv")
    if hydro_groups is not None:
        _safe_to_csv(hydro_groups, out_dir / "hydro_groups.csv")
    if hydro_generators is not None:
        _safe_to_csv(hydro_generators, out_dir / "hydro_generators.csv")
    if hydro_connections is not None:
        _safe_to_csv(hydro_connections, out_dir / "hydro_connections.csv")
    if hydro_nodes is not None:
        _safe_to_csv(hydro_nodes, out_dir / "hydro_nodes.csv")
    if inflow_block_hm3 is not None:
        # este suele ser un dict o DF largo: (reservoir, stage, block, inflow_hm3)
        _safe_to_csv(inflow_block_hm3, out_dir / "inflow_block_hm3.csv")
