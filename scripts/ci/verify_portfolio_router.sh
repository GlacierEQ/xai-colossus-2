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

from core.mastermind_orchestrator import MastermindOrchestrator
from core.portfolio_router import PortfolioReceiptRouter

artifact_dir = Path(".verification-artifacts")
router = PortfolioReceiptRouter.from_path("PORTFOLIO_REGISTRY.json")
summary = router.summary()
claims = router.public_claims()
authorities = router.canonical_authorities()
facade = MastermindOrchestrator("PORTFOLIO_REGISTRY.json")
facade_tick = asyncio.run(facade.tick())
rejected_security_tick = asyncio.run(facade.tick_subsystem("security"))

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
assert facade_tick["external_queries_executed"] == 0
assert facade_tick["external_actions_executed"] == 0
assert rejected_security_tick["execution_rejected"] is True
assert rejected_security_tick["external_actions_executed"] == 0

scenario = {
    "schema": "glaciereq.public-portfolio-router-scenario.v1",
    "evidence_state": "LOCAL_METADATA_ROUTER_SCENARIO_VERIFIED",
    "summary": summary,
    "bounded_public_claims": list(claims),
    "canonical_authorities": authorities,
    "compatibility_facade_tick": facade_tick,
    "rejected_subsystem_tick": rejected_security_tick,
    "promotion_readiness": {
        domain_id: router.promotion_ready(domain_id)
        for domain_id in router.domains()
    },
    "external_queries_executed": 0,
    "external_actions_executed": 0,
    "limits": [
        "local registry metadata only",
        "does not re-execute source repositories",
        "does not import source implementations",
        "does not promote execution-blocked candidates",
        "does not operate infrastructure or external systems",
        "does not establish company affiliation or deployment",
    ],
}
assert scenario["promotion_readiness"] == {
    "architecture_planner": False,
    "cooling": True,
    "energy": True,
    "microcode": False,
    "nanosphere": True,
    "security": True,
    "servers": True,
    "waterplant": False,
}

scenario_path = artifact_dir / "portfolio-router-scenario.json"
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
assert counts == {
    "total": 69,
    "failures": 0,
    "errors": 0,
    "skipped": 0,
    "passed": 69,
}, counts

scenario_path = artifact_dir / "portfolio-router-scenario.json"
claims_path = artifact_dir / "bounded-public-claims.json"
registry_path = Path("PORTFOLIO_REGISTRY.json")
scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
assert scenario["summary"]["bounded_source_tests_passed"] == 166
assert scenario["summary"]["execution_blocked_candidate_count"] == 3
assert scenario["external_queries_executed"] == 0
assert scenario["external_actions_executed"] == 0

head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

receipt = {
    "schema": "glaciereq.public-portfolio-receipt-router-verification.v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "repository": "GlacierEQ/xai-colossus-2",
    "tested_commit_or_merge_ref": head,
    "source_head_commit": os.environ.get("GITHUB_HEAD_SHA") or head,
    "python": platform.python_version(),
    "evidence_state": "BOUNDED_PUBLIC_RECEIPT_ROUTER_TEST_VERIFIED",
    "tests": counts,
    "verified": {
        "fail_closed_registry_validation": True,
        "aggregate_reconciliation": True,
        "unique_source_and_artifact_identity": True,
        "execution_blocked_candidates_not_promoted": True,
        "bounded_public_claim_routing": True,
        "canonical_authority_routing": True,
        "compatibility_facade_non_execution": True,
        "historical_runtime_surfaces_non_authoritative": True,
        "external_queries_executed": 0,
        "external_actions_executed": 0,
        "registry_sha256": digest(registry_path),
        "scenario_sha256": digest(scenario_path),
        "bounded_claims_sha256": digest(claims_path),
    },
    "imported_source_evidence": {
        "verified_source_count": 5,
        "bounded_source_tests_passed": 166,
        "additional_energy_memory_unit_tests_passed": 19,
        "direct_receipt_artifacts": 5,
        "source_pull_requests_merged": 0,
    },
    "execution_blocked_candidates": {
        "microcode_generated_checks": 132,
        "architecture_planner_generated_checks": 59,
        "waterplant_generated_checks": 52,
        "counted_as_verified": False,
    },
    "not_verified": [
        "source repository behavior beyond imported receipt metadata",
        "Microcode, architecture-planner, or Waterplant generated test contracts",
        "live infrastructure, telemetry, orchestration, or external action",
        "company affiliation, employment, endorsement, access, or deployment",
        "vendor validation, permits, legal conclusions, or physical-system safety",
        "hyperscale operation or measured performance and business outcomes",
    ],
}
receipt_path = artifact_dir / "public-receipt-router-verification.json"
receipt_path.write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(receipt, indent=2, sort_keys=True))
PY
