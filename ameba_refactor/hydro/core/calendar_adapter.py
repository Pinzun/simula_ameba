# -*- coding: utf-8 -*-
# hydro/core/calendar_adapter.py
from __future__ import annotations
from typing import Any
import pandas as pd
from .calendar_types import CalendarData, CalendarBlock

def make_calendar_data(cal: Any) -> CalendarData:
    """
    Adapter desde tu ModelCalendar (core.calendar.ModelCalendar) a CalendarData (hidro).
    Espera que cal.hours_df() devuelva columnas: ['stage','block','time'] (una fila por hora).
    """
    df = cal.hours_df().copy()
    # Asegura tipos
    df["stage"] = df["stage"].astype(int)
    df["block"] = df["block"].astype(int)
    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
    if df["time"].isna().any():
        bad = df.loc[df["time"].isna(), "time"].head(5).tolist()
        raise ValueError(f"[make_calendar_data] marcas de tiempo inválidas (ejemplos): {bad}")

    # En el calendario horario, cada fila es UNA hora → duration_h = 1.0
    blocks = [
        CalendarBlock(
            stage=int(r.stage),
            block=int(r.block),
            time=r.time,           # Timestamp
            duration_h=1.0,
        )
        for r in df.itertuples(index=False)
    ]
    return CalendarData(blocks=blocks)