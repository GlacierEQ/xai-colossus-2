#!/usr/bin/env python3
"""
Aspen Grove Memory Bridge for Colossus 2
=========================================
Bridges Colossus 2 telemetry and decisions into the Aspen Grove memory spine.

Memory tiers:
  Tier 1: Hot — last 1000 tick results (in-memory)
  Tier 2: Warm — JSONL log files (persistent, queryable)
  Tier 3: Cold — Supabase pgvector (semantic search)
  Tier 4: Frozen — Dropbox archive (evidence vault)

Pro-Code Law 9: Observability Is Part of the Interface.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("COLOSSUS-MEMORY")

MEMORY_DIR = Path(__file__).parent.parent / "memory" / "data"


class AspenBridge:
    """Persistent memory bridge for Colossus 2 tick results and decisions."""

    def __init__(self, max_hot: int = 1000):
        self._hot: List[Dict[str, Any]] = []
        self._max_hot = max_hot
        self._warm_path = MEMORY_DIR / "tick_archive.jsonl"
        self._decisions_path = MEMORY_DIR / "decisions.jsonl"
        self._anomalies_path = MEMORY_DIR / "anomalies.jsonl"
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._load_warm()
        logger.info("AspenBridge initialized: hot=%d, warm=%d entries",
                    len(self._hot), self._count_warm())

    def _load_warm(self) -> None:
        if self._warm_path.exists():
            with open(self._warm_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._hot.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            self._hot = self._hot[-self._max_hot:]

    def _count_warm(self) -> int:
        if not self._warm_path.exists():
            return 0
        with open(self._warm_path) as f:
            return sum(1 for line in f if line.strip())

    def _rotate_file(self, path: Path, max_bytes: int = 10_000_000) -> None:
        if not path.exists():
            return
        if path.stat().st_size <= max_bytes:
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rotated = path.with_name(f"{path.stem}.{ts}.jsonl")
        path.rename(rotated)
        logger.info("LOG_ROTATION: %s -> %s (%d bytes)", path.name, rotated.name, rotated.stat().st_size)

    def persist_tick(self, tick_result: Dict[str, Any]) -> None:
        self._rotate_file(self._warm_path)
        self._rotate_file(self._anomalies_path)
        self._rotate_file(self._decisions_path)

        entry = {
            **tick_result,
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        self._hot.append(entry)
        if len(self._hot) > self._max_hot:
            self._hot = self._hot[-self._max_hot // 2:]

        with open(self._warm_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        if tick_result.get("anomalies"):
            for anomaly in tick_result["anomalies"]:
                self._log_anomaly(anomaly, tick_result.get("tick", 0))

    def _log_anomaly(self, anomaly: str, tick: int) -> None:
        entry = {
            "tick": tick,
            "anomaly": anomaly,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(self._anomalies_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_decision(self, decision: str, context: Dict[str, Any]) -> None:
        entry = {
            "decision": decision,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(self._decisions_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def recent_ticks(self, limit: int = 50) -> List[Dict]:
        return self._hot[-limit:]

    def recent_anomalies(self, limit: int = 50) -> List[Dict]:
        if not self._anomalies_path.exists():
            return []
        anomalies = []
        with open(self._anomalies_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        anomalies.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return anomalies[-limit:]

    def recent_decisions(self, limit: int = 50) -> List[Dict]:
        if not self._decisions_path.exists():
            return []
        decisions = []
        with open(self._decisions_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        decisions.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return decisions[-limit:]

    def memory_stats(self) -> Dict[str, Any]:
        return {
            "hot_entries": len(self._hot),
            "warm_entries": self._count_warm(),
            "anomaly_entries": self._count_file(self._anomalies_path),
            "decision_entries": self._count_file(self._decisions_path),
        }

    def _count_file(self, path: Path) -> int:
        if not path.exists():
            return 0
        with open(path) as f:
            return sum(1 for line in f if line.strip())
