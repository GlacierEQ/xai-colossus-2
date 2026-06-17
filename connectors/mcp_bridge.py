#!/usr/bin/env python3
"""
Colossus 2 MCP Bridge
======================
Bridges Colossus 2 into the Model Context Protocol ecosystem.
Enables any MCP-compatible AI agent to query and control Colossus 2.

Registered tools:
  - colossus_status     — Full system status
  - colossus_health     — Quick health check
  - colossus_tick       — Trigger manual tick
  - colossus_zones      — Per-zone telemetry
  - colossus_thermal    — Thermal subsystem details
  - colossus_energy     — Energy subsystem details
  - colossus_security   — Security subsystem details
  - colossus_nanosphere — Nanosphere subsystem details
  - colossus_events     — Recent telemetry events
  - colossus_memory     — Memory bridge stats

Pro-Code Law 11: API & Interface Design — minimal, stable, well-documented.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("COLOSSUS-MCP")


TOOL_DEFINITIONS = [
    {
        "name": "colossus_status",
        "description": "Get full Colossus 2 system status including all subsystems, zones, and health",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "colossus_health",
        "description": "Quick health check — returns NOMINAL/DEGRADED/EMERGENCY/CRITICAL",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "colossus_tick",
        "description": "Trigger a manual orchestration tick cycle",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "colossus_zones",
        "description": "Get per-zone telemetry (temp, power, cooling, alerts)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Optional zone filter (A, B, or C)"},
            },
        },
    },
    {
        "name": "colossus_thermal",
        "description": "Get thermal subsystem status (immersion tanks, cascade shield, predictive dispatch)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "colossus_energy",
        "description": "Get energy subsystem status (grid balance, Megapack SOC, PUE)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "colossus_security",
        "description": "Get security subsystem status (threat level, strikes, anomaly rate)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "colossus_nanosphere",
        "description": "Get nanosphere status (fluid conductivity, degradation, replacements)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "colossus_events",
        "description": "Get recent telemetry events from the event bus",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Filter by event type (anomaly, action, etc)"},
                "limit": {"type": "integer", "description": "Max events to return (default 20)"},
            },
        },
    },
    {
        "name": "colossus_memory",
        "description": "Get memory bridge stats (hot/warm entries, anomalies, decisions)",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class MCPBridge:
    """MCP-compatible bridge for Colossus 2."""

    def __init__(self, api):
        self._api = api
        self._tool_count = 0

    def list_tools(self) -> List[Dict]:
        return TOOL_DEFINITIONS

    def call_tool(self, name: str, arguments: Optional[Dict] = None) -> Dict[str, Any]:
        self._tool_count += 1
        arguments = arguments or {}

        tool_map = {
            "colossus_status": lambda: self._api.handle("status"),
            "colossus_health": lambda: self._api.handle("health"),
            "colossus_zones": lambda: self._api.handle("zones", arguments),
            "colossus_thermal": lambda: self._api.handle("thermal"),
            "colossus_energy": lambda: self._api.handle("energy"),
            "colossus_security": lambda: self._api.handle("security"),
            "colossus_nanosphere": lambda: self._api.handle("nanosphere"),
            "colossus_events": lambda: self._api.handle("events", arguments),
            "colossus_memory": lambda: self._api._orch._memory.memory_stats() if self._api._orch._memory is not None else {"error": "Memory bridge not wired"},
        }

        if name == "colossus_tick":
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                if loop.is_running():
                    return {"error": "Cannot call tick from async context — use handle_async"}
                result = loop.run_until_complete(self._api.handle_async("tick"))
                return result
            finally:
                loop.close()

        handler = tool_map.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}", "available": list(tool_map.keys())}

        try:
            return handler()
        except Exception as e:
            return {"error": str(e), "tool": name}

    def stats(self) -> Dict:
        return {
            "tools_registered": len(TOOL_DEFINITIONS),
            "total_calls": self._tool_count,
            "tool_names": [t["name"] for t in TOOL_DEFINITIONS],
        }
