# export/io_model.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple, Iterable, Any
import pandas as pd

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def to_df(obj: Any, name: str) -> pd.DataFrame:
    """Devuelve un DataFrame a partir de varios formatos posibles."""
    if isinstance(obj, pd.DataFrame):
        return obj

    if isinstance(obj, dict):
        # busca por convenio típico
        for key in ["df", "data", "table", "rows"]:
            if key in obj and isinstance(obj[key], pd.DataFrame):
                return obj[key]
        raise ValueError(f"[{name}] No se pudo extraer un DataFrame desde un dict. Llaves presentes: {list(obj.keys())}")
    
    raise TypeError(f"[{name}] Objeto no reconocible como DataFrame ni dict: {type(obj)}")


def export_model_inputs(
    out_dir: Path,
    # calendario
    cal_blocks_df: pd.DataFrame,     # esperado: ['stage','block','start_time','end_time','duration_h']
    cal_assign_df: pd.DataFrame,     # esperado: ['stage','block','time']
    # demanda
    demand_wide_block: pd.DataFrame, # index=(stage,block) cols=buses
    # red
    busbars: Any,
    branches: Any,
    system: Any,
    # térmicas
    thermal_pkg: Dict[str, Any],     # e.g. {'units_df': df, 'fuels_df': df, 'prices_df': df}
    # PV/Wind
    pv_units: Any,                   # dict{name->PVPlant} o PVData(plants={})
    wind_units: Any,                 # dict{name->WindPlant} o WindData(plants={})
    # hidro
    inflow_block_hm3: Dict[Tuple[str, Tuple[int,int]], float],  # {(node,(y,t)) -> hm3}
) -> None:
    out_dir = Path(out_dir)
    _ensure_dir(out_dir)

    # --- calendario ---
    cal_blocks_df.to_csv(out_dir / "calendar_blocks.csv", index=False)
    cal_assign_df.to_csv(out_dir / "calendar_hours.csv", index=False)

    # --- demanda por bloque (ancho) ---
    demand_wide_block.to_csv(out_dir / "demand_by_block_wide.csv")

    # --- red ---
    to_df(busbars, "busbars").to_csv(out_dir / "busbars.csv", index=False)
    to_df(branches, "branches").to_csv(out_dir / "branches.csv", index=False)
    to_df(system, "system").to_csv(out_dir / "system.csv", index=False)

    # --- térmicas ---
    if isinstance(thermal_pkg, dict):
        for k, v in thermal_pkg.items():
            if isinstance(v, pd.DataFrame):
                v.to_csv(out_dir / f"thermal_{k}.csv", index=False)

    # --- PV/Wind catálogo mínimo ---
    def _plants_to_df(obj, kind: str) -> pd.DataFrame:
        if hasattr(obj, "plants") and isinstance(obj.plants, dict):
            vals = list(obj.plants.values())
        elif isinstance(obj, dict):
            vals = list(obj.values())
        else:
            vals = []
        rows = []
        for p in vals:
            rows.append({
                "name": getattr(p, "name", ""),
                "busbar": getattr(p, "busbar", ""),
                "profile": getattr(p, "profile", ""),
                "pmax": getattr(p, "pmax", 0.0),
                "pmin": getattr(p, "pmin", 0.0),
                "vomc": getattr(p, "vomc", 0.0),
                "inv_cost": getattr(p, "inv_cost", 0.0),
                "candidate": getattr(p, "candidate", False),
                "kind": kind
            })
        return pd.DataFrame(rows)

    _plants_to_df(pv_units, "pv").to_csv(out_dir / "plants_pv.csv", index=False)
    _plants_to_df(wind_units, "wind").to_csv(out_dir / "plants_wind.csv", index=False)

    # --- inflows (hidro) a tabla larga ---
    if inflow_block_hm3:
        rows = []
        for (node, (y, t)), q in inflow_block_hm3.items():
            rows.append({"name": node, "stage": int(y), "block": int(t), "hm3": float(q)})
        pd.DataFrame(rows).to_csv(out_dir / "inflow_block_hm3.csv", index=False)