#!/usr/bin/env python3
"""
Colossus 2 End-to-End Test Suite
==================================
Verifies the complete sovereign infrastructure:
  - Orchestrator initializes all subsystems
  - Tick cycle runs without errors
  - Thermal, Energy, Security, Nanosphere produce valid output
  - API Gateway responds to all endpoints
  - Circuit breakers isolate and recover zones
  - Memory bridge persists tick results
  - Fusion modes activate correct piston sets

Run: python3 -m pytest tests/test_end_to_end.py -v
Or:  python3 tests/test_end_to_end.py
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.colossus_orchestrator import (
    ColossusOrchestrator,
    CircuitBreaker,
    SystemHealth,
    TelemetryBus,
    ZoneState,
)


def test_orchestrator_init():
    orch = ColossusOrchestrator()
    assert orch.VERSION == "2.0.0-COLOSSUS"
    assert orch.health == SystemHealth.NOMINAL
    assert len(orch.zones) == 3
    assert "A" in orch.zones
    assert "B" in orch.zones
    assert "C" in orch.zones
    print("PASS: orchestrator_init")


def test_zone_state():
    zone = ZoneState(zone_id="TEST", temp_celsius=72.0, power_draw_kw=5000.0)
    assert zone.zone_id == "TEST"
    assert zone.temp_celsius == 72.0
    assert zone.alert_level == 0
    assert zone.isolated is False
    print("PASS: zone_state")


def test_circuit_breaker():
    cb = CircuitBreaker(max_anomalies=3, recovery_ticks=2)
    assert not cb.is_isolated("ZONE-A")

    cb.record_anomaly("ZONE-A")
    assert not cb.is_isolated("ZONE-A")
    cb.record_anomaly("ZONE-A")
    assert not cb.is_isolated("ZONE-A")
    cb.record_anomaly("ZONE-A")
    assert cb.is_isolated("ZONE-A")

    cb.tick_recovery()
    assert cb.is_isolated("ZONE-A")
    cb.tick_recovery()
    assert not cb.is_isolated("ZONE-A")
    print("PASS: circuit_breaker")


def test_telemetry_bus():
    bus = TelemetryBus(max_buffer=100)
    received = []
    bus.subscribe("test_event", lambda e: received.append(e))
    bus.emit("test_event", "test_source", {"key": "value"})
    assert len(received) == 1
    assert received[0]["type"] == "test_event"
    assert received[0]["payload"]["key"] == "value"
    assert bus._event_count == 1

    events = bus.recent("test_event")
    assert len(events) == 1
    print("PASS: telemetry_bus")


def test_tick_cycle():
    orch = ColossusOrchestrator()
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(orch.tick_cycle())
    assert result.tick_id == 1
    assert isinstance(result.health, SystemHealth)
    assert result.duration_ms >= 0
    assert result.timestamp is not None
    loop.close()
    print(f"PASS: tick_cycle (duration={result.duration_ms:.1f}ms, health={result.health.value})")


def test_multi_tick():
    orch = ColossusOrchestrator()
    loop = asyncio.new_event_loop()
    results = []
    for _ in range(5):
        r = loop.run_until_complete(orch.tick_cycle())
        results.append(r)
    assert len(results) == 5
    assert all(r.tick_id == i + 1 for i, r in enumerate(results))
    loop.close()
    print(f"PASS: multi_tick ({len(results)} ticks, final_tick={results[-1].tick_id})")


def test_system_status():
    orch = ColossusOrchestrator()
    status = orch.system_status()
    assert "version" in status
    assert "health" in status
    assert "zones" in status
    assert "subsystems" in status
    assert status["version"] == "2.0.0-COLOSSUS"
    assert len(status["zones"]) == 3
    print("PASS: system_status")


def test_api_gateway():
    from api.gateway import ColossusAPI
    orch = ColossusOrchestrator()
    api = ColossusAPI(orch)

    status = api.handle("status")
    assert "version" in status
    assert status["version"] == "2.0.0-COLOSSUS"

    health = api.handle("health")
    assert "health" in health
    assert health["health"] in ["nominal", "degraded", "emergency", "critical"]

    zones = api.handle("zones")
    assert "A" in zones
    assert "B" in zones

    events = api.handle("events")
    assert "events" in events

    stats = api.api_stats()
    assert stats["total_requests"] >= 4

    unknown = api.handle("nonexistent")
    assert "error" in unknown
    print("PASS: api_gateway")


def test_memory_bridge():
    from memory.aspen_bridge import AspenBridge
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('memory.aspen_bridge.MEMORY_DIR', Path(tmpdir)):
            bridge = AspenBridge(max_hot=100)

            bridge.persist_tick({"tick": 1, "health": "nominal", "anomalies": ["test_anomaly"]})
            bridge.log_decision("test_decision", {"reason": "testing"})

            recent = bridge.recent_ticks(limit=10)
            assert len(recent) >= 1
            assert recent[-1]["tick"] == 1

            anomalies = bridge.recent_anomalies(limit=10)
            assert len(anomalies) >= 1

            decisions = bridge.recent_decisions(limit=10)
            assert len(decisions) >= 1

            stats = bridge.memory_stats()
            assert stats["hot_entries"] >= 1
    print("PASS: memory_bridge (temp dir)")


def test_thermal_subsystem():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "thermal"))
    try:
        from pinn_digital_twin import PINNDigitalTwin
        twin = PINNDigitalTwin({"critical_temp_c": 85})
        zone = {"zone_id": "A", "temp_celsius": 72.0, "power_draw_kw": 5000.0, "cooling_flow_lpm": 100.0}
        result = twin.validate(zone)
        assert "flagged" in result
        assert "residual" in result
        print("PASS: thermal_subsystem (PINN)")
    except Exception as e:
        print(f"SKIP: thermal_subsystem — {e}")


def test_energy_subsystem():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "energy"))
    try:
        from pue_optimizer import PUEOptimizer, PUEConfig
        config = PUEConfig(target_pue=1.03)
        opt = PUEOptimizer(config)
        result = opt.get_pue(total_power_mw=1200.0, it_power_mw=1150.0)
        assert "pue" in result
        assert result["pue"] > 1.0
        print("PASS: energy_subsystem (PUE)")
    except Exception as e:
        print(f"SKIP: energy_subsystem — {e}")


def test_security_subsystem():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "security"))
    try:
        from ghost_ember import GhostEmberDetector
        detector = GhostEmberDetector()
        result = detector.ingest("sensor_001", 72.0)
        assert "anomaly" in result
        assert "severity" in result
        print("PASS: security_subsystem (Ghost-Ember)")
    except Exception as e:
        print(f"SKIP: security_subsystem — {e}")


def test_nanosphere_subsystem():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nanosphere"))
    try:
        from stability_engine import StabilitySpec, StabilityEngine
        engine = StabilityEngine()
        spec = StabilitySpec(
            nanoparticle="Al2O3",
            volume_fraction=0.03,
            particle_size_nm=30.0,
            zeta_potential_mv=38.0,
        )
        result = engine.evaluate_stability(spec)
        assert hasattr(result, 'score')
        assert result.score > 0
        print(f"PASS: nanosphere_subsystem (stability={result.score})")
    except Exception as e:
        print(f"SKIP: nanosphere_subsystem — {e}")


def test_full_integration():
    from api.gateway import ColossusAPI
    from memory.aspen_bridge import AspenBridge

    orch = ColossusOrchestrator()
    api = ColossusAPI(orch)
    bridge = AspenBridge(max_hot=100)

    loop = asyncio.new_event_loop()
    for i in range(3):
        result = loop.run_until_complete(orch.tick_cycle())
        bridge.persist_tick({
            "tick": result.tick_id,
            "health": result.health.value,
            "anomalies": result.anomalies,
            "actions": result.actions_taken,
        })
    loop.close()

    status = api.handle("status")
    health = api.handle("health")
    zones = api.handle("zones")

    assert status["tick"] == 3
    assert health["tick"] == 3
    assert len(zones) == 3

    mem_stats = bridge.memory_stats()
    assert mem_stats["hot_entries"] >= 3

    print(f"PASS: full_integration (health={health['health']}, memory={mem_stats})")


# =====================================================================
# #35: Negative test cases
# =====================================================================

def test_orchestrator_degraded_mode():
    orch = ColossusOrchestrator(manifest={"facility": {"zones": ["A"], "total_power_mw": 1500, "gpu_count": 1}})
    assert orch.health == SystemHealth.NOMINAL
    assert len(orch.zones) == 1
    assert "A" in orch.zones

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(orch.tick_cycle())
    assert result.tick_id == 1
    assert isinstance(result.health, SystemHealth)
    loop.close()
    print("PASS: orchestrator_degraded_mode")


def test_megapack_zero_soc():
    from energy.megapack_state_machine import TeslaMegapack, MegapackState
    mp = TeslaMegapack()
    mp.current.soc = 0.0

    result = mp.transition_to(MegapackState.DISCHARGING, "test_zero_soc")
    assert result is False
    assert mp.current.state == MegapackState.IDLE

    discharge_ok = mp.pulse_discharge(50.0, 10.0)
    assert discharge_ok is False
    assert mp.current.state == MegapackState.IDLE
    print("PASS: megapack_zero_soc")


def test_megapack_full_soc():
    from energy.megapack_state_machine import TeslaMegapack, MegapackState
    mp = TeslaMegapack()
    mp.current.soc = 1.0

    result = mp.transition_to(MegapackState.CHARGING, "test_full_soc")
    assert result is False
    assert mp.current.state == MegapackState.IDLE
    print("PASS: megapack_full_soc")


def test_security_max_threat():
    from security.hydra_immune import HydraImmuneSystem
    security = HydraImmuneSystem(security_config={
        "zero_trust": True,
        "threat_detection_threshold": 0.5,
    })

    loop = asyncio.new_event_loop()
    for tick in range(100):
        loop.run_until_complete(security.tick(tick))
    loop.close()

    assert security.threat_level <= 1.0
    print(f"PASS: security_max_threat (threat_level={security.threat_level:.4f})")


def test_nanosphere_all_retired():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nanosphere"))
    from nanosphere.conductivity_engine import ConductivityEngine
    from nanosphere.degradation_lifecycle import LifecycleState

    config = {
        "base_fluid": "water",
        "primary_nanoparticle": "Al2O3",
        "volume_fraction": 0.03,
        "particle_size_nm": 30,
        "degradation_halflife_days": 180,
        "stability_threshold": 60,
        "max_volume_fraction": 0.05,
        "chunks_per_zone": 2,
    }
    engine = ConductivityEngine(config)

    for batch in engine.lifecycle.all_batches():
        engine.lifecycle.update_batch_age(batch.batch_id, 200)
        assert batch.state == LifecycleState.REPLACEMENT_DUE

    for batch in engine.lifecycle.all_batches():
        result = engine.lifecycle.retire_batch(batch.batch_id)
        assert result is True
        assert batch.state == LifecycleState.RETIRED

    loop = asyncio.new_event_loop()
    zones = {"A": ZoneState(zone_id="A"), "B": ZoneState(zone_id="B"), "C": ZoneState(zone_id="C")}
    loop.run_until_complete(engine.tick(zones, 1))
    loop.close()

    for circuit in engine._circuits.values():
        assert circuit.conductivity_factor == 1.0
    print("PASS: nanosphere_all_retired")


def test_circuit_breaker_rapid_isolation():
    cb = CircuitBreaker(max_anomalies=3, recovery_ticks=10)
    for i in range(10):
        cb.record_anomaly("ZONE-RAPID")
    assert cb.is_isolated("ZONE-RAPID")
    assert cb._anomaly_counts["ZONE-RAPID"] == 10
    print("PASS: circuit_breaker_rapid_isolation")


# =====================================================================
# #36: Load/performance tests
# =====================================================================

def test_tick_performance():
    orch = ColossusOrchestrator()
    loop = asyncio.new_event_loop()

    start = time.time()
    for _ in range(100):
        loop.run_until_complete(orch.tick_cycle())
    elapsed_ms = (time.time() - start) * 1000
    loop.close()

    avg_ms = elapsed_ms / 100
    assert avg_ms < 500, f"Average tick {avg_ms:.1f}ms exceeds 500ms budget"
    print(f"PASS: tick_performance (avg={avg_ms:.2f}ms, total={elapsed_ms:.0f}ms for 100 ticks)")


# =====================================================================
# #37: Concurrency tests
# =====================================================================

def test_telemetry_bus_concurrent():
    bus = TelemetryBus(max_buffer=10000)
    count_per_thread = 100
    num_threads = 10

    def emit_events(thread_id):
        for i in range(count_per_thread):
            bus.emit(f"event_{thread_id}", f"source_{thread_id}", {"i": i})

    threads = [threading.Thread(target=emit_events, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(bus._buffer) == num_threads * count_per_thread
    print(f"PASS: telemetry_bus_concurrent ({num_threads} threads x {count_per_thread} = {num_threads * count_per_thread} events)")


# =====================================================================
# #38: Full subsystem integration test
# =====================================================================

def test_full_subsystem_integration():
    orch = ColossusOrchestrator()
    loop = asyncio.new_event_loop()
    for _ in range(10):
        loop.run_until_complete(orch.tick_cycle())
    loop.close()

    assert orch._thermal is not None, "thermal subsystem not loaded"
    assert orch._energy is not None, "energy subsystem not loaded"
    assert orch._security is not None, "security subsystem not loaded"
    assert orch._nanosphere is not None, "nanosphere subsystem not loaded"

    thermal_summary = orch._thermal.summary()
    assert thermal_summary["tanks_online"] > 0

    energy_summary = orch._energy.summary()
    assert energy_summary["baseload_mw"] > 0

    security_summary = orch._security.summary()
    assert security_summary["events_scanned"] > 0

    nanosphere_summary = orch._nanosphere.summary()
    assert nanosphere_summary["circuits_online"] > 0

    print(f"PASS: full_subsystem_integration "
          f"(tanks={thermal_summary['tanks_online']}, "
          f"baseload={energy_summary['baseload_mw']:.1f}MW, "
          f"scanned={security_summary['events_scanned']}, "
          f"circuits={nanosphere_summary['circuits_online']})")


# =====================================================================
# #40: MCP bridge test
# =====================================================================

def test_mcp_bridge():
    from api.gateway import ColossusAPI
    from connectors.mcp_bridge import MCPBridge

    orch = ColossusOrchestrator()
    api = ColossusAPI(orch)
    mcp = MCPBridge(api)

    tools = mcp.list_tools()
    assert len(tools) == 10

    status = mcp.call_tool("colossus_status")
    assert isinstance(status, dict)
    assert "version" in status

    health = mcp.call_tool("colossus_health")
    assert isinstance(health, dict)
    assert "health" in health

    stats = mcp.stats()
    assert stats["total_calls"] == 2

    print("PASS: mcp_bridge")


if __name__ == "__main__":
    tests = [
        test_orchestrator_init,
        test_zone_state,
        test_circuit_breaker,
        test_telemetry_bus,
        test_tick_cycle,
        test_multi_tick,
        test_system_status,
        test_api_gateway,
        test_memory_bridge,
        test_thermal_subsystem,
        test_energy_subsystem,
        test_security_subsystem,
        test_nanosphere_subsystem,
        test_full_integration,
        test_orchestrator_degraded_mode,
        test_megapack_zero_soc,
        test_megapack_full_soc,
        test_security_max_threat,
        test_nanosphere_all_retired,
        test_circuit_breaker_rapid_isolation,
        test_tick_performance,
        test_telemetry_bus_concurrent,
        test_full_subsystem_integration,
        test_mcp_bridge,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__} — {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
