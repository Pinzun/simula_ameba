"""Definiciones tipadas de la red eléctrica con comentarios en español."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusbarRow:
    """Representa una barra eléctrica individual dentro del sistema."""

    name: str
    voltage: float | int
    voll: float | None = None  # Costo por energía no suministrada (opcional)


@dataclass(frozen=True)
class BranchRow:
    """Describe una línea o transformador que conecta dos barras."""

    name: str
    bus_i: str
    bus_j: str
    x: float  # Reactancia en p.u. o equivalente
    fmax_ab: float  # Límite MW i→j
    fmax_ba: float  # Límite MW j→i (puede coincidir con ``fmax_ab``)
    dc: bool = True  # Uso de formulación DC según el archivo de entrada
    losses: bool = False  # Ignorado en DC puro; reservado para futuras extensiones


@dataclass(frozen=True)
class SystemRow:
    """Parámetros globales de la red eléctrica."""

    sbase: float
    busbar_ref: str
    interest_rate: float | None = None
