from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ProcRow:
    pid: int
    user: str
    mem_gb: float
    cpu_pct: float
    command: str


@dataclass
class SystemMetrics:
    cpu_pct: float
    mem_used_pct: float
    mem_cached_pct: float
    mem_free_pct: float
    mem_used_gb: float
    mem_total_gb: float
    disk_used_pct: float
    swap_used_pct: float
    net_down_pct: float
    net_up_pct: float
    net_down_human: str
    net_up_human: str
    proc_rows: List[ProcRow]


@dataclass
class PowerMetrics:
    gpu_util_pct: Optional[float]
    gpu_mem_util_pct: Optional[float]
    gpu_core_utils: List[float]
    gpu_core_count: int
    cpu_watts: Optional[float]
    gpu_watts: Optional[float]
    ane_watts: Optional[float]
    power_source: str
    battery_pct: Optional[float]
    battery_state: str
    adapter_watts: Optional[float]
    adapter_volts: Optional[float]
    adapter_amps: Optional[float]
    powermetrics_ok: bool
    powermetrics_error: str


@dataclass
class PanelData:
    cpu: deque[float]
    gpu: deque[float]
    mem_used_pct: float
    mem_cached_pct: float
    mem_free_pct: float
    mem_used_gb: float
    mem_total_gb: float
    disk_used_pct: float
    swap_used_pct: float
    net_up: deque[float]
    net_down: deque[float]
    net_up_human: str
    net_down_human: str
    proc_rows: List[ProcRow]
    power: PowerMetrics
    gpu_label: str
    cpu_core_utils: List[float]
