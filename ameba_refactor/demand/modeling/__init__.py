"""Punto de acceso a las rutinas de modelación de demanda.

Se exponen las funciones y clases que generan perfiles de demanda
agregados según el calendario del modelo.  Este archivo evita a los
consumidores conocer la estructura interna del paquete ``demand.modeling``.
"""

from .demand_builder import build_demand, DemandStore

__all__ = ["build_demand", "DemandStore"]
