# main.py
from pathlib import Path

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
from demand.io import load_loads, load_demand_factors, load_demand_series
from demand.modeling import DemandStore

# --- generación
from pv.io import load_pv_generators
from wind.io import load_wind_generators
from thermal.io import FuelStore, load_thermal_generators

# --- ESS
from bess.io import load_ess_assets
import pandas as pd


def main():
    # 1) Calendario
    stages_df = load_stages(DATA_DIR / "stages.csv")
    # Debe traer al menos: ['stage','block','time_str'] y ojalá 'time'
    blocks_assign = load_blocks(stages_df, DATA_DIR / "blocks.csv").copy()

    # Normaliza columnas mínimas
    need = ["stage", "block", "time_str"]
    for c in need:
        if c not in blocks_assign.columns:
            raise AssertionError(f"[blocks.csv] falta columna requerida: {c}")

    blocks_assign["time_str"] = blocks_assign["time_str"].astype(str).str.strip()
    if "time" not in blocks_assign.columns:
        blocks_assign["time"] = pd.to_datetime(
            blocks_assign["time_str"], format="%Y-%m-%d-%H:%M", errors="raise"
        )
    # Alias (y,t) por compatibilidad
    if "y" not in blocks_assign.columns:
        blocks_assign["y"] = blocks_assign["stage"].astype(int)
    if "t" not in blocks_assign.columns:
        blocks_assign["t"] = blocks_assign["block"].astype(int)

    # 1) blocks_assign: ya tiene ['stage','block','time_str','time', 'y','t'].
    #    Garantiza los tipos y orden.
    blocks_assign["time"] = pd.to_datetime(blocks_assign["time_str"], format="%Y-%m-%d-%H:%M", errors="raise")

    # 2) Construimos el catálogo de bloques (una fila por (stage, block))
    #    Regla: cada bloque = 2 horas → end_time = start_time + 2h
    gb = blocks_assign.groupby(["stage", "block"], as_index=False)["time"].min()
    gb = gb.rename(columns={"time": "start_time"})
    gb["end_time"] = gb["start_time"] + pd.Timedelta(hours=2)

    # (opcional) etiqueta del bloque
    gb["label"] = gb["block"].astype(int).map(lambda x: f"B{x:02d}")

    # duración en horas (constante 2.0)
    gb["duration_h"] = 2.0

    # Normaliza tipos/columnas requeridas por el calendario
    blocks_meta = gb[["stage", "block", "label", "start_time", "end_time", "duration_h"]].copy()
    blocks_meta["stage"] = blocks_meta["stage"].astype(int)
    blocks_meta["block"] = blocks_meta["block"].astype(int)




    # Construye calendario (API actual espera 3 dataframes)
    cal = ModelCalendar.from_frames(
        stages_df=stages_df,
        blocks_df=blocks_meta,
        blocks_assignments_df=blocks_assign,
    )

    # 2) Profiles (matriz time x Profile_*)
    pstore = ProfilePowerStore.from_power_csv(DATA_DIR / "power.csv")

    # 3) Red eléctrica
    busbars = load_busbars(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Busbar.csv")
    branches = load_branches(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Branch.csv")
    system = load_system(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_System.csv")
    validate_network(busbars, branches, system)

    # 4) Demanda
    _ = load_loads(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Load.csv")  # solo para validar mapeo
    demand_store = DemandStore.from_csvs(
        demand_series_csv=DATA_DIR / "demand.csv",
        load_csv=DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Load.csv",
        time_format="%Y-%m-%d-%H:%M",
    )
    #demand_by_block = demand_store.build_by_block(calendar=cal, fill_missing_as_zero=True)
    demand_wide_block = demand_store.to_dataframe_by_block(calendar=cal)

    # 5) Generación
    pv_units = load_pv_generators(
        DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_PvGenerator.csv", pstore
    )
    wind_units = load_wind_generators(
        DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_WindGenerator.csv", pstore
    )

    # Combustibles y térmicas
    fuel_store = FuelStore.from_csv(
        path_fuel_csv=DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_Fuel.csv",
        path_price_csv=DATA_DIR / "fuel_price.csv",
        calendar_blocks=cal.hours_df(),  # expone ['time_str','time','y','t']
    )
    thermal_pkg = load_thermal_generators(
        DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_ThermalGenerator.csv",
        fuel_store,
    )

    # BESS
    ess_assets = load_ess_assets(DATA_DIR / "PNCP 2 - 2025 ESC-C  - PET 2024 V2_ESS.csv")

    # 6) Listo para “modeling”
    print("OK ✓ calendar, network, demand, PV, Wind, Thermal, ESS cargados")
    print(f"- Stages: {cal.n_stages()}  Blocks/día: {cal.n_blocks()}")
    print(f"- Demand (bloques) shape: {demand_wide_block.shape}")
    print(f"- Thermal units: {len(thermal_pkg['units_df'])}")
    print(f"- PV/Wind: {len(pv_units)} / {len(wind_units)}")
    print(f"- ESS assets: {len(ess_assets)}")


if __name__ == "__main__":
    main()