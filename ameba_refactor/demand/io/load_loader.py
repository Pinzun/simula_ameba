# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import pandas as pd

@dataclass(frozen=True)
class LoadRow:
    name: str            # "L_Cumbre500"
    busbar: str          # "Cumbre500"
    projection_key: str  # "Proj_Cumbre500"
    voll: float | None

def load_loads(path_csv: Path) -> Dict[str, LoadRow]:
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]
    out: Dict[str, LoadRow] = {}
    for _, r in df.iterrows():
        if not bool(r.get("connected", True)):
            continue
        name = str(r["name"])
        busbar = str(r["busbar"])
        proj   = str(r.get("projection_type", ""))
        voll   = r.get("voll", None)
        voll_f = float(voll) if pd.notna(voll) else None
        out[name] = LoadRow(name, busbar, proj, voll_f)
    return out