#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR=".verification-artifacts"
rm -rf "${ARTIFACT_DIR}"
mkdir -p "${ARTIFACT_DIR}"

python -m pip install --disable-pip-version-check --quiet -r requirements.txt
python -m pytest -q \
  tests/test_portfolio_router.py \
  tests/test_mastermind.py \
  tests/test_public_truth_surface.py \
  --junitxml="${ARTIFACT_DIR}/pytest.xml" \
  | tee "${ARTIFACT_DIR}/pytest.txt"

python - <<'PY'
import asyncio
import json
from pathlib import Path

from core.mastermind_orchestrator import MastermindOrchestrator, Task, TaskPriority
from core.portfolio_router import PortfolioReceiptRouter

artifact_dir = Path(".verification-artifacts")
router = PortfolioReceiptRouter.from_path("PORTFOLIO_REGISTRY.json")
summary = router.summary()
claims = router.public_claims()
authorities = router.canonical_authorities()

assert summary == {
    "schema": "glaciereq.public-portfolio-summary.v1",
    "evidence_state": "LOCAL_METADATA_ROUTER_NOT_RUNTIME_ORCHESTRATOR",
    "verified_source_count": 5,
    "bounded_source_tests_passed": 166,
    "additional_energy_memory_unit_tests_passed": 19,
    "direct_receipt_artifacts": 5,
    "source_pull_requests_merged": 0,
    "execution_blocked_candidate_count": 3,
    "candidate_generated_test_contract_count": 243,
    "candidate_priority": ["microcode", "architecture_planner", "waterplant"],
    "external_queries_executed": 0,
    "external_actions_executed": 0,
}
assert len(claims) == 5
assert {item["domain_id"] for item in claims} == {
    "cooling",
    "energy",
    "servers",
    "security",
    "nanosphere",
}
assert authorities["portfolio_dependency_model"] == "GlacierEQ/colossus-build-blueprint"
assert authorities["human_evidence_navigator"] == "GlacierEQ/xai-colossus-community"

# Prove the orchestration runtime separately from the evidence-router contract.
# CI does not assume sibling repositories exist, so bind a deterministic local
# subsystem adapter and require actual task/tick execution through Mastermind.
runtime = MastermindOrchestrator(
    "PORTFOLIO_REGISTRY.json",
    discover_siblings=False,
    tick_interval_seconds=0,
)

async def security_tick(tick_num: int):
    return {
        "anomalies": [],
        "actions": [{"action": "CI_LOCAL_RUNTIME_PROOF", "executed": True}],
        "tick_num": tick_num,
        "external_actions_executed": 0,
    }

runtime.register_subsystem(
    "security",
    security_tick,
    source="ci://local-security-adapter",
)

async def exercise_runtime():
    direct = await runtime.tick_subsystem("security")
    unbound = await runtime.tick_subsystem("microcode")
    task = Task(
        "ci-security-task",
        "execute bound security runtime proof",
        TaskPriority.P0_CRITICAL,
        preferred_piston="evidence_analyzer",
    )
    await runtime.submit_task(task)
    processed = await runtime.process_tasks(max_tasks=1)
    loop = await runtime.run(2, interval_seconds=0)
    return direct, unbound, processed, loop, runtime.summary()

runtime_direct, runtime_unbound, runtime_tasks, runtime_loop, runtime_summary = asyncio.run(
    exercise_runtime()
)
assert runtime_direct["executed"] is True
assert runtime_unbound["executed"] is False
assert runtime_tasks[0]["executed"] is True
assert runtime_tasks[0]["state"] == "completed"
assert len(runtime_loop) == 2
assert runtime_summary["runtime_orchestration_available"] is True
assert runtime_summary["runtime_state"] == "LOCAL_ORCHESTRATION_RUNTIME_RESTORED"

