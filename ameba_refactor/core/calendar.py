"""Calendario central del modelo AMEBA con anotaciones detalladas.

El objetivo de este módulo es encapsular el manejo del calendario
multietapas empleado por el modelo eléctrico.  Se definen estructuras
de datos para los *stages*, los bloques temporales y la asignación
horaria detallada, junto con utilidades para navegar esta información.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pandas as pd

# El calendario no presupone un patrón uniforme entre etapas. Se mantienen
# tres tablas sincronizadas:
#   * ``stages_df``  → catálogo de etapas con ventanas temporales y metadatos.
#   * ``blocks_df``  → descripción agregada de cada bloque dentro de un stage.
#   * ``blocks_assignments_df`` → detalle horario con la pertenencia de cada
#                                 hora a un bloque determinado.

@dataclass
class ModelCalendar:
    """Agrupa las tres vistas principales del calendario del modelo.

    La clase ofrece constructores en términos de ``DataFrame`` y de archivos
    CSV, además de utilidades de consulta que facilitan los cruces entre
    bloques y marcas horarias.  El uso sistemático de copias evita efectos
    laterales cuando múltiples componentes comparten la misma instancia.
    """

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
        # 1) Validaciones mínimas de columnas en cada DataFrame
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

        # 2) Copias para evitar modificar los DataFrames originales
        S = stages_df.copy()
        B = blocks_df.copy()
        A = blocks_assignments_df.copy()

        # 3) Normaliza todos los campos temporales a ``datetime64``
        S["start_time"] = pd.to_datetime(S["start_time"], errors="raise")
        S["end_time"]   = pd.to_datetime(S["end_time"],   errors="raise")
        # (start_ts/end_ts pueden quedarse como están si ya vienen numéricos)

        B["start_time"] = pd.to_datetime(B["start_time"], errors="raise")
        B["end_time"]   = pd.to_datetime(B["end_time"],   errors="raise")

        A["time"] = pd.to_datetime(A["time"], errors="raise")
        # Asegura time_str con formato estándar (para merges por texto)
        if "time_str" not in A.columns:
            A["time_str"] = A["time"].dt.strftime("%Y-%m-%d-%H:%M")
        else:
            # fuerza formato string
            A["time_str"] = A["time_str"].astype(str)

        # 4) Ordena los datos para mantener un orden determinista
        S = S.sort_values("s_id").reset_index(drop=True)
        B = B.sort_values(["stage", "block"]).reset_index(drop=True)
        A = A.sort_values(["stage", "block", "time"]).reset_index(drop=True)

        return cls(S, B, A)

    @classmethod
    def from_files(
        cls,
        stages_csv: str | Path,
        blocks_csv: str | Path,
        tz: str = "America/Santiago",
        block_duration_h: int = 2,
    ) -> "ModelCalendar":
        """Construye el calendario a partir de archivos CSV en disco.

        Se invocan los loaders reutilizables del paquete ``core.io`` y luego
        se delega en :meth:`from_frames` para la normalización.  El parámetro
        ``block_duration_h`` documenta explícitamente la duración objetivo de
        los bloques, aunque el calendario podría contener otras duraciones si
        los archivos lo definen así.
        """

        # Import local para evitar ciclos de importación con ``core.io``
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

    def iter_hours_in_block(self, stage: int, block: int) -> Iterator[pd.Timestamp]:
        """Itera las marcas 'time' (datetime64) dentro de un bloque concreto."""
        sel = self.blocks_assignments_df
        sub = sel[(sel["stage"] == stage) & (sel["block"] == block)]
        for t in sub["time"]:
            yield pd.Timestamp(t)

    def block_window(self, stage: int, block: int) -> Tuple[pd.Timestamp, pd.Timestamp]:
        """Retorna (start_time, end_time) del bloque como Timestamps."""
        sub = self.blocks_df[(self.blocks_df["stage"] == stage) & (self.blocks_df["block"] == block)]
        if sub.empty:
            raise KeyError(f"Bloque inexistente (stage={stage}, block={block}).")
        row = sub.iloc[0]
        return pd.Timestamp(row["start_time"]), pd.Timestamp(row["end_time"])

    def map_time_to_stage_block(self, time_val: str | pd.Timestamp) -> Optional[Tuple[int, int]]:
        """
        Mapea una marca horaria exacta a (stage, block).
        Devuelve None si esa hora no está en blocks_assignments_df.
        Acepta str o Timestamp.
        """
        t = pd.to_datetime(time_val, format="%Y-%m-%d-%H:%M", errors="coerce") \
            if isinstance(time_val, str) else pd.to_datetime(time_val, errors="coerce")
        if pd.isna(t):
            return None
        sel = self.blocks_assignments_df
        sub = sel[sel["time"] == t]
        if sub.empty:
            return None
        row = sub.iloc[0]
        return int(row["stage"]), int(row["block"])

    def iter_blocks(self) -> Iterator[Tuple[int, int]]:
        """Itera (stage, block) existentes (no el producto cartesiano)."""
        for r in self.blocks_df.drop_duplicates(["stage","block"]).itertuples(index=False):
            yield int(r.stage), int(r.block)

    def hours_df(self) -> pd.DataFrame:
        """
        Devuelve un DataFrame (detalle) con todas las horas mapeadas a (stage, block).
        Columnas garantizadas: ['stage','block','time','time_str'].
        """
        cols = ["stage", "block", "time", "time_str"]
        miss = [c for c in cols if c not in self.blocks_assignments_df.columns]
        if miss:
            raise AssertionError(f"[ModelCalendar.hours_df] faltan columnas: {miss}")
        df = self.blocks_assignments_df[cols].copy()
        # asegura tipos
        df["time"] = pd.to_datetime(df["time"], errors="raise")
        df["time_str"] = df["time_str"].astype(str)
        return df

    def blocks_view(self) -> pd.DataFrame:
        """Devuelve un DataFrame (agregado a 2h) con (stage, block, start_time, end_time)."""
        cols = ["stage","block","start_time","end_time"]
        miss = [c for c in cols if c not in self.blocks_df.columns]
        if miss:
            raise AssertionError(f"[ModelCalendar.blocks_view] faltan columnas: {miss}")
        df = self.blocks_df[cols].copy()
        df["start_time"] = pd.to_datetime(df["start_time"], errors="raise")
        df["end_time"]   = pd.to_datetime(df["end_time"],   errors="raise")
        return df

    def stages_view(self) -> pd.DataFrame:
        """Devuelve el DataFrame de stages."""
        return self.stages_df.copy()