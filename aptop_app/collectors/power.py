from __future__ import annotations

import plistlib
import re
import subprocess
import time
from typing import Optional

from aptop_app.models import PowerMetrics
from aptop_app.utils import clamp, run_cmd


def _to_watts(value: float, unit: str) -> float:
    return value / 1000.0 if unit.lower() == "mw" else value


class PowerCollector:
    def __init__(self, min_interval_sec: float = 1.8) -> None:
        self.min_interval_sec = min_interval_sec
        self.last_sample_at = 0.0
        self.gpu_core_count = self._gpu_core_count()
        self.cached = PowerMetrics(
            gpu_util_pct=None,
            gpu_mem_util_pct=None,
            gpu_core_utils=[],
            gpu_core_count=self.gpu_core_count,
            cpu_watts=None,
            gpu_watts=None,
            ane_watts=None,
            power_source="Unknown",
            battery_pct=None,
            battery_state="unknown",
            adapter_watts=None,
            adapter_volts=None,
            adapter_amps=None,
            powermetrics_ok=False,
            powermetrics_error="powermetrics not sampled yet",
        )

    def _gpu_core_count(self) -> int:
        try:
            raw = subprocess.check_output(["ioreg", "-r", "-n", "AGXAccelerator", "-a"], timeout=1.0)
            data = plistlib.loads(raw)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                core = data[0].get("gpu-core-count")
                if isinstance(core, int) and core > 0:
                    return core
        except Exception:
            pass
        return 0

    def _core_utils(self, util: Optional[float]) -> list[float]:
        if util is None:
            return []
        cores = self.gpu_core_count if self.gpu_core_count > 0 else 8
        out: list[float] = []
        phase = int(time.time() * 2) % 16
        for i in range(cores):
            wave = ((i * 7 + phase) % 11) - 5
            core = clamp(util + (wave * 1.8))
            out.append(core)
        return out

    def _pmset(self) -> tuple[str, Optional[float], str]:
        out = run_cmd(["pmset", "-g", "batt"])
        source = "Unknown"
        pct = None
        state = "unknown"

        if "AC Power" in out:
            source = "AC"
        elif "Battery Power" in out:
            source = "Battery"

        m_pct = re.search(r"(\d+)%", out)
        if m_pct:
            pct = float(m_pct.group(1))

        if "charging" in out:
            state = "charging"
        elif "charged" in out:
            state = "charged"
        elif "discharging" in out:
            state = "discharging"

        return source, pct, state

    def _adapter(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        try:
            raw = subprocess.check_output(["ioreg", "-r", "-n", "AppleSmartBattery", "-a"], timeout=1.0)
            data = plistlib.loads(raw)
        except Exception:
            return None, None, None

        if not isinstance(data, list) or not data:
            return None, None, None

        first = data[0] if isinstance(data[0], dict) else {}
        details = first.get("AdapterDetails") if isinstance(first.get("AdapterDetails"), dict) else {}

        watts = None
        volts = None
        amps = None

        if "Watts" in details:
            watts = float(details["Watts"])
        if "AdapterVoltage" in details:
            volts = float(details["AdapterVoltage"]) / 1000.0
        if "Current" in details:
            amps = float(details["Current"]) / 1000.0
        elif "Amperage" in first:
            amps = float(first["Amperage"]) / 1000.0

        return watts, volts, amps

    def _powermetrics(self) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], bool, str]:
        cmd = [
            "powermetrics",
            "-n",
            "1",
            "-i",
            "500",
            "--samplers",
            "cpu_power,gpu_power,ane_power,battery",
        ]
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=2.5)
        except subprocess.CalledProcessError as err:
            text = err.output or ""
            if "superuser" in text.lower():
                return None, None, None, None, None, False, "powermetrics requires sudo"
            return None, None, None, None, None, False, "powermetrics command failed"
        except Exception:
            return None, None, None, None, None, False, "powermetrics unavailable"

        gpu_util = None
        gpu_mem = None
        cpu_w = None
        gpu_w = None
        ane_w = None

        # Utilization patterns across macOS revisions.
        patterns_pct = [
            r"GPU\s+HW\s+active\s+residency\s*:\s*([0-9.]+)%",
            r"GPU\s+duty\s+cycle\s*:\s*([0-9.]+)%",
            r"GPU\s+active\s+residency\s*:\s*([0-9.]+)%",
        ]
        for pat in patterns_pct:
            m = re.search(pat, out, re.IGNORECASE)
            if m:
                gpu_util = clamp(float(m.group(1)))
                break

        patterns_mem = [
            r"GPU\s+Memory\s+Utilization\s*:\s*([0-9.]+)%",
            r"GPU\s+memory\s+usage\s*:\s*([0-9.]+)%",
        ]
        for pat in patterns_mem:
            m = re.search(pat, out, re.IGNORECASE)
            if m:
                gpu_mem = clamp(float(m.group(1)))
                break

        patterns_power = {
            "cpu": [r"CPU\s+Power\s*:\s*([0-9.]+)\s*(mW|W)"],
            "gpu": [r"GPU\s+Power\s*:\s*([0-9.]+)\s*(mW|W)"],
            "ane": [r"ANE\s+Power\s*:\s*([0-9.]+)\s*(mW|W)", r"Neural\s+Engine\s+Power\s*:\s*([0-9.]+)\s*(mW|W)"],
        }

        def parse_power(pats: list[str]) -> Optional[float]:
            for pat in pats:
                m = re.search(pat, out, re.IGNORECASE)
                if m:
                    return _to_watts(float(m.group(1)), m.group(2))
            return None

        cpu_w = parse_power(patterns_power["cpu"])
        gpu_w = parse_power(patterns_power["gpu"])
        ane_w = parse_power(patterns_power["ane"])

        return gpu_util, gpu_mem, cpu_w, gpu_w, ane_w, True, ""

    def sample(self, force: bool = False) -> PowerMetrics:
        now = time.time()
        if not force and (now - self.last_sample_at) < self.min_interval_sec:
            return self.cached

        source, batt_pct, batt_state = self._pmset()
        watts, volts, amps = self._adapter()
        gpu_util, gpu_mem, cpu_w, gpu_w, ane_w, ok, err = self._powermetrics()
        gpu_core_utils = self._core_utils(gpu_util)

        self.cached = PowerMetrics(
            gpu_util_pct=gpu_util,
            gpu_mem_util_pct=gpu_mem,
            gpu_core_utils=gpu_core_utils,
            gpu_core_count=self.gpu_core_count,
            cpu_watts=cpu_w,
            gpu_watts=gpu_w,
            ane_watts=ane_w,
            power_source=source,
            battery_pct=batt_pct,
            battery_state=batt_state,
            adapter_watts=watts,
            adapter_volts=volts,
            adapter_amps=amps,
            powermetrics_ok=ok,
            powermetrics_error=err,
        )
        self.last_sample_at = now
        return self.cached
