# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import pandas as pd
from network.core.types import SystemRow

def load_system(path_csv: Path) -> SystemRow:
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]
    r = df.iloc[0]
    return SystemRow(
        sbase=float(r["sbase"]),
        busbar_ref=str(r["busbar_ref"]),
        interest_rate=float(r.get("interest_rate", 0.0)),
    )