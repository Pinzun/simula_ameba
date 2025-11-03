# hydro/core/validators.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, List, Tuple, Set
from hydro.core.types import ReservoirCatalog, GeneratorsCatalog, HydroGraph

# --------------------- Helpers ---------------------

def ensure_names_unique(names: Iterable[str], where: str) -> None:
    seen: Set[str] = set()
    dups: List[str] = []
    for n in names:
        if n in seen:
            dups.append(n)
        else:
            seen.add(n)
    if dups:
        raise ValueError(f"[{where}] nombres duplicados: {sorted(set(dups))}")

def _ensure_no_self_loops(arcs: List[Tuple[str, str]], tag: str) -> None:
    loops = [(u, v) for (u, v) in arcs if u == v]
    if loops:
        raise ValueError(f"[Graph:{tag}] arcos con self-loop: {loops[:5]}{' ...' if len(loops) > 5 else ''}")

def _check_arcs(
    arcs: List[Tuple[str, str]],
    left: Set[str],
    right: Set[str],
    tag: str,
) -> None:
    missing_left: List[str] = []
    missing_right: List[str] = []
    for u, v in arcs:
        if u not in left:
            missing_left.append(u)
        if v not in right:
            missing_right.append(v)
    msgs: List[str] = []
    if missing_left:
        msgs.append(f"orígenes desconocidos: {sorted(set(missing_left))[:10]}{' ...' if len(set(missing_left)) > 10 else ''}")
    if missing_right:
        msgs.append(f"destinos desconocidos: {sorted(set(missing_right))[:10]}{' ...' if len(set(missing_right)) > 10 else ''}")
    if msgs:
        raise ValueError(f"[Graph:{tag}] " + " | ".join(msgs))
    _ensure_no_self_loops(arcs, tag)

# --------------------- Validadores públicos ---------------------

def validate_catalogs(res: ReservoirCatalog, gen: GeneratorsCatalog) -> None:
    ensure_names_unique(res.names, "ReservoirCatalog")
    ensure_names_unique(gen.HG_all, "GeneratorsCatalog")

def validate_graph(graph: HydroGraph, res: ReservoirCatalog, gen: GeneratorsCatalog) -> None:
    """
    Valida coherencia básica del grafo con los catálogos.
    Convención:
      - arcs_spill_res:   Emb_* -> Emb_*
      - arcs_turb_res:    Emb_* -> Emb_*
      - arcs_spill_to_hg: Emb_* -> HG_*
      - arcs_turb_to_hg:  Emb_* -> HG_*
      - arcs_natural:     puede conectar Emb_* y/o HG_* en ambos extremos
    """
    all_res: Set[str] = set(res.names)
    all_hg:  Set[str] = set(gen.HG_all)
    all_nodes = all_res | all_hg  # para 'natural' permitimos ambos

    # Validaciones por lista
    _check_arcs(graph.arcs_spill_res,   all_res, all_res, "spill_res")
    _check_arcs(graph.arcs_turb_res,    all_res, all_res, "turb_res")
    _check_arcs(graph.arcs_spill_to_hg, all_res, all_hg,  "spill_to_hg")
    _check_arcs(graph.arcs_turb_to_hg,  all_res, all_hg,  "turb_to_hg")
    _check_arcs(graph.arcs_natural,     all_nodes, all_nodes, "natural")