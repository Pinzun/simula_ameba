

#scripts/crea_demand.py
"""
Genera data/processed/demand.csv (formato largo: node,stage,block,demand_mwh)
a partir de:
- data/raw/demand.csv  (wide: time, scenario, L_<Barra>..., en MWh/hora)
- data/raw/factor.csv  (wide: time, Proj_<Barra>..., adimensional)

Requisitos:
- data/processed/blocks.csv con filas HORARIAS y columnas: stage, block, start_time
  (start_time en "%Y-%m-%d-%H:%M"). Cada (stage,block) agrupa N horas (2 en tu caso).
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path

def build_demand_from_raw(
    ruta_demanda_raw: Path,
    ruta_factor_raw: Path,
    ruta_blocks: Path,
    ruta_out: Path,
    registrar_csv: bool = True,
) -> pd.DataFrame:
    # 1) Cargar
    demanda_raw = pd.read_csv(ruta_demanda_raw)
    factor_raw  = pd.read_csv(ruta_factor_raw)
    blocks_raw  = pd.read_csv(ruta_blocks)

    # 2) Normalizaciones mínimas
    demanda_raw["time_dt"] = pd.to_datetime(demanda_raw["time"], format="%Y-%m-%d-%H:%M")
    factor_raw["time_dt"]  = pd.to_datetime(factor_raw["time"],  format="%Y-%m-%d-%H:%M")

    demanda_raw["anio_base"] = demanda_raw["time_dt"].dt.year
    factor_raw["anio"]       = factor_raw["time_dt"].dt.year

    # Limpia prefijos (L_ y Proj_)
    demanda_raw.columns = demanda_raw.columns.str.replace(r"^L_", "", regex=True)
    factor_raw.columns  = factor_raw.columns.str.replace(r"^Proj_", "", regex=True)

    # Columnas de barras
    cols_excluir_demanda = {"time", "scenario", "anio_base", "time_dt"}
    bar_cols_demanda = [c for c in demanda_raw.columns if c not in cols_excluir_demanda]

    cols_excluir_factor = {"time", "anio", "time_dt"}
    bar_cols_factor = [c for c in factor_raw.columns if c not in cols_excluir_factor]

    barras = sorted(set(bar_cols_demanda).intersection(set(bar_cols_factor)))
    if not barras:
        raise ValueError("No hay barras comunes entre demand.csv y factor.csv tras limpiar prefijos.")

    # 3) Formato largo y proyección (energía base * factor)
    base_long = (
        demanda_raw[["time_dt", "anio_base"] + barras]
        .melt(id_vars=["time_dt", "anio_base"], var_name="node", value_name="energy_base_mwh")
    )

    factor_long = (
        factor_raw[["time_dt", "anio"] + barras]
        .melt(id_vars=["time_dt", "anio"], var_name="node", value_name="factor")
    )

    df = base_long.merge(factor_long[["time_dt", "anio", "node", "factor"]], on="node", how="inner")

    # Timestamp proyectado: año objetivo + (mm-dd-HH:MM) del perfil base
    tail = df["time_dt_x"].dt.strftime("%m-%d-%H:%M")
    df["time_proj_str"] = df["anio"].astype(str) + "-" + tail
    df["time_proj"]     = pd.to_datetime(df["time_proj_str"], format="%Y-%m-%d-%H:%M", errors="coerce")
    df = df.dropna(subset=["time_proj"]).copy()

    # Energía proyectada por hora (MWh)
    df["energy_mwh"] = df["energy_base_mwh"] * df["factor"]

    # 4) Mapear a (stage, block) con blocks.csv (join exacto por hora)
    blocks = blocks_raw[["stage", "block", "start_time"]].copy()
    blocks["start_time"] = pd.to_datetime(blocks["start_time"], format="%Y-%m-%d-%H:%M", errors="coerce")

    df = df.merge(blocks, left_on="time_proj", right_on="start_time", how="inner")

    # 5) Agregar a nivel de bloque: SUMA de energía (MWh por bloque)
    demand_block = (
        df.groupby(["node", "stage", "block"], as_index=False)["energy_mwh"]
          .sum()
          .rename(columns={"energy_mwh": "demand_mwh"})
          .sort_values(["node", "stage", "block"])
          .reset_index(drop=True)
    )

    # 6) Salida
    demand_block = demand_block[["node", "stage", "block", "demand_mwh"]]

    if registrar_csv:
        ruta_out.parent.mkdir(parents=True, exist_ok=True)
        demand_block.to_csv(ruta_out, index=False, encoding="utf-8")

    return demand_block


if __name__ == "__main__":
    base = Path(__file__).parent.parent
    ruta_demanda_raw = base / "data" / "raw" / "demand.csv"
    ruta_factor_raw  = base / "data" / "raw" / "factor.csv"
    ruta_blocks      = base / "data" / "processed" / "blocks.csv"
    ruta_out         = base / "data" / "processed" / "demand.csv"

    out_df = build_demand_from_raw(
        ruta_demanda_raw,
        ruta_factor_raw,
        ruta_blocks,
        ruta_out,
        registrar_csv=True,
    )
    print(out_df.head(10).to_string(index=False))
    print("[OK] demand.csv generado en", ruta_out)
