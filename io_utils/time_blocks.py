# io/time_blocks.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

import logging

def log_blocks_info(tb: dict, logger, sample: int = 3):
    lg = logger

    sb = tb["sb_list"]
    n  = len(sb)
    lg.info("blocks (agregados): %s pares (stage, block)", n)

    head = sb[:sample]
    tail = sb[-sample:] if n >= sample else sb
    lg.info("primeros %d: %s", len(head), head)
    lg.info("últimos %d: %s", len(tail), tail)

    fbs = tb["first_block_of_stage"]
    lbs = tb["last_block_of_stage"]
    min_stage = min(fbs.keys()); max_stage = max(fbs.keys())
    lg.info("stage mínimo=%s (blocks %s→%s), stage máximo=%s (blocks %s→%s)",
            min_stage, fbs[min_stage], lbs[min_stage],
            max_stage, fbs[max_stage], lbs[max_stage])

    # === NUEVO: métricas desde gdf (agregado a bloque) ===
    gdf = tb["gdf"]
    dur = tb["duration"]  # dict (s,b)->hours
    total_hours = sum(dur.values())
    avg_block_h = total_hours / max(n, 1)
    lg.info("horas totales (agregado): %.1f; horas/bloque promedio: %.3f",
            total_hours, avg_block_h)

    # Horas por stage (útil para revisar que todas las meses tengan mismo total si aplica)
    hours_by_stage = gdf.groupby("stage")["duration_h"].sum()
    lg.info("horas en stage %s: %.1f; stage %s: %.1f",
            int(min_stage), float(hours_by_stage.loc[min_stage]),
            int(max_stage), float(hours_by_stage.loc[max_stage]))

    # Horas por año (derivadas del start_time del bloque agregado)
    hours_by_year = gdf.groupby("year")["duration_h"].sum().sort_index()
    for y, h in hours_by_year.items():
        lg.info("año %s: horas (agregado) = %.1f", int(y), float(h))

    # Sucesor (sanity)
    first_has_succ = (sb[0] in tb["succ_stage"])
    lg.info("el primer bloque tiene sucesor? %s", first_has_succ)
    lg.info("el último bloque tiene sucesor? %s", sb[-1] in tb["succ_stage"])



def load_blocks_structures(csv_path: str | Path):
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)

    # Requeridos mínimos
    req = {"stage", "block", "start_time", "duration_h"}
    faltan = req - set(df.columns)
    assert not faltan, f"Faltan columnas en {csv_path.name}: {sorted(faltan)}"

    # Parseo
    df["start_time"] = pd.to_datetime(df["start_time"])
    # 'end_time' es opcional; si existe, parsea para reportes
    if "end_time" in df.columns:
        df["end_time"] = pd.to_datetime(df["end_time"])

    # --- NUEVO: agregación por (stage, block) ---
    # - duration_h: suma de las horas dentro del bloque (debe dar 2.0)
    # - start_time: tomamos la mínima (inicio del bloque)
    # - end_time: (si existe) tomamos la máxima (fin del bloque)
    agg_dict = {
        "duration_h": "sum",
        "start_time": "min",
    }
    if "end_time" in df.columns:
        agg_dict["end_time"] = "max"

    gdf = (
        df.sort_values(["stage", "block", "start_time"], kind="mergesort")
          .groupby(["stage", "block"], as_index=False)
          .agg(agg_dict)
          .sort_values(["stage", "block"], kind="mergesort")
          .reset_index(drop=True)
    )

    # Año/mes desde el inicio del bloque
    gdf["year"]  = gdf["start_time"].dt.year
    gdf["month"] = gdf["start_time"].dt.month

    # Estructuras para Pyomo
    sb_list = [tuple(x) for x in gdf[["stage", "block"]].to_numpy()]
    duration = {(int(r.stage), int(r.block)): float(r.duration_h) for r in gdf.itertuples(index=False)}

    # Sucesor entre bloques agregados (sin “wrap” del último)
    succ_stage, succ_block = {}, {}
    for i in range(len(gdf) - 1):
        s, b = int(gdf.at[i, "stage"]), int(gdf.at[i, "block"])
        s1, b1 = int(gdf.at[i + 1, "stage"]), int(gdf.at[i + 1, "block"])
        succ_stage[(s, b)] = s1
        succ_block[(s, b)] = b1

    # Primer/último block por stage
    gb = gdf.groupby("stage")["block"]
    first_block_of_stage = {int(s): int(v.min()) for s, v in gb}
    last_block_of_stage  = {int(s): int(v.max()) for s, v in gb}

    # Calendario por stage (usando el primer bloque de cada stage)
    stage_calendar = gdf.drop_duplicates("stage")[["stage", "year", "month"]].sort_values("stage")
    stage_year  = {int(r.stage): int(r.year)  for r in stage_calendar.itertuples(index=False)}
    stage_month = {int(r.stage): int(r.month) for r in stage_calendar.itertuples(index=False)}

    return dict(
        df=df,                # crudo, por si quieres inspeccionar horas
        gdf=gdf,              # agregado a bloque (1 fila por (stage,block))
        sb_list=sb_list,
        duration=duration,
        succ_stage=succ_stage,
        succ_block=succ_block,
        first_block_of_stage=first_block_of_stage,
        last_block_of_stage=last_block_of_stage,
        stage_year=stage_year,
        stage_month=stage_month,
    )
