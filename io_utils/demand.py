# io_utils/demand.py

from __future__ import annotations
from pathlib import Path
import pandas as pd

def load_demand(csv_path: str | Path):
    """
    Espera data/processed/demand.csv con columnas:
      node, stage, block, demand_mwh
    Devuelve:
      - demand_mwh: dict[(node, s, b)] -> MWh del bloque
      - nodes: set de nodos
      - df: DataFrame consolidado (para inspección)
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)

    req = {"node", "stage", "block", "demand_mwh"}
    faltan = req - set(df.columns)
    assert not faltan, f"Faltan columnas en {csv_path.name}: {sorted(faltan)}"

    df["stage"] = df["stage"].astype(int)
    df["block"] = df["block"].astype(int)
    df["node"]  = df["node"].astype(str).str.strip()

    # consolida por si hay duplicados
    gdf = (df.groupby(["node", "stage", "block"], as_index=False)["demand_mwh"]
             .sum()
             .sort_values(["node", "stage", "block"])
             .reset_index(drop=True))

    demand_mwh = {(r.node, int(r.stage), int(r.block)): float(r.demand_mwh)
                  for r in gdf.itertuples(index=False)}
    nodes = set(gdf["node"].unique())

    return dict(df=gdf, nodes=nodes, demand_mwh=demand_mwh)


def log_demand_info(dmd: dict, blocks_data: dict, logger, sample: int = 3):
    lg = logger
    gdf = dmd["df"]
    lg.info("demand(nodos-MWh): %d filas (node, stage, block)", len(gdf))
    if len(gdf):
        lg.info("head: %s", gdf.head(sample).to_dict(orient="records"))
        lg.info("tail: %s", gdf.tail(sample).to_dict(orient="records"))

    # Totales MWh por año usando StageYear del calendario
    stage_year = blocks_data["stage_year"]
    total_by_year, total_all = {}, 0.0
    for (nd, s, b), mwh in dmd["demand_mwh"].items():
        y = stage_year[s]
        total_by_year[y] = total_by_year.get(y, 0.0) + mwh
        total_all += mwh

    for y in sorted(total_by_year):
        lg.info("Demanda total %s: %.3f MWh", y, total_by_year[y])
    lg.info("Demanda total (horizonte): %.3f MWh", total_all)
    lg.info("Nodos con demanda: %d (muestra): %s",
            len(dmd["nodes"]), sorted(dmd["nodes"])[:10])
