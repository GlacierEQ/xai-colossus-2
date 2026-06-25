#!/usr/bin/env python3
"""
Colossus 2 CLI — Command-line interface to the autonomous infrastructure.

Usage:
    python3 -m cli.colossus_cli status
    python3 -m cli.colossus_cli health
    python3 -m cli.colossus_cli tick [--count N]
    python3 -m cli.colossus_cli thermal
    python3 -m cli.colossus_cli energy
    python3 -m cli.colossus_cli security
    python3 -m cli.colossus_cli nanosphere
    python3 -m cli.colossus_cli servers
    python3 -m cli.colossus_cli waterplant
    python3 -m cli.colossus_cli microcode
    python3 -m cli.colossus_cli community
    python3 -m cli.colossus_cli zones [--zone A]
    python3 -m cli.colossus_cli metrics
    python3 -m cli.colossus_cli run [--ticks N]
"""

import argparse
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cmd_status(args):
    from core.colossus_orchestrator import ColossusOrchestrator
    orch = ColossusOrchestrator()
    status = orch.system_status()
    print(json.dumps(status, indent=2))


def cmd_health(args):
    from core.colossus_orchestrator import ColossusOrchestrator
    orch = ColossusOrchestrator()
    status = orch.system_status()
    health = status["health"]
    tick = status["tick"]
    subsystems = sum(1 for v in status["subsystems"].values() if v is True)
    print(f"Health: {health}")
    print(f"Tick: {tick}")
    print(f"Subsystems: {subsystems}/{len(status['subsystems'])}")


def cmd_tick(args):
    from core.colossus_orchestrator import ColossusOrchestrator
    orch = ColossusOrchestrator()
    count = args.count or 1

    async def run():
        for i in range(count):
            result = await orch.tick_cycle()
            print(f"Tick {result.tick_id}: health={result.health.value} "
                  f"duration={result.duration_ms:.1f}ms "
                  f"anomalies={len(result.anomalies)} "
                  f"actions={len(result.actions_taken)}")

    asyncio.run(run())


def cmd_subsystem(args):
    from core.colossus_orchestrator import ColossusOrchestrator
    orch = ColossusOrchestrator()
    subsystem = args.subsystem_name

    subsystem_map = {
        "thermal": orch._thermal,
        "energy": orch._energy,
        "security": orch._security,
        "nanosphere": orch._nanosphere,
        "servers": orch._servers,
        "waterplant": orch._waterplant,
        "microcode": orch._microcode,
        "community": orch._community,
    }

    obj = subsystem_map.get(subsystem)
    if obj:
        print(json.dumps(obj.summary(), indent=2))
    else:
        print(f"Subsystem '{subsystem}' not loaded")


def cmd_zones(args):
    from core.colossus_orchestrator import ColossusOrchestrator
    orch = ColossusOrchestrator()
    zones = orch.zones
    if args.zone:
        if args.zone in zones:
            zone = zones[args.zone]
            print(json.dumps({
                "zone_id": zone.zone_id,
                "temp_celsius": zone.temp_celsius,
                "power_draw_kw": zone.power_draw_kw,
                "cooling_flow_lpm": zone.cooling_flow_lpm,
                "conductivity_factor": zone.conductivity_factor,
                "isolated": zone.isolated,
                "alert_level": zone.alert_level,
            }, indent=2))
        else:
            print(f"Zone '{args.zone}' not found")
    else:
        for zid, zone in zones.items():
            print(f"{zid}: temp={zone.temp_celsius:.1f}C "
                  f"power={zone.power_draw_kw:.0f}kW "
                  f"isolated={zone.isolated}")


def cmd_metrics(args):
    from core.colossus_orchestrator import ColossusOrchestrator
    orch = ColossusOrchestrator()
    metrics = orch.metrics()
    print(metrics["text"])


def cmd_run(args):
    from core.colossus_orchestrator import ColossusOrchestrator
    orch = ColossusOrchestrator()
    ticks = args.ticks or 10

    async def run():
        await orch.run(duration_ticks=ticks)

    asyncio.run(run())


def main():
    parser = argparse.ArgumentParser(
        description="Colossus 2 CLI — Infrastructure Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("status", help="Full system status")
    subparsers.add_parser("health", help="Quick health check")

    tick_parser = subparsers.add_parser("tick", help="Run tick cycle(s)")
    tick_parser.add_argument("--count", type=int, default=1, help="Number of ticks")

    for name in ["thermal", "energy", "security", "nanosphere",
                  "servers", "waterplant", "microcode", "community"]:
        subparsers.add_parser(name, help=f"{name.capitalize()} subsystem status")

    zones_parser = subparsers.add_parser("zones", help="Zone telemetry")
    zones_parser.add_argument("--zone", type=str, help="Specific zone (A/B/C)")

    subparsers.add_parser("metrics", help="Prometheus-compatible metrics")

    run_parser = subparsers.add_parser("run", help="Run continuous tick loop")
    run_parser.add_argument("--ticks", type=int, default=10, help="Number of ticks")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "status": cmd_status,
        "health": cmd_health,
        "tick": cmd_tick,
        "thermal": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'thermal'})()),
        "energy": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'energy'})()),
        "security": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'security'})()),
        "nanosphere": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'nanosphere'})()),
        "servers": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'servers'})()),
        "waterplant": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'waterplant'})()),
        "microcode": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'microcode'})()),
        "community": lambda a: cmd_subsystem(type('NS', (), {'subsystem_name': 'community'})()),
        "zones": cmd_zones,
        "metrics": cmd_metrics,
        "run": cmd_run,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
