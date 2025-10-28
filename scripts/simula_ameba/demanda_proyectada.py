# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path

#def project_demanda(ruta_base: Path):
def project_demanda(ruta_demanda_base: Path,ruta_factor: Path, registro: bool ):
    """
    Ejecuta la proyección de demanda con la misma lógica del script compartido.
    Devuelve (ruta_out, dataframe_out) donde ruta_out es el CSV escrito.
    """
    # ================================
    # Cargar datos
    # ================================


    demanda_base = pd.read_csv(ruta_demanda_base, sep=",", encoding="utf-8")
    factor       = pd.read_csv(ruta_factor, sep=",", encoding="utf-8")

    # ================================
    # Normalización de columnas y tipos
    # ================================
    demanda_base["anio_base"] = demanda_base["time"].str.split("-").str[0].astype(int)
    factor["anio"]            = factor["time"].str.split("-").str[0].astype(int)

    # Limpia prefijos
    demanda_base.columns = demanda_base.columns.str.replace(r"^L_", "", regex=True)
    factor.columns       = factor.columns.str.replace(r"^Proj_", "", regex=True)

    # Parseo de tiempo del año base
    demanda_base["time_dt"] = pd.to_datetime(demanda_base["time"], format="%Y-%m-%d-%H:%M")

    # Identifica columnas de barras
    cols_excluir_demanda = {"time", "scenario", "anio_base", "time_dt"}
    bar_cols_demanda = [c for c in demanda_base.columns if c not in cols_excluir_demanda]

    cols_excluir_factor = {"time", "anio"}
    bar_cols_factor = [c for c in factor.columns if c not in cols_excluir_factor]

    # Intersección de barras
    barras = sorted(set(bar_cols_demanda).intersection(set(bar_cols_factor)))
    if not barras:
        raise ValueError("No hay barras comunes entre demanda_base y factor.")

    # ================================
    # Formato largo para cruzar por barra
    # ================================
    base_long = (
        demanda_base[["time_dt", "anio_base"] + barras]
        .melt(id_vars=["time_dt", "anio_base"], var_name="barra", value_name="demanda_base")
    )

    factors_long = (
        factor[["anio"] + barras]
        .melt(id_vars=["anio"], var_name="barra", value_name="factor")
    )

    # ================================
    # Cruce (replica cada hora del año base para todos los años del factor)
    # ================================
    df = base_long.merge(factors_long, on="barra", how="inner")

    # ================================
    # Construir el timestamp proyectado
    # ================================
    stamp_tail = df["time_dt"].dt.strftime("%m-%d-%H:%M")
    df["time_proj_str"] = df["anio"].astype(str) + "-" + stamp_tail
    df["time_proj"] = pd.to_datetime(df["time_proj_str"], format="%Y-%m-%d-%H:%M", errors="coerce")

    # Descarta fechas inválidas (29-feb no bisiesto)
    df = df.dropna(subset=["time_proj"]).copy()

    # ================================
    # Proyección: demanda_base * factor
    # ================================
    df["demanda_proj"] = df["demanda_base"] * df["factor"]

    # ================================
    # Tabla ancha final
    # ================================
    out_wide = (
        df.pivot_table(index="time_proj", columns="barra", values="demanda_proj", aggfunc="first")
        .sort_index()
        .reset_index()
    )

    # Año objetivo y columna time
    out_wide["anio_objetivo"] = out_wide["time_proj"].dt.year
    out_wide["time"] = out_wide["time_proj"].dt.strftime("%Y-%m-%d-%H:%M")

    # Reordenar columnas
    cols_finales = ["time", "anio_objetivo"] + [c for c in out_wide.columns if c not in {"time", "anio_objetivo", "time_proj"}]
    out_wide = out_wide[cols_finales]
    out_wide = out_wide.drop(columns={"anio_objetivo"})

    # Guardar CSV consolidado
    ruta_base = Path(__file__).parent.parent.parent
    ruta_out = ruta_base / "resultados" / "demanda_proyectada_ameba.csv"
    ruta_out.parent.mkdir(parents=True, exist_ok=True)
    if registro == True:
        out_wide.to_csv(ruta_out, index=False, encoding="utf-8")

    return out_wide

if __name__ == "__main__":
    base = Path(__file__).parent.parent.parent
    ruta_demanda = base / "data" / "demanda" / "demand.csv"
    ruta_factor  = base / "data" / "demanda" / "factor.csv"
    out_wide = project_demanda(ruta_demanda, ruta_factor, registro=True)
    print(out_wide.head())
    print(f"[OK] Archivo generado")