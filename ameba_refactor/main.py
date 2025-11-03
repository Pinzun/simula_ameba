# main.py
from pathlib import Path
from typing import Dict
import pandas as pd

# --- rutas base
from core.config import DATA_DIR

# --- calendario
from core import load_stages, load_blocks, ModelCalendar

# --- profiles (PV/Wind usan perfiles horarios)
from profiles.io import ProfilePowerStore

# --- red
from network.io import load_busbars, load_branches, load_system
from network.core.validators import validate_network

# --- demanda
from demand.io import load_loads
from demand.modeling import DemandStore

# --- generación
from pv.io import load_pv_generators
from wind.io import load_wind_generators
from thermal.io import FuelStore, load_thermal_generators

# --- ESS
from bess.io import load_ess_assets

# --- HYDRO
from hydro.io.dam_loader import load_dam
from hydro.io.hydrogenerator_loader import load_hydrogenerator
from hydro.io.hydrogroup_loader import load_hydrogroup
from hydro.io.hydroconn_loader import load_hydroconnection
from hydro.io.hydronode_loader import load_hydronode
from hydro.core.graph import build_graph
from hydro.core.validators import (
    validate_catalogs as validate_hydro_catalogs,
    validate_graph as validate_hydro_graph,
)
from hydro.io.inflow_loader import (
    load_inflow_nodes, load_irrigation_nodes,
    load_inflow_series_long, aggregate_inflows_to_blocks
)
from hydro.core.aggregate import aggregate_hydro_to_blocks
from hydro.core.calendar_adapter import make_calendar_data

from export.io_model import export_model_inputs

def load_inflow_alias(path_csv: Path) -> Dict[str, str]:
    """Carga alias opcionales para mapear inflows Afl_* -> Emb_* o HG_*."""
    if not Path(path_csv).exists():
        return {}
    df = pd.read_csv(path_csv)
    df.columns = [c.strip().lower() for c in df.columns]
    need = {"name", "target"}
    miss = [c for c in need if c not in set(df.columns)]
    if miss:
        raise ValueError(f"[inflow_alias.csv] faltan columnas: {miss}")
    df["name"] = df["name"].astype(str).str.strip().str.lower()
    df["target"] = df["target"].astype(str).str.strip()
    return dict(zip(df["name"], df["target"]))


