from __future__ import annotations

import re
import shutil
import time
from typing import List

from aptop_app.models import ProcRow, SystemMetrics
from aptop_app.utils import clamp, human_rate, run_cmd


class SystemCollector:
    def __init__(self) -> None:
        self.total_mem_bytes = self._read_total_mem()
        self.default_if = self._default_interface()

        self.last_net_ts = 0.0
        self.last_net_in = 0
        self.last_net_out = 0
        self.peak_down_bps = 1.0
        self.peak_up_bps = 1.0

    def _read_total_mem(self) -> int:
        out = run_cmd(["sysctl", "-n", "hw.memsize"])
        try:
            return int(out)
        except ValueError:
            return 0

    def _default_interface(self) -> str:
        out = run_cmd(["route", "-n", "get", "default"])
        for line in out.splitlines():
            if "interface:" in line:
                return line.split("interface:", 1)[1].strip()
        return "en0"

    def _cpu_percent(self) -> float:
        out = run_cmd(["top", "-l", "1", "-n", "0"], timeout=1.4)
        m = re.search(r"CPU usage:\s*([0-9.]+)% user,\s*([0-9.]+)% sys,\s*([0-9.]+)% idle", out)
        if not m:
            return 0.0
        try:
            idle = float(m.group(3))
            return clamp(100.0 - idle)
        except ValueError:
            return 0.0

    def _memory(self) -> tuple[float, float, float, float, float]:
        vm = run_cmd(["vm_stat"])
        if not vm:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        page_size = 4096
        m_page = re.search(r"page size of\s+(\d+)\s+bytes", vm)
        if m_page:
            page_size = int(m_page.group(1))

        stats: dict[str, int] = {}
        for line in vm.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value_num = "".join(ch for ch in value if ch.isdigit())
            if value_num:
                stats[key.strip()] = int(value_num)

        free = stats.get("Pages free", 0)
        speculative = stats.get("Pages speculative", 0)
        inactive = stats.get("Pages inactive", 0)
        purgeable = stats.get("Pages purgeable", 0)
        active = stats.get("Pages active", 0)
        wired = stats.get("Pages wired down", 0)
        compressed = stats.get("Pages occupied by compressor", 0)

        used_pages = active + wired + compressed
        cached_pages = inactive + speculative + purgeable
        free_pages = free

        used_bytes = used_pages * page_size
        cached_bytes = cached_pages * page_size
        free_bytes = free_pages * page_size

        total_bytes = self.total_mem_bytes if self.total_mem_bytes > 0 else max(1, used_bytes + cached_bytes + free_bytes)
        used_pct = clamp((used_bytes / total_bytes) * 100.0)
        cached_pct = clamp((cached_bytes / total_bytes) * 100.0)
        free_pct = clamp((free_bytes / total_bytes) * 100.0)

        return used_pct, cached_pct, free_pct, used_bytes / (1024**3), total_bytes / (1024**3)

    def _disk(self) -> tuple[float, float]:
        du = shutil.disk_usage("/")
        used_pct = clamp((du.used / max(1, du.total)) * 100.0)

        swap_out = run_cmd(["sysctl", "vm.swapusage"])
        swap_used_pct = 0.0
        m = re.search(r"used\s*=\s*([0-9.]+)([MGT])", swap_out)
        t = re.search(r"total\s*=\s*([0-9.]+)([MGT])", swap_out)
        if m and t:
            mult = {"M": 1.0, "G": 1024.0, "T": 1024.0 * 1024.0}
            used_mb = float(m.group(1)) * mult[m.group(2)]
            total_mb = float(t.group(1)) * mult[t.group(2)]
            swap_used_pct = clamp((used_mb / max(1.0, total_mb)) * 100.0)

        return used_pct, swap_used_pct

    def _interface_bytes(self) -> tuple[int, int]:
        out = run_cmd(["netstat", "-b", "-n", "-I", self.default_if])
        lines = [ln for ln in out.splitlines() if ln.strip()]
        for line in reversed(lines):
            parts = line.split()
            if len(parts) < 10:
                continue
            try:
                ibytes = int(parts[6])
                obytes = int(parts[9])
                return ibytes, obytes
            except ValueError:
                continue
        return self.last_net_in, self.last_net_out

    def _network(self) -> tuple[float, float, str, str]:
        now = time.time()
        ibytes, obytes = self._interface_bytes()

        if self.last_net_ts == 0.0:
            self.last_net_ts = now
            self.last_net_in = ibytes
            self.last_net_out = obytes
            return 0.0, 0.0, "0 B/s", "0 B/s"

        dt = max(0.001, now - self.last_net_ts)
        down_bps = max(0.0, (ibytes - self.last_net_in) / dt)
        up_bps = max(0.0, (obytes - self.last_net_out) / dt)

        self.last_net_ts = now
        self.last_net_in = ibytes
        self.last_net_out = obytes

        self.peak_down_bps = max(self.peak_down_bps * 0.997, down_bps, 1.0)
        self.peak_up_bps = max(self.peak_up_bps * 0.997, up_bps, 1.0)

        down_pct = clamp((down_bps / self.peak_down_bps) * 100.0)
        up_pct = clamp((up_bps / self.peak_up_bps) * 100.0)
        return down_pct, up_pct, human_rate(down_bps), human_rate(up_bps)

    def _processes(self, limit: int = 280) -> List[ProcRow]:
        out = run_cmd(["ps", "-Ao", "pid,user,rss,pcpu,comm"])
        rows: List[ProcRow] = []
        for line in out.splitlines()[1:]:
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                user = parts[1]
                rss_kb = int(parts[2])
                cpu_pct = float(parts[3])
                cmd = parts[4].split("/")[-1]
            except ValueError:
                continue
            rows.append(ProcRow(pid=pid, user=user, mem_gb=rss_kb / (1024 * 1024), cpu_pct=cpu_pct, command=cmd))

        rows.sort(key=lambda r: (-r.mem_gb, -r.cpu_pct, r.pid))
        return rows[:limit]

    def sample(self) -> SystemMetrics:
        cpu_pct = self._cpu_percent()
        mem_used_pct, mem_cached_pct, mem_free_pct, mem_used_gb, mem_total_gb = self._memory()
        disk_used_pct, swap_used_pct = self._disk()
        down_pct, up_pct, down_h, up_h = self._network()
        proc_rows = self._processes()

        return SystemMetrics(
            cpu_pct=cpu_pct,
            mem_used_pct=mem_used_pct,
            mem_cached_pct=mem_cached_pct,
            mem_free_pct=mem_free_pct,
            mem_used_gb=mem_used_gb,
            mem_total_gb=mem_total_gb,
            disk_used_pct=disk_used_pct,
            swap_used_pct=swap_used_pct,
            net_down_pct=down_pct,
            net_up_pct=up_pct,
            net_down_human=down_h,
            net_up_human=up_h,
            proc_rows=proc_rows,
        )
