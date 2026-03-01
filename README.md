# aptop

Apple Silicon terminal monitor inspired by `btop`, `htop`, and `nvtop`.

## Phase 2 status

Phase 2 keeps the target layout and adds real macOS system collectors.

Implemented:
- 4-region layout:
  - top half: CPU + GPU graph area
  - bottom-left top: memory and disks split
  - bottom-left bottom: network graph
  - bottom-right half: process pane
- Real collectors (macOS):
  - CPU: `top -l 1`
  - Memory: `vm_stat` + `sysctl hw.memsize`
  - Disk + swap: `disk_usage(/)` + `sysctl vm.swapusage`
  - Network throughput: `route` + `netstat`
  - Process table: `ps -Ao pid,user,rss,pcpu,comm -r`
- Keybinds:
  - `q`: quit
  - `r`: reset sampler state

Current limitation:
- GPU graph is still a placeholder in Phase 2.
  - Phase 3 will replace it with `powermetrics`-backed GPU metrics.

## Run

```bash
cd /Users/ashishchawla/Documents/My-DIY-Projects/thepiProject/aptop
./aptop
```

Optional:

```bash
./aptop --interval-ms 500
```

## Terminal size

Use at least `110x28`.
