# hydro/core/aggregate.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Tuple

from hydro.core.types import (
    # calendario minimalista y tipo de índice temporal
    CalendarKeys, TimeIndex,
    # contrato de salida y catálogos
    HydroData, ReservoirCatalog, GeneratorsCatalog, HydroGroupsLimits,
    HydroGraph, BlockAggregates,
)

def aggregate_hydro_to_blocks(
    calendar: CalendarKeys,
    res: ReservoirCatalog,
    gen: GeneratorsCatalog,
    limits: HydroGroupsLimits,
    graph: HydroGraph,
    inflow_to_res: Dict[str, str],
    inflow_to_hg: Dict[str, str],
    inflow_block_hm3: Dict[Tuple[str, TimeIndex], float],
    irrigation_block_hm3: Dict[Tuple[str, TimeIndex], float],
) -> HydroData:
    """
    Arma el paquete HydroData listo para el modelador, usando el calendario nuevo.

    Parámetros
    ----------
    calendar : CalendarKeys
        Claves ordenadas de stages y blocks.
    res, gen, limits, graph : catálogos y grafo ya cargados/validados.
    inflow_to_res : map Afl_* -> Emb_*
    inflow_to_hg  : map Afl_* -> HG_*
    inflow_block_hm3 : {(node, (stage, block)) -> Hm3 por bloque} (ya agregado a 2h si aplica)
    irrigation_block_hm3 : {(irrig_node, (stage, block)) -> Hm3 por bloque}

    Notas
    -----
    - Aplica la escala `res.scale[Emb_*]` a los aportes naturales dirigidos a embalses.
    - Deja pasar aportes que vayan directo a HG sin escala.
    - Si un nodo no está en `inflow_to_res` ni en `inflow_to_hg`, se ignora (o podrías
      rutearlos por `graph.arcs_natural` si defines esa convención).
    """
    I_nat_reservoir: Dict[Tuple[str, TimeIndex], float] = {}
    I_nat_hg:        Dict[Tuple[str, TimeIndex], float] = {}

    for (node, yt), q in inflow_block_hm3.items():
        # Resuelve el destino del afluente
        dst_res = inflow_to_res.get(node)
        dst_hg  = inflow_to_hg.get(node)

        if dst_res:
            sc = res.scale.get(dst_res, 1.0)
            I_nat_reservoir[(dst_res, yt)] = I_nat_reservoir.get((dst_res, yt), 0.0) + (q * sc)
        elif dst_hg:
            I_nat_hg[(dst_hg, yt)] = I_nat_hg.get((dst_hg, yt), 0.0) + q
        else:
            # Si no calza en ningún mapa, podrías definir aquí un fallback (opcional).
            # Por ahora, lo ignoramos explícitamente.
            continue

    agg = BlockAggregates(
        I_nat_reservoir=I_nat_reservoir,
        I_nat_hg=I_nat_hg,
        I_irrigation=irrigation_block_hm3.copy(),
    )

    return HydroData(
        calendar=calendar,
        reservoirs=res,
        generators=gen,
        groups_limits=limits,
        graph=graph,
        agg=agg,
        inflow_to_reservoir=inflow_to_res,
        inflow_to_hg=inflow_to_hg,
        balance_nodes=[],  # poblar si tienes nodos de balance explícitos
        metadata={"version": "0.1"},
    )