scenario = {
    "schema": "glaciereq.colossus-capability-evidence-scenario.v2",
    "evidence_router": {
        "summary": summary,
        "bounded_public_claims": list(claims),
        "authority_routing": authorities,
        "external_queries_executed": 0,
        "external_actions_executed": 0,
    },
    "runtime": {
        "state": runtime_summary["runtime_state"],
        "orchestration_available": runtime_summary["runtime_orchestration_available"],
        "direct_bound_tick": runtime_direct,
        "unbound_candidate_tick": runtime_unbound,
        "task_execution": runtime_tasks,
        "loop_ticks": [item["tick"] for item in runtime_loop],
        "bound_subsystems": runtime_summary["bound_subsystems"],
    },
    "truth_boundary": [
        "local runtime execution is not production deployment proof",
        "CI-injected adapter proves orchestration mechanics, not sibling repository availability",
        "portfolio evidence remains bounded to imported receipt metadata",
        "unbound candidates remain unexecuted until a real adapter exists",
        "no company affiliation or infrastructure authority is inferred",
    ],
}
scenario_path = artifact_dir / "capability-evidence-scenario.json"
scenario_path.write_text(
    json.dumps(scenario, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
claims_path = artifact_dir / "bounded-public-claims.json"
claims_path.write_text(
    json.dumps(list(claims), indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(scenario, indent=2, sort_keys=True))
PY

python - <<'PY'
import hashlib
import json
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

artifact_dir = Path(".verification-artifacts")
xml_root = ET.parse(artifact_dir / "pytest.xml").getroot()
suites = [xml_root] if xml_root.tag == "testsuite" else list(xml_root.findall("testsuite"))
counts = {
    "total": sum(int(suite.attrib.get("tests", 0)) for suite in suites),
    "failures": sum(int(suite.attrib.get("failures", 0)) for suite in suites),
    "errors": sum(int(suite.attrib.get("errors", 0)) for suite in suites),
    "skipped": sum(int(suite.attrib.get("skipped", 0)) for suite in suites),
}
counts["passed"] = counts["total"] - counts["failures"] - counts["errors"] - counts["skipped"]
assert counts["failures"] == 0, counts
assert counts["errors"] == 0, counts
assert counts["passed"] >= 40, counts

scenario_path = artifact_dir / "capability-evidence-scenario.json"
claims_path = artifact_dir / "bounded-public-claims.json"
registry_path = Path("PORTFOLIO_REGISTRY.json")
scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
assert scenario["evidence_router"]["summary"]["bounded_source_tests_passed"] == 166
assert scenario["runtime"]["orchestration_available"] is True
assert scenario["runtime"]["direct_bound_tick"]["executed"] is True
assert scenario["runtime"]["unbound_candidate_tick"]["executed"] is False

head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

receipt = {
    "schema": "glaciereq.colossus-capability-evidence-verification.v2",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "repository": "GlacierEQ/xai-colossus-2",
    "tested_commit_or_merge_ref": head,
    "source_head_commit": os.environ.get("GITHUB_HEAD_SHA") or head,
    "python": platform.python_version(),
    "verification_state": "LOCAL_RUNTIME_AND_BOUNDED_EVIDENCE_TEST_VERIFIED",
    "tests": counts,
    "verified": {
        "fail_closed_registry_validation": True,
        "aggregate_reconciliation": True,
        "execution_blocked_candidates_not_promoted": True,
        "bounded_public_claim_routing": True,
        "local_mastermind_runtime_executes_bound_subsystem": True,
        "local_mastermind_runtime_executes_queued_task": True,
        "unbound_runtime_does_not_fake_success": True,
        "runtime_and_evidence_planes_are_separate": True,
        "registry_sha256": digest(registry_path),
        "scenario_sha256": digest(scenario_path),
        "bounded_claims_sha256": digest(claims_path),
    },
    "not_verified": [
        "production or company deployment",
        "physical infrastructure authority or actuation",
        "sibling repository availability in this isolated CI checkout",
        "source repository behavior beyond imported receipt metadata except the injected CI adapter",
        "Microcode, architecture-planner, or Waterplant generated test contracts",
        "vendor validation, permits, legal conclusions, or physical-system safety",
        "hyperscale measured performance or business outcomes",
    ],
}
receipt_path = artifact_dir / "colossus-capability-evidence-verification.json"
receipt_path.write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(receipt, indent=2, sort_keys=True))
PY
