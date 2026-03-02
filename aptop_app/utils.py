from __future__ import annotations

import subprocess


def run_cmd(cmd: list[str], timeout: float = 0.8) -> str:
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=timeout)
        return out.strip()
    except Exception:
        return ""


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def human_rate(value_bps: float) -> str:
    units = ["B/s", "KB/s", "MB/s", "GB/s", "TB/s"]
    v = max(0.0, value_bps)
    idx = 0
    while v >= 1024.0 and idx < len(units) - 1:
        v /= 1024.0
        idx += 1
    if idx == 0:
        return f"{v:.0f} {units[idx]}"
    return f"{v:.2f} {units[idx]}"
