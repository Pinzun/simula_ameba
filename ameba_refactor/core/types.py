# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Tuple, Dict, Iterable, Optional

# Identificadores semánticos
UnitId = NewType("UnitId", str)
BusId  = NewType("BusId", str)

@dataclass(frozen=True)
class Stage:
    """Stage de planificación (e.g., día o mes)."""
    s_id: int             # índice entero del stage
    start_time: str         # inicio del stage p.ej. '2025-01-01-00:00' 
    end_time: int          # fin del stage '2025-02-01-00:00' cada stage dura un mes exacto
    num_blocks: int        # cantidad de bloques de la stage, siempre es 24

@dataclass(frozen=True)
class Block:
    """Bloque intrastage (p.ej., hora, bloque típico)."""
    stage: int           # identifíca a que stage corresponde el bloque
    block: str          # indentifica el bloque
    time: int           # inicio del bloque ej: 2025-03-27-09:00. Cada bloque dura una hora exacta



