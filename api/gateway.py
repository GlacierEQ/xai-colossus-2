#!/usr/bin/env python3
"""
Colossus 2 API Gateway
=======================
Unified REST-like interface to the entire Colossus 2 sovereign infrastructure.

Exposes:
  - /status        — Full system status JSON
  - /tick          — Trigger a manual tick cycle
  - /thermal       — Thermal subsystem status
  - /energy        — Energy subsystem status
  - /security      — Security subsystem status
  - /nanosphere    — Nanosphere subsystem status
  - /zones         — Per-zone telemetry
  - /events        — Recent telemetry events
  - /health        — Quick health check (NOMINAL/DEGRADED/EMERGENCY/CRITICAL)
  - /ready         — Readiness probe (all subsystems online)
  - /live          — Liveness probe (at least 1 tick completed)
  - /metrics       — Prometheus-compatible metrics export

Designed for:
  - MCP server integration (colossus-gateway)
  - APEX orchestrator tick loop consumption
  - Human CLI inspection via curl/jq
  - Subagent health probes

Pro-Code Compliance: Law 1 (naming), Law 2 (failure modes), Law 9 (observability).
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("COLOSSUS-API")


class TokenBucket:
    """Simple token bucket rate limiter — max 100 req/s, refills at 100/sec."""

    def __init__(self, capacity: int = 100, refill_rate: float = 100.0):
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_rate = refill_rate
        self._last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    @property
    def tokens(self) -> float:
        return self._tokens


class ColossusAPI:
    """Synchronous facade over the async ColossusOrchestrator."""

    def __init__(self, orchestrator, api_key: Optional[str] = None):
        self._orch = orchestrator
        self._request_count = 0
        self._last_request_time = 0.0
        self._rate_limiter = TokenBucket(capacity=100, refill_rate=100.0)
        self._api_key = api_key

    def handle(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        if self._api_key:
            provided = (headers or {}).get("X-API-Key", "")
            if provided != self._api_key:
                return {
                    "error": "Unauthorized: invalid or missing X-API-Key header",
                    "status_code": 401,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        if not self._rate_limiter.consume():
            return {
                "error": "Rate limit exceeded (max 100 req/s)",
                "status_code": 429,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        self._request_count += 1
        self._last_request_time = time.time()
        params = params or {}

        handlers = {
            "status": self._handle_status,
            "health": self._handle_health,
            "tick": self._handle_tick,
            "thermal": self._handle_thermal,
            "energy": self._handle_energy,
            "security": self._handle_security,
            "nanosphere": self._handle_nanosphere,
            "zones": self._handle_zones,
            "events": self._handle_events,
            "ready": self._handle_ready,
            "live": self._handle_live,
            "metrics": self._handle_metrics,
        }

        handler = handlers.get(endpoint)
        if not handler:
            return {
                "error": f"Unknown endpoint: {endpoint}",
                "available": list(handlers.keys()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            return handler(params)
        except Exception as e:
            logger.error("API error on /%s: %s", endpoint, e)
            return {
                "error": str(e),
                "endpoint": endpoint,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def handle_async(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        if endpoint == "tick":
            result = await self._orch.tick_cycle()
            return self._format_tick_result(result)
        return self.handle(endpoint, params, headers=headers)

    def _handle_status(self, params: Dict) -> Dict:
        return self._orch.system_status()

    def _handle_health(self, params: Dict) -> Dict:
        return {
            "health": self._orch.health.value,
            "tick": self._orch.tick,
            "uptime_s": round(time.time() - self._orch.start_time, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _handle_tick(self, params: Dict) -> Dict:
        return {"error": "Use /tick via async interface", "hint": "await api.handle_async('tick')"}

    def _handle_thermal(self, params: Dict) -> Dict:
        if not self._orch._thermal:
            return {"status": "OFFLINE", "reason": "Thermal engine not loaded"}
        return {
            "status": "ONLINE",
            **self._orch._thermal.summary(),
        }

    def _handle_energy(self, params: Dict) -> Dict:
        if not self._orch._energy:
            return {"status": "OFFLINE", "reason": "Grid balancer not loaded"}
        return {
            "status": "ONLINE",
            **self._orch._energy.summary(),
        }

    def _handle_security(self, params: Dict) -> Dict:
        if not self._orch._security:
            return {"status": "OFFLINE", "reason": "Security system not loaded"}
        return {
            "status": "ONLINE",
            **self._orch._security.summary(),
        }

    def _handle_nanosphere(self, params: Dict) -> Dict:
        if not self._orch._nanosphere:
            return {"status": "OFFLINE", "reason": "Nanosphere engine not loaded"}
        return {
            "status": "ONLINE",
            **self._orch._nanosphere.summary(),
        }

    def _handle_zones(self, params: Dict) -> Dict:
        zone_filter = params.get("zone")
        zones = self._orch.zones
        if zone_filter and zone_filter in zones:
            zones = {zone_filter: zones[zone_filter]}
        return {
            zid: {
                "temp_celsius": z.temp_celsius,
                "gpu_utilization": z.gpu_utilization,
                "power_draw_kw": z.power_draw_kw,
                "cooling_flow_lpm": z.cooling_flow_lpm,
                "conductivity_factor": z.conductivity_factor,
                "thermal_budget_kw": z.thermal_budget_kw,
                "alert_level": z.alert_level,
                "isolated": z.isolated,
            }
            for zid, z in zones.items()
        }

    def _handle_events(self, params: Dict) -> Dict:
        event_type = params.get("type")
        limit = int(params.get("limit", 20))
        events = self._orch.telemetry.recent_events(event_type=event_type, limit=limit)
        return {"events": events, "total_buffered": self._orch.telemetry.buffer_size()}

    def _handle_ready(self, params: Dict) -> Dict:
        subsystems = {
            "thermal": self._orch._thermal is not None,
            "energy": self._orch._energy is not None,
            "security": self._orch._security is not None,
            "nanosphere": self._orch._nanosphere is not None,
            "memory": self._orch._memory is not None,
            "digital_twin": self._orch._digital_twin is not None,
            "cascade_shield": self._orch._cascade_shield is not None,
            "predictive_dispatch": self._orch._predictive is not None,
        }
        ready = all(subsystems.values())
        return {
            "ready": ready,
            "subsystems": subsystems,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _handle_live(self, params: Dict) -> Dict:
        return {
            "live": self._orch.tick >= 1,
            "tick": self._orch.tick,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _handle_metrics(self, params: Dict) -> Dict:
        m = self._orch.metrics()
        return {"text": m["text"], "tick": m["tick"], "uptime_s": m["uptime_s"]}

    def _format_tick_result(self, result) -> Dict:
        return {
            "tick": result.tick_id,
            "timestamp": result.timestamp,
            "duration_ms": result.duration_ms,
            "health": result.health.value,
            "fusion_mode": result.fusion_mode,
            "anomalies": result.anomalies,
            "actions_taken": result.actions_taken,
            "thermal": result.thermal_summary,
            "energy": result.energy_summary,
            "security": result.security_summary,
            "nanosphere": result.nanosphere_summary,
        }

    def api_stats(self) -> Dict:
        return {
            "total_requests": self._request_count,
            "last_request": self._last_request_time,
            "rate_limit_tokens": self._rate_limiter.tokens,
            "endpoints": ["status", "health", "tick", "thermal", "energy", "security", "nanosphere", "zones", "events", "ready", "live", "metrics"],
        }
