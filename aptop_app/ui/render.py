from __future__ import annotations

import curses
import time
from collections import deque
from typing import Optional

from aptop_app.models import PanelData, PowerMetrics, ProcRow


MIN_H = 28
MIN_W = 110


def init_colors() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)
    curses.init_pair(6, curses.COLOR_WHITE, -1)
    curses.init_pair(7, curses.COLOR_BLUE, -1)


def pct_color(p: float) -> int:
    if p < 60:
        return curses.color_pair(1)
    if p < 85:
        return curses.color_pair(2)
    return curses.color_pair(3)


def safe_addstr(stdscr: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or x < 0 or y >= max_y or x >= max_x:
        return
    clipped = text[: max(0, max_x - x)]
    if not clipped:
        return
    try:
        stdscr.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def draw_box(stdscr: curses.window, y: int, x: int, h: int, w: int, title: str) -> None:
    if h < 3 or w < 6:
        return
    safe_addstr(stdscr, y, x, "+" + "-" * (w - 2) + "+", curses.color_pair(1))
    for i in range(1, h - 1):
        safe_addstr(stdscr, y + i, x, "|", curses.color_pair(1))
        safe_addstr(stdscr, y + i, x + w - 1, "|", curses.color_pair(1))
    safe_addstr(stdscr, y + h - 1, x, "+" + "-" * (w - 2) + "+", curses.color_pair(1))
    if len(title) < (w - 4):
        safe_addstr(stdscr, y, x + 2, title, curses.A_BOLD)


def draw_sparkline(stdscr: curses.window, y: int, x: int, h: int, w: int, values: deque[float], label: str, color: int) -> None:
    if h < 4 or w < 12:
        return
    safe_addstr(stdscr, y, x, label, curses.A_BOLD | color)
    chars = " .:-=+*#%@"
    data = list(values)
    if not data:
        return
    step = max(1, len(data) // max(1, (w - 2)))
    sliced = data[-(w - 2) * step :]
    cols = [sum(sliced[i : i + step]) / step for i in range(0, len(sliced), step)]
    cols = cols[-(w - 2) :]
    for i, p in enumerate(cols):
        level = int((p / 100.0) * (len(chars) - 1))
        level = max(0, min(len(chars) - 1, level))
        bar_h = int((p / 100.0) * (h - 2))
        bar_h = max(1, bar_h)
        ch = chars[level]
        for j in range(bar_h):
            yy = y + h - 2 - j
            if yy <= y:
                break
            safe_addstr(stdscr, yy, x + 1 + i, ch, pct_color(p))


def draw_mirror_graph(stdscr: curses.window, y: int, x: int, h: int, w: int, values: deque[float], label: str) -> None:
    if h < 6 or w < 20:
        return
    safe_addstr(stdscr, y, x, label, curses.A_BOLD | curses.color_pair(4))
    data = list(values)
    if not data:
        return

    baseline = y + (h // 2)
    safe_addstr(stdscr, baseline, x + 1, "-" * max(0, w - 2), curses.color_pair(2))

    step = max(1, len(data) // max(1, (w - 2)))
    sliced = data[-(w - 2) * step :]
    cols = [sum(sliced[i : i + step]) / step for i in range(0, len(sliced), step)]
    cols = cols[-(w - 2) :]

    top_room = max(1, baseline - (y + 1))
    bot_room = max(1, (y + h - 2) - baseline)
    for i, p in enumerate(cols):
        up = max(1, int((p / 100.0) * top_room))
        dn = max(1, int((p / 100.0) * bot_room))
        col = pct_color(p)
        for j in range(up):
            safe_addstr(stdscr, baseline - 1 - j, x + 1 + i, "█", col)
        for j in range(dn):
            safe_addstr(stdscr, baseline + 1 + j, x + 1 + i, "█", col)


def draw_progress(stdscr: curses.window, y: int, x: int, w: int, label: str, pct: float, color: int) -> None:
    if w < 16:
        return
    bar_w = max(6, w - 18)
    fill = int((pct / 100.0) * bar_w)
    fill = max(0, min(bar_w, fill))
    safe_addstr(stdscr, y, x, f"{label:<8}", curses.A_BOLD)
    safe_addstr(stdscr, y, x + 8, "[" + "#" * fill + "-" * (bar_w - fill) + "]", color)
    safe_addstr(stdscr, y, x + 10 + bar_w, f"{pct:5.1f}%")


def draw_processes(stdscr: curses.window, y: int, x: int, h: int, w: int, rows: list[ProcRow], scroll_offset: int) -> None:
    if h < 6 or w < 30:
        return
    safe_addstr(stdscr, y + 1, x + 2, "PID    USER     MEM↓    CPU   PROCESS", curses.A_BOLD)
    visible = h - 4
    if not rows:
        return
    start = scroll_offset % len(rows)
    ordered = rows[start:] + rows[:start]
    for i, row in enumerate(ordered[:visible]):
        line = f"{row.pid:<6} {row.user[:8]:<8} {row.mem_gb:>4.1f}G  {row.cpu_pct:>5.1f}%  {row.command}"
        color = curses.color_pair(1) if i % 2 == 0 else curses.color_pair(7)
        safe_addstr(stdscr, y + 2 + i, x + 2, line[: max(1, w - 4)], color)


def _fmt_opt_w(value: Optional[float]) -> str:
    return "--" if value is None else f"{value:.2f}W"


def _fmt_opt(value: Optional[float], suffix: str) -> str:
    return "--" if value is None else f"{value:.2f}{suffix}"


def draw_power_block(stdscr: curses.window, y: int, x: int, w: int, p: PowerMetrics) -> None:
    if w < 40:
        return
    batt = "--" if p.battery_pct is None else f"{p.battery_pct:.0f}%"
    status = f"{p.power_source}/{p.battery_state}"
    safe_addstr(stdscr, y, x, f"PWR {status:<18} BAT {batt:>4}", curses.A_BOLD)
    safe_addstr(stdscr, y + 1, x, f"CPU {_fmt_opt_w(p.cpu_watts):>8}  GPU {_fmt_opt_w(p.gpu_watts):>8}  ANE {_fmt_opt_w(p.ane_watts):>8}")
    safe_addstr(stdscr, y + 2, x, f"ADP {_fmt_opt_w(p.adapter_watts):>8}  V {_fmt_opt(p.adapter_volts, 'V'):>8}  A {_fmt_opt(p.adapter_amps, 'A'):>8}")
    if p.powermetrics_ok:
        safe_addstr(stdscr, y + 3, x, "powermetrics: OK", curses.color_pair(1))
    else:
        safe_addstr(stdscr, y + 3, x, f"powermetrics: {p.powermetrics_error}", curses.color_pair(2))


def _draw_small_bar(stdscr: curses.window, y: int, x: int, w: int, pct: float) -> None:
    bar_w = max(8, w)
    fill = int((pct / 100.0) * bar_w)
    fill = max(0, min(bar_w, fill))
    safe_addstr(stdscr, y, x, "█" * fill + "·" * (bar_w - fill), pct_color(pct))


def draw_top_detail(stdscr: curses.window, y: int, x: int, w: int, h: int, data: PanelData) -> None:
    if w < 44 or h < 10:
        return
    draw_box(stdscr, y, x, h, w, "M-series")
    p = data.power
    cpu_total = data.cpu[-1] if data.cpu else 0.0
    gpu_total = data.gpu[-1] if data.gpu else 0.0
    safe_addstr(stdscr, y + 1, x + 2, f"CPU {cpu_total:5.1f}%   GPU {gpu_total:5.1f}%", curses.A_BOLD)
    mem_lbl = "--" if p.gpu_mem_util_pct is None else f"{p.gpu_mem_util_pct:4.1f}%"
    safe_addstr(stdscr, y + 2, x + 2, f"GPU mem util: {mem_lbl}  cores: {len(p.gpu_core_utils) or p.gpu_core_count or 0}")
    safe_addstr(stdscr, y + 3, x + 2, f"GPU W: {_fmt_opt_w(p.gpu_watts)}  CPU W: {_fmt_opt_w(p.cpu_watts)}  ANE W: {_fmt_opt_w(p.ane_watts)}")

    rows = min((h - 5), max(len(data.cpu_core_utils), len(p.gpu_core_utils), 1))
    if rows <= 0:
        return
    for i in range(rows):
        cy = y + 4 + i
        c = data.cpu_core_utils[i] if i < len(data.cpu_core_utils) else 0.0
        g = p.gpu_core_utils[i] if i < len(p.gpu_core_utils) else 0.0
        safe_addstr(stdscr, cy, x + 2, f"C{i:02d}", curses.color_pair(6))
        _draw_small_bar(stdscr, cy, x + 6, 8, c)
        safe_addstr(stdscr, cy, x + 15, f"{c:4.0f}%")
        safe_addstr(stdscr, cy, x + 21, f"G{i:02d}", curses.color_pair(6))
        _draw_small_bar(stdscr, cy, x + 25, 8, g)
        safe_addstr(stdscr, cy, x + 34, f"{g:4.0f}%")


def draw_ui(
    stdscr: curses.window,
    data: PanelData,
    interval_ms: int,
    default_if: str,
    frame: int,
    manual_scroll: int,
    auto_scroll: bool,
) -> None:
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    if max_y < MIN_H or max_x < MIN_W:
        safe_addstr(stdscr, 1, 2, f"aptop requires at least {MIN_W}x{MIN_H} terminal size.", curses.A_BOLD)
        safe_addstr(stdscr, 3, 2, f"Current: {max_x}x{max_y}")
        safe_addstr(stdscr, 5, 2, "Resize terminal and rerun.")
        stdscr.refresh()
        return

    now = time.strftime("%H:%M:%S")
    header = (
        f" aptop  phase-3  {now}  load {data.load_avg}  up {data.uptime}  iface {default_if}"
        f"  q quit  r reset  j/k scroll  a auto({str(auto_scroll).lower()})  {interval_ms}ms "
    )
    safe_addstr(stdscr, 0, 1, header[: max_x - 2], curses.A_BOLD | curses.color_pair(6))

    top_h = max_y // 2
    bottom_h = max_y - top_h - 1

    draw_box(stdscr, 1, 0, top_h, max_x, "1 cpu + gpu")

    graph_h = top_h - 4
    graph_w = max_x - 4
    cpu_h = graph_h // 2
    gpu_h = graph_h - cpu_h
    detail_w = min(56, max(44, max_x // 3))
    graph_w = max(20, graph_w - detail_w - 1)
    draw_mirror_graph(stdscr, 3, 2, cpu_h, graph_w, data.cpu, f"CPU {data.cpu[-1]:5.1f}%")
    draw_sparkline(stdscr, 3 + cpu_h, 2, gpu_h, graph_w, data.gpu, data.gpu_label, curses.color_pair(5))

    draw_top_detail(stdscr, 2, max_x - detail_w - 2, detail_w, top_h - 2, data)

    by = 1 + top_h
    left_w = max_x // 2
    right_w = max_x - left_w

    left_top_h = bottom_h // 2
    left_bottom_h = bottom_h - left_top_h

    mem_w = left_w // 2
    disk_w = left_w - mem_w

    draw_box(stdscr, by, 0, left_top_h, mem_w, "2 mem")
    draw_box(stdscr, by, mem_w, left_top_h, disk_w, "3 disks")
    draw_box(stdscr, by + left_top_h, 0, left_bottom_h, left_w, "4 net")
    draw_box(stdscr, by, left_w, bottom_h, right_w, "5 proc")

    draw_progress(stdscr, by + 2, 2, mem_w - 4, "Used", data.mem_used_pct, pct_color(data.mem_used_pct))
    draw_progress(stdscr, by + 4, 2, mem_w - 4, "Cached", data.mem_cached_pct, curses.color_pair(2))
    draw_progress(stdscr, by + 6, 2, mem_w - 4, "Free", data.mem_free_pct, curses.color_pair(4))
    safe_addstr(stdscr, by + left_top_h - 2, 2, f"{data.mem_used_gb:.1f} GiB / {data.mem_total_gb:.1f} GiB")

    draw_progress(stdscr, by + 2, mem_w + 2, disk_w - 4, "Root", data.disk_used_pct, pct_color(data.disk_used_pct))
    draw_progress(stdscr, by + 4, mem_w + 2, disk_w - 4, "Swap", data.swap_used_pct, pct_color(data.swap_used_pct))

    net_y = by + left_top_h + 2
    net_h = max(6, left_bottom_h - 3)
    net_w = left_w - 4
    draw_sparkline(stdscr, net_y, 2, net_h // 2, net_w, data.net_down, f"DOWN {data.net_down_human}", curses.color_pair(7))
    draw_sparkline(stdscr, net_y + net_h // 2, 2, net_h - (net_h // 2), net_w, data.net_up, f"UP   {data.net_up_human}", curses.color_pair(5))

    visible = max(1, bottom_h - 4)
    scroll_offset = manual_scroll
    if len(data.proc_rows) > visible:
        if auto_scroll:
            scroll_offset = (frame // 2) % len(data.proc_rows)
    draw_processes(stdscr, by, left_w, bottom_h, right_w, data.proc_rows, scroll_offset)

    footer = "GPU mem/core util is best-effort on macOS; run with sudo for full powermetrics telemetry."
    safe_addstr(stdscr, max_y - 1, 1, footer[: max_x - 2], curses.color_pair(6))
    stdscr.refresh()
