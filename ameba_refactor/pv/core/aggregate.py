# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Tuple, List
import pandas as pd

from solar.core.types import PvData, Stage, Block, Plant
from solar.io.pv_loader import pv_df_to_records
from solar.io.power_loader import available_profile_cols

def parse_time(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%Y-%m-%d-%H:%M", errors="coerce")

def build_pvdata(
    pv_df: pd.DataFrame,           # de load_pv_generator()
    power_df: pd.DataFrame,        # de load_power_timeseries()
    blocks_df: pd.DataFrame,       # calendario granular: columnas ['stage','block','time']
    Y_list: List[Stage],
    T_by_Y: Dict[Stage, List[Block]],
    clip_01: bool = True
) -> PvData:
    """
    Calcula AF_{plant,(y,t)} como el PROMEDIO del perfil horario (columna 'Profile_*')
    sobre los timestamps que caen en ese (stage,block). No multiplicamos por Pmax aquí;
    ese límite se aplica en el modelo: p_pv <= AF * Pmax * alpha.
    """
    # Validaciones rápidas
    if "time" not in power_df.columns:
        raise ValueError("power_df debe traer columna 'time'")
    for c in ("stage","block","time"):
        if c not in blocks_df.columns:
            raise ValueError("blocks_df debe traer columnas 'stage','block','time'")

    blocks = blocks_df.copy()
    blocks["time"] = parse_time(blocks["time"])
    pwr = power_df.copy()
    pwr["time"] = parse_time(pwr["time"])

    # Mapeo planta -> perfil (columna en power_df)
    records = pv_df_to_records(pv_df)
    prof_cols = set(available_profile_cols(pwr))

    # Merge para asignar, a cada timestamp de block, el valor del perfil de CADA planta
    merged = blocks.merge(pwr, how="left", on="time")

    # AF dict
    af: Dict[Tuple[Plant, Stage, Block], float] = {}

    # Para cada planta, promediamos su perfil en cada (y,t)
    for plant, rec in records.items():
        prof = rec.profile
        if prof not in prof_cols:
            # perfil faltante: ponemos AF=0
            for y in Y_list:
                for t in T_by_Y[y]:
                    af[(plant, y, t)] = 0.0
            continue

        # agrupamos por (stage,block) el promedio del perfil
        grp = merged.groupby(["stage","block"], as_index=False)[prof].mean()
        for _, row in grp.iterrows():
            y, t = int(row["stage"]), int(row["block"])
            val = float(row[prof])
            if clip_01:
                val = 0.0 if pd.isna(val) else max(0.0, min(1.0, val))
            else:
                val = 0.0 if pd.isna(val) else float(val)
            af[(plant, y, t)] = val

        # Si faltan algunos (y,t) por huecos en calendario, completamos a 0
        for y in Y_list:
            for t in T_by_Y[y]:
                af.setdefault((plant, y, t), 0.0)

    return PvData(plants=records, af=af)