def main():
    # 1) Calendario
    stages_df = load_stages(DATA_DIR / "stages.csv")
    blocks_assign = load_blocks(stages_df, DATA_DIR / "blocks.csv").copy()

    # columnas mínimas
    need = ["stage", "block", "time_str"]
    for c in need:
        if c not in blocks_assign.columns:
            raise AssertionError(f"[blocks.csv] falta columna requerida: {c}")

    blocks_assign["time_str"] = blocks_assign["time_str"].astype(str).str.strip()
    if "time" not in blocks_assign.columns:
        blocks_assign["time"] = pd.to_datetime(
            blocks_assign["time_str"], format="%Y-%m-%d-%H:%M", errors="raise"
        )

    if "y" not in blocks_assign.columns:
        blocks_assign["y"] = blocks_assign["stage"].astype(int)
    if "t" not in blocks_assign.columns:
        blocks_assign["t"] = blocks_assign["block"].astype(int)

    # asegura dtype Timestamp coherente
    blocks_assign["time"] = pd.to_datetime(
        blocks_assign["time_str"], format="%Y-%m-%d-%H:%M", errors="raise"
    )

    # catálogo de bloques (una fila por (stage,block))
    gb = blocks_assign.groupby(["stage", "block"], as_index=False)["time"].min()
    gb = gb.rename(columns={"time": "start_time"})
    gb["end_time"] = gb["start_time"] + pd.Timedelta(hours=2)
    gb["label"] = gb["block"].astype(int).map(lambda x: f"B{x:02d}")
    gb["duration_h"] = 2.0

    blocks_meta = gb[["stage", "block", "label", "start_time", "end_time", "duration_h"]].copy()
    blocks_meta["stage"] = blocks_meta["stage"].astype(int)
    blocks_meta["block"] = blocks_meta["block"].astype(int)

    cal = ModelCalendar.from_frames(
        stages_df=stages_df,
        blocks_df=blocks_meta,
        blocks_assignments_df=blocks_assign,
    )

    # 2) Profiles (matriz time x Profile_*)
    pstore = ProfilePowerStore.from_power_csv(DATA_DIR / "power.csv")

    # 3) Red eléctrica
    busbars  = load_busbars(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Busbar.csv")
    branches = load_branches(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Branch.csv")
    system   = load_system(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_System.csv")
    validate_network(busbars, branches, system)

    # 4) Demanda
    _ = load_loads(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Load.csv")  # valida mapeo
    demand_store = DemandStore.from_csvs(
        demand_series_csv=DATA_DIR / "demand.csv",
        load_csv=DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Load.csv",
        time_format="%Y-%m-%d-%H:%M",
    )
    demand_wide_block = demand_store.to_dataframe_by_block(calendar=cal)

    # 5) Generación variable (PV/Wind)
    pv_units = load_pv_generators(
        DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_PvGenerator.csv", pstore, cal
    )
    wind_units = load_wind_generators(
        DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_WindGenerator.csv", pstore, cal
    )

    # --- FuelStore (para térmicas) ---
    cb = cal.hours_df().copy()  # stage, block, time
    cb["time"] = pd.to_datetime(cb["time"], errors="coerce")
    if cb["time"].isna().any():
        bad = cb.loc[cb["time"].isna(), "time"].head(5).tolist()
        raise ValueError(f"[calendar] marcas de tiempo inválidas (ejemplos): {bad}")

    cb["time_str"] = cb["time"].dt.strftime("%Y-%m-%d-%H:%M")
    calendar_blocks = (
        cb.rename(columns={"stage": "y", "block": "t"})[["time_str", "y", "t"]]
          .drop_duplicates()
    )

    fuel_store = FuelStore.from_csv(
        path_fuel_csv=DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Fuel.csv",
        path_price_csv=DATA_DIR / "fuel_price.csv",
        calendar_blocks=calendar_blocks,
    )
    thermal_pkg = load_thermal_generators(
        DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_ThermalGenerator.csv",
        fuel_store,
    )

    # 5.bis) HYDRO – catálogos + grafo (validados primero)
    dam_rows, res_catalog = load_dam(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Dam.csv")
    hg_rows, hg_limits    = load_hydrogroup(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGroup.csv")
    gen_rows, gen_catalog = load_hydrogenerator(
        DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroGenerator.csv",
        r_names=res_catalog.names,
        ror_prefix="HG_"
    )
    conn_rows = load_hydroconnection(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroConnection.csv")
    node_rows = load_hydronode(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_HydroNode.csv")

    graph, inflow_to_res, inflow_to_hg = build_graph(conn_rows)
    inflow_to_res = {str(k).lower(): v for k, v in inflow_to_res.items()}
    inflow_to_hg  = {str(k).lower(): v for k, v in inflow_to_hg.items()}

    # Alias opcional
    alias = load_inflow_alias(DATA_DIR / "inflow_alias.csv")
    for k, tgt in alias.items():
        if tgt.startswith("Emb_"):
            inflow_to_res[k] = tgt
            inflow_to_hg.pop(k, None)
        else:
            # asumimos HG_* si no empieza por Emb_
            inflow_to_hg[k] = tgt
            inflow_to_res.pop(k, None)

    # Validaciones de integridad (fail-fast antes de inflows)
    validate_hydro_catalogs(res_catalog, gen_catalog)
    validate_hydro_graph(graph, res_catalog, gen_catalog)

    # --- Inflows/irrigación → bloques y HydroData ---
    # 1) Metadatos (para stats/validaciones blandas)
    inflow_rows = load_inflow_nodes(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Inflow.csv")
    irr_rows    = load_irrigation_nodes(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Irrigation.csv")

    # 2) Serie horaria larga y agregado a (y,t)
    inflow_series = load_inflow_series_long(DATA_DIR / "pelp_inflows_qm3.csv")
    if not inflow_series:
        print("[hydro] WARNING: inflow_series está vacío (revisa pelp_inflows_qm3.csv).")

    # Contadores útiles
    print(f"- Inflow nodes meta: {len(inflow_rows)} | Irrigation nodes meta: {len(irr_rows)}")
    unique_series_nodes = len({s.name for s in inflow_series})
    print(f"- Inflow series (nodos con serie): {unique_series_nodes}")

    cal_hydro = make_calendar_data(cal)  # adapter ModelCalendar -> CalendarData
    inflow_block_hm3 = aggregate_inflows_to_blocks(calendar=cal_hydro, series=inflow_series)

    # Normalización ligera de nombres y alerta de mapeo
    def _norm(s: str) -> str:
        return str(s).strip().lower()

    inflow_names = {_norm(s.name) for s in inflow_series}
    mapped = set(inflow_to_res.keys()) | set(inflow_to_hg.keys())
    unmapped = sorted(n for n in inflow_names if n not in mapped)
    if unmapped:
        print(f"[hydro] WARNING: {len(unmapped)} inflow(s) sin mapeo a Emb_/HG_: p.ej. {unmapped[:5]}")
        # Exporta TODO para completar el alias
        pd.DataFrame({"name": unmapped, "target": ""}).to_csv(DATA_DIR / "inflow_alias_todo.csv", index=False)

    irrigation_block_hm3 = {}  # si aún no tienes serie horaria de riego

    # 3) Construir paquete HydroData para el modelador
    hydro_pkg = aggregate_hydro_to_blocks(
        calendar=cal_hydro,
        res=res_catalog,
        gen=gen_catalog,
        limits=hg_limits,
        graph=graph,
        inflow_to_res=inflow_to_res,
        inflow_to_hg=inflow_to_hg,
        inflow_block_hm3=inflow_block_hm3,
        irrigation_block_hm3=irrigation_block_hm3,
    )

    # 4) Checks rápidos de sanidad de inflows
    print(f"- Inflows en bloques: {len(inflow_block_hm3):,} claves (Afl_*/(y,t))")
    try:
        s1 = int(cal.blocks_df["stage"].min())
        tot_s1 = sum(q for (node, (y, t)), q in inflow_block_hm3.items() if y == s1)
        print(f"- Total inflow Hm3 en stage {s1}: {tot_s1:,.3f}")
    except Exception:
        pass

    # 6) BESS
    ess_assets = load_ess_assets(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_ESS.csv")

    # 7) Listo para “modeling”
    print("OK ✓ calendar, network, demand, PV, Wind, Thermal, ESS cargados")

    # --- calendario
    try:
        n_blocks_total = cal.n_blocks_total()
    except AttributeError:
        n_blocks_total = int(cal.blocks_df.drop_duplicates(["stage", "block"]).shape[0])
    print(f"- Stages: {cal.n_stages()}  Bloques totales: {n_blocks_total}")

    # --- demanda por bloques
    print(f"- Demand (bloques) shape: {getattr(demand_wide_block, 'shape', ('?', '?'))}")

    # --- térmicas
    try:
        n_thermal = len(thermal_pkg["units_df"])
    except Exception:
        n_thermal = "?"
    print(f"- Thermal units: {n_thermal}")

    # --- PV / Wind
    def _count_plants(obj):
        if hasattr(obj, "plants") and isinstance(getattr(obj, "plants"), dict):
            return len(obj.plants)
        if isinstance(obj, dict):
            return len(obj)
        return "?"
    print(f"- PV/Wind: {_count_plants(pv_units)} / {_count_plants(wind_units)}")

    # --- HYDRO: contadores para confirmar carga
    print(f"- Hydro reservoirs: {len(res_catalog.names)}")
    print(f"- Hydro groups limits: {len(hg_limits.sp_min)} con límites definidos")
    print(f"- Hydro generators (HG_all): {len(gen_catalog.HG_all)}")
    print(f"- Hydro connections: {len(conn_rows)}  | Hydro nodes: {len(node_rows)}")
    print(f"- inflow_to_res: {len(inflow_to_res)}  | inflow_to_hg: {len(inflow_to_hg)}")

    # --- ESS
    try:
        n_ess = len(ess_assets)
    except Exception:
        n_ess = "?"
    print(f"- ESS assets: {n_ess}")

    export_model_inputs(
    out_dir=DATA_DIR / "model_inputs",
    cal_blocks_df=cal.blocks_df.assign(
        start_time=pd.to_datetime(cal.blocks_df["start_time"]),
        end_time=pd.to_datetime(cal.blocks_df["end_time"]),
    )[["stage","block","start_time","end_time","duration_h"]],
    cal_assign_df=cal.blocks_assignments_df[["stage","block","time"]],
    demand_wide_block=demand_wide_block,
    busbars=busbars, branches=branches, system=system,
    thermal_pkg=thermal_pkg,
    pv_units=pv_units, wind_units=wind_units,
    inflow_block_hm3=inflow_block_hm3,
    )
    print(f"✓ Export OK → {DATA_DIR / 'model_inputs'}")    

if __name__ == "__main__":
    main()