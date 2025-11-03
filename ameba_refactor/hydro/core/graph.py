# hydro/core/graph.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, List, Tuple
from hydro.core.types import HydroConnectionRow, HydroGraph

def _norm(s: str | None) -> str:
    return (s or "").strip()

def _norm_type(s: str | None) -> str:
    """Normaliza el tipo de conexión a un set pequeño de etiquetas."""
    t = _norm(s).lower()
    # alias frecuentes → etiqueta canónica
    if t in {"spill", "derrame"}:
        return "spill"
    if t in {"turb", "turbine", "turbinado"}:
        return "turb"
    if t in {"nat", "natural"}:
        return "nat"
    if t in {"pump", "pumping"}:
        return "pump"
    return "other"

def build_graph(conns: List[HydroConnectionRow]) -> Tuple[HydroGraph, Dict[str, str], Dict[str, str]]:
    """
    Construye los arcos del grafo hidráulico y devuelve además:
      - inflow_to_reservoir: mapeo Afl_* → Emb_* (si aplica)
      - inflow_to_hg:       mapeo Afl_* → HG_*  (si aplica)

    Reglas:
      - Si ini comienza por 'Afl_' y end por 'Emb_' => inflow_to_reservoir[ini] = end
      - Si ini comienza por 'Afl_' y end por 'HG_'  => inflow_to_hg[ini]        = end
      - Arcos se clasifican por h_type normalizado: 'spill' | 'turb' | 'nat' | 'pump' | 'other'
        y por destino (Emb_ vs HG_) cuando aplica.
    """
    arcs_spill_res: List[Tuple[str, str]] = []
    arcs_turb_res:  List[Tuple[str, str]] = []
    arcs_spill_to_hg: List[Tuple[str, str]] = []
    arcs_turb_to_hg:  List[Tuple[str, str]] = []
    arcs_nat:        List[Tuple[str, str]] = []
    # Si en el futuro quieres distinguir bombas, puedes añadir listas específicas
    # arcs_pump_res: List[Tuple[str, str]] = []
    # arcs_pump_to_hg: List[Tuple[str, str]] = []

    inflow_to_res: Dict[str, str] = {}
    inflow_to_hg:  Dict[str, str] = {}

    # Para detectar conflictos de mapeo Afl_* (múltiples destinos)
    afl_res_targets: Dict[str, set] = {}
    afl_hg_targets:  Dict[str, set] = {}

    for r in conns:
        ht = _norm_type(r.h_type)
        u  = _norm(r.ini)
        v  = _norm(r.end)

        # Mapeos de afluentes → destino
        if u.startswith("Afl_"):
            if v.startswith("Emb_"):
                afl_res_targets.setdefault(u, set()).add(v)
                # si ya existía y coincide, se mantiene; si hay múltiples, lo avisamos abajo
                inflow_to_res[u] = v
            elif v.startswith("HG_"):
                afl_hg_targets.setdefault(u, set()).add(v)
                inflow_to_hg[u] = v

        # Clasificación de arcos según tipo y destino
        if ht == "spill":
            if v.startswith("Emb_"):
                arcs_spill_res.append((u, v))
            else:
                arcs_spill_to_hg.append((u, v))
        elif ht == "turb":
            if v.startswith("Emb_"):
                arcs_turb_res.append((u, v))
            else:
                arcs_turb_to_hg.append((u, v))
        elif ht == "nat":
            arcs_nat.append((u, v))
        elif ht == "pump":
            # Si luego quieres modelar reversas/trasvases, podrías separarlo:
            # if v.startswith("Emb_"): arcs_pump_res.append((u, v))
            # else: arcs_pump_to_hg.append((u, v))
            arcs_nat.append((u, v))  # por ahora, tratar como natural (neutral)
        else:
            # 'other': ignóralo o clasifícalo como natural neutro
            arcs_nat.append((u, v))

    # Avisos de conflictos de mapeo (no detienen la ejecución, solo informan)
    for afl, targets in afl_res_targets.items():
        if len(targets) > 1:
            print(f"[HydroGraph][WARN] Afluente {afl} mapea a múltiples Emb_: {sorted(targets)}. "
                  f"Usando {inflow_to_res[afl]}.")
    for afl, targets in afl_hg_targets.items():
        if len(targets) > 1:
            print(f"[HydroGraph][WARN] Afluente {afl} mapea a múltiples HG_: {sorted(targets)}. "
                  f"Usando {inflow_to_hg[afl]}.")

    graph = HydroGraph(
        arcs_spill_res=arcs_spill_res,
        arcs_turb_res=arcs_turb_res,
        arcs_spill_to_hg=arcs_spill_to_hg,
        arcs_turb_to_hg=arcs_turb_to_hg,
        arcs_natural=arcs_nat,
    )
    return graph, inflow_to_res, inflow_to_hg