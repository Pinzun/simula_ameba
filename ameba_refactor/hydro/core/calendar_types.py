# -*- coding: utf-8 -*-
# hydro/core/calendar_types.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Iterable

TimeIndex = Tuple[int, int]  # (stage, block)

@dataclass(frozen=True)
class CalendarBlock:
    stage: int
    block: int
    time: "object"          # str o datetime; el adapter decide
    duration_h: float       # duración de la hora (normalmente 1.0)

@dataclass(frozen=True)
class CalendarData:
    """
    Contenedor simple que usa el módulo hidro:
      - blocks: lista de horas con su (stage, block) y duración_h de **la hora**
    """
    blocks: List[CalendarBlock]

    def iter_blocks(self) -> Iterable[TimeIndex]:
        seen = set()
        for b in self.blocks:
            key = (int(b.stage), int(b.block))
            if key not in seen:
                seen.add(key)
                yield key