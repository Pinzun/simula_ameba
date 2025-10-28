# carga_hydroconnection.py
from pathlib import Path
import pandas as pd

def load_hydro_connection(path: Path):
    """
    Devuelve:
      - inflow_to_reservoir: dict Afl_* -> Emb_* (h_type='inflow' a embalse)
      - inflow_to_hg:        dict Afl_* -> HG_*  (h_type='inflow' a generador)
      - arcs_spill_res:      list[(Emb_u, Emb_d)]                 # SIN delay (para usar hoy)
      - arcs_turb_res:       list[(Emb_u, Emb_d)]                 # SIN delay (para usar hoy)
      - arcs_spill_to_hg:    list[(Emb_u, HG_g)]                  # SIN delay (para usar hoy)
      - arcs_turb_to_hg:     list[(Emb_u, HG_g)]                  # SIN delay (para usar hoy)
      - arcs_spill_res_d:    list[(Emb_u, Emb_d, delay_h)]        # CON delay (para “futuro”)
      - arcs_turb_res_d:     list[(Emb_u, Emb_d, delay_h)]        # CON delay (para “futuro”)
      - arcs_spill_to_hg_d:  list[(Emb_u, HG_g, delay_h)]         # CON delay (para “futuro”)
      - arcs_turb_to_hg_d:   list[(Emb_u, HG_g, delay_h)]         # CON delay (para “futuro”)
    """
    hc = pd.read_csv(path)
    hc.columns = [c.strip().lower() for c in hc.columns]

    def s(x): return str(x).strip()

    inflow_to_reservoir = {}
    inflow_to_hg = {}

    arcs_spill_res, arcs_turb_res = [], []
    arcs_spill_to_hg, arcs_turb_to_hg = [], []

    arcs_spill_res_d, arcs_turb_res_d = [], []
    arcs_spill_to_hg_d, arcs_turb_to_hg_d = [], []

    for _, r in hc.iterrows():
        htype = s(r["h_type"]).lower()
        ini   = s(r["ini"])
        end   = s(r["end"])
        delay = float(r.get("h_delay", 0) or 0.0)

        if htype == "inflow":
            if end.startswith("Emb_"):
                inflow_to_reservoir[ini] = end
            elif end.startswith("HG_"):
                inflow_to_hg[ini] = end

        elif htype in ("overflow", "spilled"):
            if end.startswith("Emb_"):
                arcs_spill_res.append((ini, end))
                arcs_spill_res_d.append((ini, end, delay))
            elif end.startswith("HG_"):
                arcs_spill_to_hg.append((ini, end))
                arcs_spill_to_hg_d.append((ini, end, delay))

        elif htype == "turbinated":
            if ini.startswith("Emb_") and end.startswith("Emb_"):
                arcs_turb_res.append((ini, end))
                arcs_turb_res_d.append((ini, end, delay))
            elif ini.startswith("Emb_") and end.startswith("HG_"):
                arcs_turb_to_hg.append((ini, end))
                arcs_turb_to_hg_d.append((ini, end, delay))

    return (inflow_to_reservoir, inflow_to_hg,
            arcs_spill_res, arcs_turb_res, arcs_spill_to_hg, arcs_turb_to_hg,
            arcs_spill_res_d, arcs_turb_res_d, arcs_spill_to_hg_d, arcs_turb_to_hg_d)