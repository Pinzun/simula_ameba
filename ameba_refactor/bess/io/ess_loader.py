"""Rutinas de lectura para sistemas de almacenamiento (ESS).

El archivo CSV de ESS contiene toda la información de configuración de cada
unidad de almacenamiento.  Este módulo transforma ese archivo en un
diccionario de dataclasses que resulta fácil de consumir por las etapas
posteriores del modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pandas as pd


@dataclass(frozen=True)
class ESSUnit:
    """Representa una unidad de almacenamiento eléctrica individual.

    Cada campo refleja una columna del CSV de entrada. Se prefiere un
    dataclass inmutable para evitar modificaciones accidentales durante el
    pipeline y mantener una descripción clara de cada parámetro físico o
    económico.
    """

    name: str
    busbar: str
    pmax_dis: float  # Potencia máxima de descarga (columna ``pmax``)
    pmax_ch: float  # Potencia máxima de carga (columna ``ess_pmaxc``)
    pmin_dis: float  # Potencia mínima de descarga segura
    pmin_ch: float  # Potencia mínima de carga controlada
    vomc: float  # Costo variable operativo en $/MWh
    auxserv: float  # Consumo auxiliar como fracción de la potencia
    e_ini: float  # Energía inicial almacenada en MWh
    e_max: float  # Capacidad máxima de almacenamiento
    e_min: float  # Capacidad mínima operativa
    eff_c: float  # Eficiencia de carga (valor específico o ``ess_effn``)
    eff_d: float  # Eficiencia de descarga
    cycle_neutral: bool  # Si la unidad debe cerrar balance dentro de la etapa


def _to_bool(value: object) -> bool:
    """Normaliza entradas tipo texto/numérico al booleano esperado."""

    return str(value).strip().lower() in {"true", "1", "t", "yes", "y"}


def load_ess_assets(path_csv: Path) -> Dict[str, ESSUnit]:
    """Carga el catálogo de ESS desde ``path_csv`` y lo mapea a :class:`ESSUnit`.

    Pasos principales de la rutina:
    1. Leer el CSV y normalizar los nombres de columnas a minúsculas.
    2. Recorrer cada fila, aplicando conversión numérica defensiva con
       valores por defecto cuando hay datos faltantes.
    3. Ajustar eficiencias de carga/descarga: si no se encuentran valores
       específicos se reutiliza ``ess_effn``.
    4. Registrar cada unidad en un diccionario indexado por su nombre.
    """

    df = pd.read_csv(path_csv)
    df.columns = [c.strip().lower() for c in df.columns]

    def get_value(row: pd.Series, key: str, default: float = 0.0) -> float:
        """Obtiene ``row[key]`` como ``float`` y usa ``default`` si está vacío."""

        value = row.get(key, default)
        return float(value) if pd.notna(value) else float(default)

    units: Dict[str, ESSUnit] = {}
    for _, raw_row in df.iterrows():
        name = str(raw_row["name"])
        effn = get_value(raw_row, "ess_effn", 1.0)
        effc = get_value(raw_row, "ess_effc", effn)
        effd = get_value(raw_row, "ess_effd", effn)
        units[name] = ESSUnit(
            name=name,
            busbar=str(raw_row.get("busbar", "")),
            pmax_dis=get_value(raw_row, "pmax", 0.0),
            pmax_ch=get_value(raw_row, "ess_pmaxc", 0.0),
            pmin_dis=get_value(raw_row, "pmin", 0.0),
            pmin_ch=get_value(raw_row, "ess_pminc", 0.0),
            vomc=get_value(raw_row, "vomc_avg", 0.0),
            auxserv=get_value(raw_row, "auxserv", 0.0),
            e_ini=get_value(raw_row, "ess_eini", 0.0),
            e_max=get_value(raw_row, "ess_emax", 0.0),
            e_min=get_value(raw_row, "ess_emin", 0.0),
            eff_c=effc,
            eff_d=effd,
            cycle_neutral=_to_bool(raw_row.get("ess_intrastage_balance", False)),
        )

    return units
