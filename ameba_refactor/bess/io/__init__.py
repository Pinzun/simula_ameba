"""Utilidades de entrada/salida para activos de almacenamiento eléctrico.

Este paquete concentra las funciones necesarias para cargar los archivos
de entrada asociados a sistemas ESS (Energy Storage Systems).  Se expone
un único punto de acceso llamado :func:`load_ess_assets`, que transforma
los CSV de definición de activos en estructuras de Python listas para ser
consumidas por el resto del pipeline.
"""

from .ess_loader import load_ess_assets

__all__ = ["load_ess_assets"]
