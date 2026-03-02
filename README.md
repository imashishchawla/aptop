# aptop

Apple Silicon terminal monitor inspired by `btop`, `htop`, and `nvtop`.

## Phase 3 status

Phase 3 is implemented with a modular codebase and real power telemetry integration.

Implemented:
- 4-region layout (same target geometry):
  - top half: CPU + GPU graph area
  - bottom-left top: memory + disks
  - bottom-left bottom: network
  - bottom-right half: process pane
- Real collectors (macOS):
  - CPU: `top -l 1 -n 0`
  - Memory: `vm_stat` + `sysctl hw.memsize`
  - Disk + swap: filesystem usage + `sysctl vm.swapusage`
  - Network throughput: `route` + `netstat`
  - Processes: `ps -Ao pid,user,rss,pcpu,comm -r`
- Power + battery telemetry:
  - `pmset -g batt` (AC/battery source + percent/state)
  - `ioreg -r -n AppleSmartBattery -a` (adapter W/V/A when available)
  - `powermetrics` (GPU utilization + CPU/GPU/ANE power)
- Graceful fallback:
  - if `powermetrics` is unavailable/not sudo, GPU graph uses fallback estimator and UI clearly shows status.
- Process pane behavior:
  - default sort is memory high to low
  - smooth auto-scroll when rows exceed visible space
  - manual scrolling: `j`/`k` (auto-scroll pauses)
  - toggle auto-scroll: `a`
- Top detail behavior:
  - mirrored CPU graph style
  - CPU/GPU per-core bars
  - GPU memory utilization shown when available, otherwise `--`

## Code layout

- Entry command:
  - `aptop`
- Application package:
  - `aptop_app/main.py`
  - `aptop_app/models.py`
  - `aptop_app/utils.py`
  - `aptop_app/collectors/system.py`
  - `aptop_app/collectors/power.py`
  - `aptop_app/ui/render.py`

## Run

```bash
cd /Users/ashishchawla/Documents/My-DIY-Projects/thepiProject/aptop
./aptop
```

Optional:

```bash
./aptop --interval-ms 700
sudo ./aptop --interval-ms 700
```

Use `sudo` to unlock full `powermetrics` telemetry.

## Keys

- `q`: quit
- `r`: reset samplers
- `j` / `k`: process scroll
- `a`: toggle process auto-scroll

## Terminal size

Use at least `110x28`.
