# AGENTS.md — xAI Colossus 2

## What This Is

Sovereign infrastructure control system for xAI Colossus 2 — a 1.5GW, 200k-GPU AI supercomputer. Python, pure dataclasses, no frameworks. Tick-driven orchestrator with 8 pluggable subsystems.

## Essential Commands

```bash
# Run all tests (38 total: 24 e2e + 14 CLI)
python3 tests/test_end_to_end.py
python3 tests/test_cli.py

# CLI commands
python3 -m cli.colossus_cli status       # Full JSON status
python3 -m cli.colossus_cli health       # Quick health check
python3 -m cli.colossus_cli tick --count 5  # Run 5 tick cycles
python3 -m cli.colossus_cli thermal      # Thermal subsystem summary
python3 -m cli.colossus_cli zones --zone A  # Single zone telemetry
python3 -m cli.colossus_cli metrics      # Prometheus-compatible output
python3 -m cli.colossus_cli run --ticks 10  # Continuous tick loop

# Run orchestrator directly
python3 -c "from core.colossus_orchestrator import ColossusOrchestrator; import asyncio; asyncio.run(ColossusOrchestrator().run(duration_ticks=5))"
```

## Architecture

```
colossus_orchestrator.py  ← Central brain, tick-driven (500ms)
    │
    ├── thermal/          PINN digital twin + immersion + cascade + predictive
    ├── energy/           1.5GW grid balancer + Megapack FSM + PUE + forecast
    ├── security/         Hydra immune + ghost-ember + incident + SBOM
    ├── nanosphere/       Conductivity + degradation + optimizer + stability
    ├── servers/          12500 racks + 200k GPU health + 100k IB links
    ├── waterplant/       5-stage treatment + cooling tower + compliance
    ├── microcode/        Firmware matrix + driver compat + hot patcher
    ├── community/        Emissions + impact + licensing
    ├── api/              REST gateway (16+ endpoints) + MCP bridge (10 tools)
    ├── cli/              argparse CLI (12 commands)
    ├── memory/           Aspen Grove 4-tier persistence (JSONL)
    ├── physics/          Shared constants (PARTICLE_DATABASE, Maxwell, H-C)
    └── config/           colossus_manifest.json (single source of truth)
```

## Critical Patterns

### Subsystem Interface Contract
Every subsystem MUST expose exactly two methods:

```python
# Async tick — returns anomalies and actions
async def tick(self, zones: Dict, tick_num: int) -> Dict[str, Any]:
    return {"anomalies": [...], "actions": [...]}

# Sync summary — returns current state
def summary(self) -> Dict[str, Any]:
    return {...}
```

Some subsystems take `zones` dict, others take just `tick_num`. Check existing implementations before adding new ones.

### Orchestrator Wiring (5 Steps)
When adding a new subsystem, touch these files:
1. `core/colossus_orchestrator.py` — add `self._new_sub = None` in `__init__`, import+init in `_init_subsystems`, call in `tick_cycle`, add to `TickResult` and `system_status`
2. `api/gateway.py` — add `_handle_new_sub` method and register in `handlers` dict
3. `tests/test_end_to_end.py` — add subsystem test
4. `tests/test_cli.py` — add CLI test

### Configuration
All config lives in `config/colossus_manifest.json`. The orchestrator validates it at startup via `_validate_manifest()`. Missing sections get defaults with warnings. Never hardcode config values — always read from manifest.

### Physics Constants
`physics/constants.py` is the single source of truth for `PARTICLE_DATABASE`, `BASE_FLUID_THERMAL_CONDUCTIVITY`, `maxwell_conductivity()`, and `hamilton_crosser_conductivity()`. Other files import from here — never duplicate these constants.

## Gotchas

1. **Some ticks are sync, some are async** — `servers.tick()` is `async`, `waterplant.tick()` is sync, `microcode.tick()` is sync, `community.tick()` is sync. The orchestrator wraps sync ticks in try/except. Check the method signature before calling.

2. **Waterplant returns `TreatmentTickResult`** — not a dict. The orchestrator converts it: `wp_result.alerts` becomes `anomalies`.

3. **PINN has weight reset logic** — if residuals stay >0.5 for 10 ticks, the perceptron resets to fresh Xavier init. This is intentional to prevent divergence.

4. **Circuit breaker is per-zone** — 3 consecutive anomalies → isolate. 10 recovery ticks → HALF_OPEN → CLOSED. The orchestrator's `CircuitBreaker` is separate from `thermal/cascade_shield.py` (which is also wired).

5. **Fusion modes gate subsystem ticks** — `_active_pistons` determines which subsystems run each tick. COLOSSUS_FULL activates all pistons. EMERGENCY_RESPONSE skips GHOST and CORE-THINK.

6. **Memory bridge writes JSONL** — `memory/data/` contains `tick_archive.jsonl`, `decisions.jsonl`, `anomalies.jsonl`. These are gitignored. The bridge auto-rotates at 10MB.

7. **CLI creates a fresh orchestrator per command** — no persistent state between CLI invocations. Use `run` command for continuous operation.

8. **No real I/O** — all subsystems simulate their own data. No actual sensor ingestion, no real grid metering. This is a closed simulation loop.

## Naming Conventions

- Subsystem dirs: lowercase (`thermal/`, `energy/`, `security/`)
- Classes: PascalCase (`ColossusOrchestrator`, `SovereignGridBalancer`, `HydraImmuneSystem`)
- Logger prefix: `COLOSSUS-SUBSYSTEM` (e.g., `COLOSSUS-THERMAL`, `COLOSSUS-ENERGY`)
- Config keys: snake_case (`critical_temp_c`, `grid_capacity_mva`)
- Files: snake_case (`pinn_digital_twin.py`, `grid_balancer.py`)

## Testing

Tests use plain `assert` + `print("PASS: ...")` pattern, not pytest fixtures. Run with `python3 tests/test_end_to_end.py` directly. Each test is self-contained. Subsystem tests use try/except with SKIP on import failure.

CLI tests use `subprocess.run()` to invoke `python3 -m cli.colossus_cli <command>` and verify stdout output.

## What NOT To Do

- Don't duplicate `PARTICLE_DATABASE` — import from `physics/constants.py`
- Don't hardcode config values — read from `config/colossus_manifest.json`
- Don't add `pytest` fixtures — keep the plain assert pattern
- Don't make ticks sync if they need `await` — check existing patterns
- Don't access `_buffer` directly on TelemetryBus — use `recent_events()` and `buffer_size()`
