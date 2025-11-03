# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict
import pandas as pd
from network.core.types import BranchRow

def load_branches(path_csv: Path) -> Dict[str, BranchRow]:
    df = pd.read_csv(path_csv)
    df.columns = [c.strip() for c in df.columns]
    out: Dict[str, BranchRow] = {}
    for _, r in df.iterrows():
        if not bool(r.get("connected", True)):
            continue
        name = str(r["name"])
        bi = str(r["busbari"])
        bj = str(r["busbarf"])
        x  = float(r["x"])
        fmax_ab = float(r.get("max_flow", 0.0))
        fmax_ba = float(r.get("max_flow_reverse", fmax_ab))
        dc = bool(r.get("dc", True))
        losses = bool(r.get("losses", False))
        out[name] = BranchRow(name=name, bus_i=bi, bus_j=bj, x=x,
                              fmax_ab=fmax_ab, fmax_ba=fmax_ba, dc=dc, losses=losses)
    return out