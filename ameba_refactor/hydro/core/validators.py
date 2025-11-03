# hydro/core/validators.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, List, Tuple, Set
from hydro.core.types import ReservoirCatalog, GeneratorsCatalog, HydroGraph

def ensure_names_unique(names: Iterable[str], where: str):
    s = set()
    for n in names:
        if n in s:
            raise ValueError(f"[{where}] nombre duplicado: {n}")
        s.add(n)

def validate_catalogs(res: ReservoirCatalog, gen: GeneratorsCatalog):
    ensure_names_unique(res.names, "ReservoirCatalog")
    ensure_names_unique(gen.HG_all, "GeneratorsCatalog")

def _check_arcs(arcs: List[Tuple[str,str]], left: Set[str], right: Set[str], tag: str):
    bad_src, bad_dst = [], []
    for u, v in arcs:
        if u not in left:
            bad_src.append(u)
        if v not in right:
            bad_dst.append(v)
    if bad_src or bad_dst:
        msgs = []
        if bad_src:
            msgs.append("orígenes desconocidos: " + str(sorted(set(bad_src))[:10]) + (" ..." if len(set(bad_src))>10 else ""))
        if bad_dst:
            msgs.append("destinos desconocidos: " + str(sorted(set(bad_dst))[:10]) + (" ..." if len(set(bad_dst))>10 else ""))
        raise ValueError(f"[Graph:{tag}] " + " | ".join(msgs))

def validate_graph(
    graph: HydroGraph,
    res: ReservoirCatalog,
    gen: GeneratorsCatalog,
    *,
    extra_nodes: Iterable[str] = (),
    allow_unknown_natural: bool = True,
):
    """
    - Valida arcos spill/turb entre RES↔RES y RES→HG (según corresponda).
    - Para arcos 'natural':
        * Si allow_unknown_natural=True (por defecto), solo se verifica formato básico (no falla por nodos fuera de catálogos).
        * Si False, se valida contra RES ∪ HG ∪ extra_nodes.
    """
    all_res = set(res.names)
    all_hg  = set(gen.HG_all)

    # Validaciones “duras”
    _check_arcs(graph.arcs_spill_res,   all_res, all_res, "spill_res")
    _check_arcs(graph.arcs_turb_res,    all_res, all_res, "turb_res")
    _check_arcs(graph.arcs_spill_to_hg, all_res, all_hg,  "spill_to_hg")
    _check_arcs(graph.arcs_turb_to_hg,  all_res, all_hg,  "turb_to_hg")

    # Natural: por defecto, no fallar por nodos fuera de catálogos
    if not allow_unknown_natural:
        known = all_res | all_hg | set(extra_nodes or [])
        _check_arcs(graph.arcs_natural, known, known, "natural")
    else:
        # chequeo suave: que no haya nombres vacíos u origin==dest
        for (u, v) in graph.arcs_natural:
            if not u or not v:
                raise ValueError("[Graph:natural] hay arco con nombre vacío")
            if u == v:
                raise ValueError(f"[Graph:natural] lazo trivial u==v en '{u}'")