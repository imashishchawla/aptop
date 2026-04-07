# Apple Silicon Terminal Monitor Blueprint

This document defines a feature-first plan for `aptop`, inspired by `btop`, `htop`, and `nvtop`, with explicit trade-offs for Apple Silicon and low-overhead realtime rendering.

## Goals

1. **Complete observability** for CPU, GPU, memory, process, thermal/power, and I/O.
2. **No hidden state**: every derived metric should expose its source and confidence.
3. **Low self-overhead**: monitor should stay lightweight enough to trust under load.
4. **Apple Silicon native behavior**: distinguish P-cores/E-cores, unified memory, ANE, and power domains.

## Feature inventory from btop, htop, nvtop

### btop strengths to borrow

- Rich multi-panel layout (CPU/memory/net/disks/processes).
- Usability controls: sorting, filtering, kill/signals, tree mode, per-panel toggles.
- High information density with smooth UI updates.
- Human readable bandwidth, temperatures, and historical charts.

### htop strengths to borrow

- Process interaction workflow is best-in-class:
  - fast search/filter
  - per-column sorting
  - process tree and thread visibility
  - signal/send priority actions
- Minimal runtime overhead and very responsive keyboard loop.
- Operator-first shortcuts and predictable terminal behavior.

### nvtop strengths to borrow

- Dedicated accelerator telemetry focus:
  - per-device utilization
  - memory usage and engine stats
  - process-level GPU memory/usage
  - per-accelerator graphs with clear labels
- Tight refresh loop optimized for monitoring GPU-heavy jobs.

## Apple Silicon-specific requirements

### Must have

- CPU split by core class (Performance vs Efficiency) and total package usage.
- GPU utilization with source annotation:
  - `powermetrics` direct mode
  - fallback estimator mode (clearly tagged)
- Unified memory accounting:
  - wired/compressed/active/inactive/free
  - pressure state and swap in/out activity
- Power rails and battery/adapter telemetry:
  - CPU/GPU/ANE watts
  - battery %, charge/discharge state
  - adapter voltage/current/watts when available
- Process table with memory + CPU + command + owner + PID + optional thread count.

### Should have

- Thermal headroom indicators (if available from source commands).
- Network per-interface breakdown, not only default interface.
- Disk per-volume + read/write throughput trends.
- Process->GPU association where source data exists.

### Could have

- JSON export / machine-readable snapshot mode.
- Remote mode (`ssh`) with degraded collectors.
- Theme presets and compact layout profiles.

## Add / keep / remove decision framework

## Add now (high impact)

1. **Metric provenance in UI**
   - Show source tags (`powermetrics`, `vm_stat`, `ps`, etc.).
   - Show stale/estimated markers when collectors fail.
2. **Process interaction parity with htop-lite**
   - Sort by CPU/memory/PID/name
   - Filter/search
   - Optional tree mode
3. **Unified memory detail panel**
   - Replace generic used/cached/free-only summary with Apple-native buckets.
4. **Per-interface network table**
   - Keep total graph + expandable interface rows.

## Keep as core baseline

- Existing 5-pane layout and keyboard-driven TUI loop.
- Realtime history graphs for CPU/GPU/network.
- Power and battery integration with graceful fallback.
- Process auto-scroll plus manual navigation.

## Remove or avoid (to reduce complexity and monitor overhead)

- Heavy animation effects that allocate per-frame large buffers.
- Unbounded history or ever-growing caches.
- Frequent shell command fan-out per frame when data can be sampled at staggered rates.
- Redundant collectors for the same metric without explicit purpose.

## Efficiency plan (reduce aptop memory + system load)

1. **Staggered collector schedule**
   - fast loop (every frame): lightweight counters, cached parsed values
   - medium loop (every 1-2s): process list, interface details
   - slow loop (every 2-5s): expensive power/thermal probes
2. **Bounded data structures only**
   - fixed-size ring buffers for all time-series
   - avoid per-frame full-copy transforms when rendering
3. **Collector process reuse where possible**
   - prefer persistent subprocess streams over repeated spawn/parse.
4. **Adaptive refresh**
   - auto-degrade refresh interval under high monitor self-CPU.
5. **Allocation discipline**
   - precompute static labels/format templates
   - minimize temporary string/object churn in draw loop.

## Proposed v1 feature set for `aptop`

### Panels

1. **CPU/GPU timeline + core-class bars**
2. **Unified memory + swap pressure**
3. **Disk + per-volume throughput**
4. **Network total + per-interface breakdown**
5. **Process explorer (sort/filter/tree/actions)**
6. **Power/Thermal block (CPU/GPU/ANE + battery/adapter)**

### Interaction model

- `Tab` cycle focused panel
- `/` filter processes
- `s` cycle sort key
- `t` toggle tree
- `k` signal menu
- `d` toggle details/provenance layer
- `r` reset histories
- `q` quit

### Provenance policy

Every non-trivial metric displays one of:

- `direct`: source read succeeded this cycle
- `cached`: last successful read reused
- `estimated`: derived fallback algorithm
- `na`: unsupported on current privileges/system

## Milestone plan

1. **M1: feature parity baseline**
   - process sort/filter
   - unified memory buckets
   - source/provenance labels
2. **M2: efficiency pass**
   - staggered collection loops
   - reduced allocations in rendering path
   - self-overhead telemetry row
3. **M3: advanced observability**
   - interface drilldown, thermal hints, optional JSON snapshot.

## Acceptance criteria

- At 700ms default refresh, monitor self-CPU remains low and stable during idle.
- No panel silently shows fallback values without marker.
- Process and GPU/power panels remain readable in minimum supported terminal size.
- No unbounded memory growth over long-running sessions.
