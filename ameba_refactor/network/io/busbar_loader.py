# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict
import pandas as pd
from network.core.types import BusbarRow

def load_busbars(path_csv: Path) -> Dict[str, BusbarRow]:
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]
    out: Dict[str, BusbarRow] = {}
    for _, r in df.iterrows():
        name = str(r["name"])
        voltage = float(r.get("voltage", 0))
        voll = r.get("prices", None)  # en tu archivo `prices` = 0; si prefieres VOLL por Load lo ajustamos después
        voll_f = float(voll) if pd.notna(voll) else None
        out[name] = BusbarRow(name=name, voltage=voltage, voll=voll_f)
    return out