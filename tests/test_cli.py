#!/usr/bin/env python3
"""CLI integration tests for Colossus 2."""

import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CLI = [sys.executable, "-m", "cli.colossus_cli"]


def run_cli(*args):
    result = subprocess.run(
        CLI + list(args),
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return result.stdout, result.stderr, result.returncode


def test_health():
    stdout, stderr, code = run_cli("health")
    assert code == 0
    assert "Health:" in stdout
    assert "nominal" in stdout
    print("PASS: cli_health")


def test_status():
    stdout, stderr, code = run_cli("status")
    assert code == 0
    assert "version" in stdout
    assert "2.0.0-COLOSSUS" in stdout
    print("PASS: cli_status")


def test_zones():
    stdout, stderr, code = run_cli("zones")
    assert code == 0
    assert "A:" in stdout
    assert "B:" in stdout
    assert "C:" in stdout
    print("PASS: cli_zones")


def test_zone_filter():
    stdout, stderr, code = run_cli("zones", "--zone", "A")
    assert code == 0
    assert "temp_celsius" in stdout
    assert "A" in stdout
    print("PASS: cli_zone_filter")


def test_thermal():
    stdout, stderr, code = run_cli("thermal")
    assert code == 0
    assert "tanks_online" in stdout
    print("PASS: cli_thermal")


def test_energy():
    stdout, stderr, code = run_cli("energy")
    assert code == 0
    assert "baseload_mw" in stdout
    print("PASS: cli_energy")


def test_security():
    stdout, stderr, code = run_cli("security")
    assert code == 0
    assert "threat_level" in stdout
    print("PASS: cli_security")


def test_nanosphere():
    stdout, stderr, code = run_cli("nanosphere")
    assert code == 0
    assert "circuits_online" in stdout
    print("PASS: cli_nanosphere")


def test_servers():
    stdout, stderr, code = run_cli("servers")
    assert code == 0
    assert "total_racks" in stdout
    print("PASS: cli_servers")


def test_waterplant():
    stdout, stderr, code = run_cli("waterplant")
    assert code == 0
    assert "flow_gpm" in stdout
    print("PASS: cli_waterplant")


def test_microcode():
    stdout, stderr, code = run_cli("microcode")
    assert code == 0
    assert "total_components" in stdout
    print("PASS: cli_microcode")


def test_community():
    stdout, stderr, code = run_cli("community")
    assert code == 0
    assert "total_readings" in stdout
    print("PASS: cli_community")


def test_metrics():
    stdout, stderr, code = run_cli("metrics")
    assert code == 0
    assert "colossus_ticks_total" in stdout
    assert "colossus_health_gauge" in stdout
    print("PASS: cli_metrics")


def test_tick():
    stdout, stderr, code = run_cli("tick", "--count", "2")
    assert code == 0
    assert "Tick 1:" in stdout
    assert "Tick 2:" in stdout
    print("PASS: cli_tick")


if __name__ == "__main__":
    tests = [
        test_health, test_status, test_zones, test_zone_filter,
        test_thermal, test_energy, test_security, test_nanosphere,
        test_servers, test_waterplant, test_microcode, test_community,
        test_metrics, test_tick,
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
    print(f"CLI RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    sys.exit(1 if failed else 0)
