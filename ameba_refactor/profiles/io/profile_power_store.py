# -*- coding: utf-8 -*-
# profiles/io/profile_power_store.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Literal, Optional
import pandas as pd
import numpy as np

_TIME_FORMATS = ("%Y-%m-%d-%H:%M", "%Y-%m-%d %H:%M")

def _parse_time(s: str) -> pd.Timestamp:
    s = str(s)
    for fmt in _TIME_FORMATS:
        try:
            return pd.to_datetime(s, format=fmt)
        except ValueError:
            pass
    # fallback robusto (más lento pero tolerante)
    return pd.to_datetime(s)

def _norm_cols(cols) -> list[str]:
    # normaliza nombres tipo 'profile_x' vs 'Profile_X' y quita espacios
    return [str(c).strip() for c in cols]

@dataclass
class ProfilePowerStore:
    """
    Mantiene una matriz time x profile con valores (p.u. normalmente).
    - power_wide: DataFrame con index datetime y columnas = nombres de perfiles.
    """
    power_wide: pd.DataFrame  # index=time (datetime64[ns]), cols=profile names

    # ---------- Carga ----------
    @classmethod
    def from_power_csv(cls, power_csv: Path) -> "ProfilePowerStore":
        df = pd.read_csv(power_csv)
        df.columns = _norm_cols(df.columns)
        if "time" not in df.columns:
            raise AssertionError("[power.csv] falta columna 'time'.")

        # Parse de tiempo y orden
        df["time"] = df["time"].map(_parse_time)
        df = df.sort_values("time").set_index("time")

        # Remueve 'scenario' si existe
        if "scenario" in df.columns:
            df = df.drop(columns=["scenario"])

        # Asegura numérico (perfiles muy ruidosos a veces vienen como 'str')
        df = df.apply(pd.to_numeric, errors="coerce")

        # Columnas normalizadas
        df.columns = _norm_cols(df.columns)
        return cls(power_wide=df)

    # ---------- Agregación a nivel de bloque ----------
    def _aggregate_by_block(
        self,
        blocks_df: pd.DataFrame,
        agg: Literal["mean", "median"] = "mean",
        missing_policy: Literal["zero", "ignore"] = "ignore",
    ) -> pd.DataFrame:
        """
        Devuelve un DataFrame con índice MultiIndex (stage, block) y
        columnas = perfiles, con el valor agregado por bloque (p.u.).

        - agg: "mean" (default) o "median".
        - missing_policy:
            * "ignore": promedia solo timestamps presentes (NaN se ignoran).
            * "zero": timestamps ausentes se rellenan con 0 antes de agregar.
        """
        need = {"stage", "block", "time"}
        if not need.issubset(set(blocks_df.columns)):
            faltan = sorted(need - set(blocks_df.columns))
            raise AssertionError(f"[blocks_df] faltan columnas {faltan}.")

        blk = blocks_df.copy()
        blk["time"] = blk["time"].map(_parse_time)

        # Para eficiencia: agrupamos las horas por (stage, block) una vez
        grouped = blk.groupby(["stage", "block"])["time"].apply(list)

        # Preparamos salida
        profiles = list(self.power_wide.columns)
        out = pd.DataFrame(index=grouped.index, columns=profiles, dtype=float)

        # Acceso rápido
        pw = self.power_wide

        for (y, t), ts_list in grouped.items():
            ts_idx = pd.DatetimeIndex(ts_list)
            # Reindex estricta a los timestamps del bloque
            # No usamos método de relleno; controlamos abajo con missing_policy
            sample = pw.reindex(ts_idx)

            if missing_policy == "zero":
                sample = sample.fillna(0.0)

            if agg == "mean":
                vals = sample.mean(axis=0, skipna=True)
            else:  # "median"
                vals = sample.median(axis=0, skipna=True)

            out.loc[(y, t)] = vals.to_numpy(dtype=float, copy=False)

        # MultiIndex ordenado
        out.index = pd.MultiIndex.from_tuples(out.index, names=["stage", "block"])
        out = out.sort_index()
        return out

    # ---------- API principal para el modelo ----------
    def build_af_by_block(
        self,
        blocks_df: pd.DataFrame,
        plant_to_profile: Dict[str, str],
        agg: Literal["mean", "median"] = "mean",
        missing_policy: Literal["zero", "ignore"] = "ignore",
        clip_range: Tuple[float, float] = (0.0, 1.0),
    ) -> Dict[Tuple[str, int, int], float]:
        """
        Devuelve {(plant, stage, block) -> AF_bloque}.

        - Usa el promedio (o mediana) del perfil en las horas que componen cada bloque.
        - Si un profile no existe en power_wide:
            * AF = 0.0 (comportamiento explícito; así no explotamos).
        - missing_policy controla cómo tratamos horas del bloque sin dato en power:
            * "ignore": se promedia solo con las horas existentes.
            * "zero": se asume 0.0 para las horas faltantes (recomendado cuando el bloque debe estar completo).
        - clip_range recorta el resultado a [0,1] por sanidad.
        """
        # Preagregamos todas las columnas por bloque una sola vez
        agg_df = self._aggregate_by_block(blocks_df, agg=agg, missing_policy=missing_policy)

        lo, hi = clip_range
        out: Dict[Tuple[str, int, int], float] = {}

        # Iteramos por bloque y asignamos a cada planta según su profile
        for (y, t), row in agg_df.iterrows():
            for plant, prof in plant_to_profile.items():
                prof_norm = prof.strip()  # nombre tal cual viene en tus mapeos
                if prof_norm in agg_df.columns:
                    af = row[prof_norm]
                    af = 0.0 if pd.isna(af) else float(af)
                else:
                    # perfil inexistente -> AF=0 (y podríamos loguear un warning si quieres)
                    af = 0.0
                # recorte a [0,1]
                af = float(np.clip(af, lo, hi))
                out[(plant, int(y), int(t))] = af

        return out