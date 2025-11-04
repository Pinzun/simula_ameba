"""Central model data bundle aggregating all domain packages."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import pandas as pd

from core.calendar import ModelCalendar
from demand.modeling import DemandPackage
from network.core.types import BranchRow, BusbarRow, SystemRow
from pv.io import PVData
from wind.io import WindData
from thermal.io import ThermalPackage
from bess.io import ESSData
from hydro.core.types import (
    DamRow,
    HydroConnectionRow,
    HydroData,
    HydroGeneratorRow,
    HydroGroupRow,
    HydroNodeRow,
)


def _mapping_to_frame(values: Iterable[object]) -> pd.DataFrame:
    rows = [asdict(v) for v in values]
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    if "name" in frame.columns:
        frame = frame.sort_values("name")
    return frame.reset_index(drop=True)


def _dict_of_dataclasses_to_df(data: Dict[str, object]) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for obj in data.values():
        rows.append(asdict(obj))
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    if "name" in frame.columns:
        frame = frame.sort_values("name")
    return frame.reset_index(drop=True)


@dataclass
class CalendarBundle:
    calendar: ModelCalendar

    def blocks_frame(self) -> pd.DataFrame:
        blocks = self.calendar.blocks_df.copy()
        blocks["start_time"] = pd.to_datetime(blocks["start_time"], errors="raise")
        blocks["end_time"] = pd.to_datetime(blocks["end_time"], errors="raise")
        return blocks

    def hours_frame(self) -> pd.DataFrame:
        hours = self.calendar.blocks_assignments_df.copy()
        hours["time"] = pd.to_datetime(hours["time"], errors="raise")
        hours["time_str"] = hours["time"].dt.strftime("%Y-%m-%d-%H:%M")
        return hours

    def stages_frame(self) -> pd.DataFrame:
        return self.calendar.stages_df.copy()

    def unique_block_index(self) -> pd.DataFrame:
        unique = self.calendar.blocks_df[["stage", "block"]].drop_duplicates().copy()
        unique = unique.rename(columns={"stage": "y", "block": "t"})
        return unique.astype(int)

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "calendar_blocks", self.blocks_frame()
        yield "calendar_hours", self.hours_frame()
        yield "calendar_stages", self.stages_frame()


@dataclass
class NetworkBundle:
    busbars: Dict[str, BusbarRow]
    branches: Dict[str, BranchRow]
    system: SystemRow

    def busbars_frame(self) -> pd.DataFrame:
        return _dict_of_dataclasses_to_df(self.busbars).sort_values("name").reset_index(drop=True)

    def branches_frame(self) -> pd.DataFrame:
        return _dict_of_dataclasses_to_df(self.branches).sort_values("name").reset_index(drop=True)

    def system_frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(self.system)])

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "busbars", self.busbars_frame()
        yield "branches", self.branches_frame()
        yield "system", self.system_frame()


@dataclass
class DemandBundle:
    package: DemandPackage

    def demand_frame(self) -> pd.DataFrame:
        df = self.package.by_block_df
        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index()
        return df.sort_values(["stage", "block"]).reset_index(drop=True)

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "demand_wide_block", self.demand_frame()


@dataclass
class PVBundle:
    data: PVData

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "plants_pv", self.data.plants_frame()
        yield "pv_af", self.data.availability_frame()


@dataclass
class WindBundle:
    data: WindData

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "plants_wind", self.data.plants_frame()
        yield "wind_af", self.data.availability_frame()


@dataclass
class ThermalBundle:
    data: ThermalPackage

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "thermal_units", self.data.units_frame()


@dataclass
class ESSBundle:
    data: ESSData

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "ess_units", self.data.units_frame()


@dataclass
class HydroBundle:
    dam_rows: List[DamRow]
    hydro_group_rows: List[HydroGroupRow]
    generator_rows: List[HydroGeneratorRow]
    connection_rows: List[HydroConnectionRow]
    node_rows: List[HydroNodeRow]
    inflow_block_hm3: Dict[Tuple[str, Tuple[int, int]], float]
    irrigation_block_hm3: Dict[Tuple[str, Tuple[int, int]], float]
    aggregates: HydroData

    def _rows_frame(self, rows: Iterable[object]) -> pd.DataFrame:
        return _mapping_to_frame(rows)

    def inflow_frame(self) -> pd.DataFrame:
        records = [
            {"name": name, "stage": int(idx[0]), "block": int(idx[1]), "hm3": float(value)}
            for (name, idx), value in self.inflow_block_hm3.items()
        ]
        if not records:
            return pd.DataFrame(columns=["name", "stage", "block", "hm3"])
        return pd.DataFrame(records).sort_values(["name", "stage", "block"]).reset_index(drop=True)

    def irrigation_frame(self) -> pd.DataFrame:
        records = [
            {"name": name, "stage": int(idx[0]), "block": int(idx[1]), "hm3": float(value)}
            for (name, idx), value in self.irrigation_block_hm3.items()
        ]
        if not records:
            return pd.DataFrame(columns=["name", "stage", "block", "hm3"])
        return pd.DataFrame(records).sort_values(["name", "stage", "block"]).reset_index(drop=True)

    def agg_reservoir_inflows_frame(self) -> pd.DataFrame:
        data = self.aggregates.agg.I_nat_reservoir
        records = [
            {"reservoir": name, "stage": int(idx[0]), "block": int(idx[1]), "hm3": float(value)}
            for (name, idx), value in data.items()
        ]
        if not records:
            return pd.DataFrame(columns=["reservoir", "stage", "block", "hm3"])
        return pd.DataFrame(records).sort_values(["reservoir", "stage", "block"]).reset_index(drop=True)

    def agg_hg_inflows_frame(self) -> pd.DataFrame:
        data = self.aggregates.agg.I_nat_hg
        records = [
            {"hydro_group": name, "stage": int(idx[0]), "block": int(idx[1]), "hm3": float(value)}
            for (name, idx), value in data.items()
        ]
        if not records:
            return pd.DataFrame(columns=["hydro_group", "stage", "block", "hm3"])
        return pd.DataFrame(records).sort_values(["hydro_group", "stage", "block"]).reset_index(drop=True)

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield "hydro_dams", self._rows_frame(self.dam_rows)
        yield "hydro_groups", self._rows_frame(self.hydro_group_rows)
        yield "hydro_generators", self._rows_frame(self.generator_rows)
        yield "hydro_connections", self._rows_frame(self.connection_rows)
        yield "hydro_nodes", self._rows_frame(self.node_rows)
        yield "inflow_block_hm3", self.inflow_frame()
        yield "irrigation_block_hm3", self.irrigation_frame()
        yield "hydro_nat_reservoir", self.agg_reservoir_inflows_frame()
        yield "hydro_nat_hg", self.agg_hg_inflows_frame()


@dataclass
class ModelBundle:
    calendar: CalendarBundle
    network: NetworkBundle
    demand: DemandBundle
    pv: Optional[PVBundle] = None
    wind: Optional[WindBundle] = None
    thermal: Optional[ThermalBundle] = None
    ess: Optional[ESSBundle] = None
    hydro: Optional[HydroBundle] = None

    def iter_export_frames(self) -> Iterator[Tuple[str, pd.DataFrame]]:
        yield from self.calendar.iter_export_frames()
        yield from self.network.iter_export_frames()
        yield from self.demand.iter_export_frames()
        if self.pv is not None:
            yield from self.pv.iter_export_frames()
        if self.wind is not None:
            yield from self.wind.iter_export_frames()
        if self.thermal is not None:
            yield from self.thermal.iter_export_frames()
        if self.ess is not None:
            yield from self.ess.iter_export_frames()
        if self.hydro is not None:
            yield from self.hydro.iter_export_frames()

    def export(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, frame in self.iter_export_frames():
            path = out_dir / f"{name}.csv"
            frame.to_csv(path, index=False)
