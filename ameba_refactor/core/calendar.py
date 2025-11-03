# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Tuple

import pandas as pd

# Este calendar NO asume patrón uniforme. Mantiene:
# - stages_df:             s_id,start_time,end_time,num_blocks,start_ts,end_ts
# - blocks_df:             stage,block,start_time,end_time   (bloques de 2h)
# - blocks_assignments_df: stage,block,time                  (detalle horario tal cual)

@dataclass
class ModelCalendar:
    stages_df: pd.DataFrame
    blocks_df: pd.DataFrame
    blocks_assignments_df: pd.DataFrame

    # ---------- Constructores ----------
    @classmethod
    def from_frames(
        cls,
        stages_df: pd.DataFrame,
        blocks_df: pd.DataFrame,
        blocks_assignments_df: pd.DataFrame,
    ) -> "ModelCalendar":
        # Validaciones mínimas de columnas
        need_stages = {"s_id", "start_time", "end_time", "start_ts", "end_ts", "num_blocks"}
        need_blocks = {"stage", "block", "start_time", "end_time"}
        need_assign = {"stage", "block", "time"}

        def _check(df: pd.DataFrame, need: set, name: str):
            miss = [c for c in need if c not in df.columns]
            if miss:
                raise AssertionError(f"[{name}] faltan columnas: {miss}")

        _check(stages_df, need_stages, "Stages")
        _check(blocks_df, need_blocks, "Blocks")
        _check(blocks_assignments_df, need_assign, "BlocksAssignments")

        # Copias ordenadas por sanidad
        S = stages_df.sort_values("s_id").reset_index(drop=True).copy()
        B = blocks_df.sort_values(["stage", "block"]).reset_index(drop=True).copy()
        A = blocks_assignments_df.sort_values(["stage", "block", "time"]).reset_index(drop=True).copy()

        return cls(S, B, A)

    @classmethod
    def from_files(
        cls,
        stages_csv: str | Path,
        blocks_csv: str | Path,
        tz: str = "America/Santiago",
        block_duration_h: int = 2,
    ) -> "ModelCalendar":
        # Import local para evitar ciclos
        from .io import load_stages, load_blocks_with_hourly_assignments

        stages_df = load_stages(stages_csv, tz=tz)
        blocks_df, blocks_assignments_df = load_blocks_with_hourly_assignments(
            stages_df,
            blocks_csv,
            block_duration_h=block_duration_h,
            tz=tz,
        )
        return cls.from_frames(stages_df, blocks_df, blocks_assignments_df)

    # ---------- Helpers de consulta ----------
    def n_stages(self) -> int:
        return int(self.stages_df["s_id"].nunique())

    def n_blocks_total(self) -> int:
        # cuenta (stage,block) distintos
        return int(self.blocks_df.drop_duplicates(["stage", "block"]).shape[0])

    def iter_hours_in_block(self, stage: int, block: int) -> Iterator[str]:
        """Itera las marcas 'time' (str) dentro de un bloque concreto."""
        sel = self.blocks_assignments_df
        sub = sel[(sel["stage"] == stage) & (sel["block"] == block)]
        for t in sub["time"]:
            yield str(t)

    def block_window(self, stage: int, block: int) -> Tuple[str, str]:
        """Retorna (start_time, end_time) del bloque (strings con el mismo formato de entrada)."""
        sub = self.blocks_df[(self.blocks_df["stage"] == stage) & (self.blocks_df["block"] == block)]
        if sub.empty:
            raise KeyError(f"Bloque inexistente (stage={stage}, block={block}).")
        row = sub.iloc[0]
        return str(row["start_time"]), str(row["end_time"])

    def map_time_to_stage_block(self, time_str: str) -> Optional[Tuple[int, int]]:
        """
        Mapea una marca horaria exacta a (stage, block).
        Devuelve None si esa hora no está en blocks_assignments_df.
        """
        sel = self.blocks_assignments_df
        sub = sel[sel["time"] == time_str]
        if sub.empty:
            return None
        # Si apareciera más de una (no debería), toma la primera
        row = sub.iloc[0]
        return int(row["stage"]), int(row["block"])
    '''
    def iter_blocks(self) -> Iterator[Tuple[int, int]]:
    """Itera (stage, block) existentes (no el producto cartesiano)."""
    for r in self.blocks_df.itertuples(index=False):
        yield int(r.stage), int(r.block)

    def hours_df(self) -> pd.DataFrame:
        """Devuelve un DataFrame (detalle) con todas las horas mapeadas a (stage, block)."""
        return self.blocks_assignments_df.copy()

    def blocks_view(self) -> pd.DataFrame:
        """Devuelve un DataFrame (agregado a 2h) con (stage, block, start_time, end_time)."""
        return self.blocks_df.copy()

    def stages_view(self) -> pd.DataFrame:
        """Devuelve el DataFrame de stages."""
        return self.stages_df.copy()
        '''