"""Local metadata router for the GlacierEQ portfolio evidence registry.

This module validates and reports repository evidence metadata. It does not
import subsystem implementations, contact external services, or operate any
infrastructure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "glaciereq.public-portfolio-receipt-router.v1"
EVIDENCE_STATE = "LOCAL_METADATA_ROUTER_NOT_RUNTIME_ORCHESTRATOR"
ALLOWED_CANDIDATE_CLASSIFICATIONS = {
    "REVIEWED_EXECUTION_BLOCKED",
    "GENERATED_EXECUTION_BLOCKED",
}


class RegistryValidationError(ValueError):
    """Raised when the public registry cannot support a bounded claim."""


def _require_mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RegistryValidationError(f"{name} must be a mapping")
    return value


def _require_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _require_positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RegistryValidationError(f"{name} must be a positive integer")
    return value


def validate_registry(raw: Any) -> dict:
    """Validate and normalize the local portfolio registry."""

    root = _require_mapping("registry", raw)
    if root.get("schema") != SCHEMA:
        raise RegistryValidationError(f"schema must equal {SCHEMA}")
    if root.get("evidence_state") != EVIDENCE_STATE:
        raise RegistryValidationError(
            f"evidence_state must equal {EVIDENCE_STATE}"
        )
    if root.get("non_affiliation") is not True:
        raise RegistryValidationError("non_affiliation must be true")

    verified_raw = _require_mapping("verified_sources", root.get("verified_sources"))
    if not verified_raw:
        raise RegistryValidationError("verified_sources must not be empty")

    verified: dict[str, dict] = {}
    repositories: set[str] = set()
    artifacts: set[int] = set()
    for domain_id in sorted(verified_raw):
        normalized_id = _require_string("verified domain id", domain_id)
        item = _require_mapping(f"verified_sources.{normalized_id}", verified_raw[domain_id])
        repository = _require_string(
            f"verified_sources.{normalized_id}.repository", item.get("repository")
        )
        if repository in repositories:
            raise RegistryValidationError("verified repository values must be unique")
        repositories.add(repository)

        source_pr = _require_positive_int(
            f"verified_sources.{normalized_id}.source_pull_request",
            item.get("source_pull_request"),
        )
        evidence_state = _require_string(
            f"verified_sources.{normalized_id}.evidence_state",
            item.get("evidence_state"),
        )
        if not evidence_state.endswith("_VERIFIED"):
            raise RegistryValidationError(
                f"verified source {normalized_id} must use a *_VERIFIED evidence state"
            )
        tests_passed = _require_positive_int(
            f"verified_sources.{normalized_id}.bounded_tests_passed",
            item.get("bounded_tests_passed"),
        )
        artifact_id = _require_positive_int(
            f"verified_sources.{normalized_id}.artifact_id", item.get("artifact_id")
        )
        if artifact_id in artifacts:
            raise RegistryValidationError("artifact_id values must be unique")
        artifacts.add(artifact_id)
        if item.get("merged") is not False:
            raise RegistryValidationError(
                f"verified source {normalized_id} must preserve merged=false"
            )
        public_claim = _require_string(
            f"verified_sources.{normalized_id}.public_claim", item.get("public_claim")
        )
        memory_tests = item.get("additional_memory_unit_tests_passed", 0)
        if isinstance(memory_tests, bool) or not isinstance(memory_tests, int) or memory_tests < 0:
            raise RegistryValidationError(
                "additional_memory_unit_tests_passed must be a non-negative integer"
            )

        verified[normalized_id] = {
            "repository": repository,
            "source_pull_request": source_pr,
            "evidence_state": evidence_state,
            "bounded_tests_passed": tests_passed,
            "additional_memory_unit_tests_passed": memory_tests,
            "artifact_id": artifact_id,
            "merged": False,
            "public_claim": public_claim,
            "promotion_ready": True,
        }

    candidates_raw = _require_mapping(
        "execution_blocked_candidates", root.get("execution_blocked_candidates")
    )
    candidates: dict[str, dict] = {}
    candidate_repositories: set[str] = set()
    for domain_id in sorted(candidates_raw):
        normalized_id = _require_string("candidate domain id", domain_id)
        item = _require_mapping(
            f"execution_blocked_candidates.{normalized_id}", candidates_raw[domain_id]
        )
        repository = _require_string(
            f"execution_blocked_candidates.{normalized_id}.repository",
            item.get("repository"),
        )
        if repository in repositories or repository in candidate_repositories:
            raise RegistryValidationError("source and candidate repositories must be unique")
        candidate_repositories.add(repository)
        source_pr = _require_positive_int(
            f"execution_blocked_candidates.{normalized_id}.source_pull_request",
            item.get("source_pull_request"),
        )
        classification = _require_string(
            f"execution_blocked_candidates.{normalized_id}.classification",
            item.get("classification"),
        )
        if classification not in ALLOWED_CANDIDATE_CLASSIFICATIONS:
            raise RegistryValidationError(
                f"unsupported candidate classification: {classification}"
            )
        generated_count = _require_positive_int(
            f"execution_blocked_candidates.{normalized_id}.generated_test_contract_count",
            item.get("generated_test_contract_count"),
        )
        if item.get("runner_steps_created") is not False:
            raise RegistryValidationError(
                f"candidate {normalized_id} must preserve runner_steps_created=false"
            )
        if item.get("counted_as_verified") is not False:
            raise RegistryValidationError(
                f"candidate {normalized_id} must preserve counted_as_verified=false"
            )
        strategic_priority = _require_positive_int(
            f"execution_blocked_candidates.{normalized_id}.strategic_priority",
            item.get("strategic_priority"),
        )
        candidate = {
            "repository": repository,
            "source_pull_request": source_pr,
            "classification": classification,
            "generated_test_contract_count": generated_count,
            "runner_steps_created": False,
            "counted_as_verified": False,
            "strategic_priority": strategic_priority,
            "promotion_ready": False,
        }
        if "static_review" in item:
            candidate["static_review"] = _require_string(
                f"execution_blocked_candidates.{normalized_id}.static_review",
                item["static_review"],
            )
        if "canonical_role" in item:
            candidate["canonical_role"] = _require_string(
                f"execution_blocked_candidates.{normalized_id}.canonical_role",
                item["canonical_role"],
            )
        candidates[normalized_id] = candidate

    priorities = [item["strategic_priority"] for item in candidates.values()]
    if len(priorities) != len(set(priorities)):
        raise RegistryValidationError("candidate strategic_priority values must be unique")

    aggregate_raw = _require_mapping(
        "aggregate_executed_evidence", root.get("aggregate_executed_evidence")
    )
    aggregate = {
        "verified_source_count": _require_positive_int(
            "aggregate_executed_evidence.verified_source_count",
            aggregate_raw.get("verified_source_count"),
        ),
        "bounded_source_tests_passed": _require_positive_int(
            "aggregate_executed_evidence.bounded_source_tests_passed",
            aggregate_raw.get("bounded_source_tests_passed"),
        ),
        "additional_energy_memory_unit_tests_passed": _require_positive_int(
            "aggregate_executed_evidence.additional_energy_memory_unit_tests_passed",
            aggregate_raw.get("additional_energy_memory_unit_tests_passed"),
        ),
        "direct_receipt_artifacts": _require_positive_int(
            "aggregate_executed_evidence.direct_receipt_artifacts",
            aggregate_raw.get("direct_receipt_artifacts"),
        ),
        "source_pull_requests_merged": aggregate_raw.get("source_pull_requests_merged"),
    }
    if aggregate["source_pull_requests_merged"] != 0:
        raise RegistryValidationError("source_pull_requests_merged must equal 0")
    if aggregate["verified_source_count"] != len(verified):
        raise RegistryValidationError("verified_source_count does not reconcile")
    if aggregate["bounded_source_tests_passed"] != sum(
        item["bounded_tests_passed"] for item in verified.values()
    ):
        raise RegistryValidationError("bounded source test total does not reconcile")
    if aggregate["additional_energy_memory_unit_tests_passed"] != sum(
        item["additional_memory_unit_tests_passed"] for item in verified.values()
    ):
        raise RegistryValidationError("additional memory test total does not reconcile")
    if aggregate["direct_receipt_artifacts"] != len(artifacts):
        raise RegistryValidationError("direct receipt artifact count does not reconcile")

    authorities_raw = _require_mapping(
        "canonical_authorities", root.get("canonical_authorities")
    )
    required_authorities = {
        "technical_sources",
        "portfolio_dependency_model",
        "human_evidence_navigator",
        "public_receipt_router",
    }
    if set(authorities_raw) != required_authorities:
        raise RegistryValidationError("canonical_authorities keys are incomplete or unknown")
    authorities = {
        key: _require_string(f"canonical_authorities.{key}", authorities_raw[key])
        for key in sorted(required_authorities)
    }

    historical_raw = _require_mapping(
        "historical_runtime_surfaces", root.get("historical_runtime_surfaces")
    )
    if historical_raw.get("classification") != "HISTORICAL_NON_AUTHORITATIVE":
        raise RegistryValidationError(
            "historical_runtime_surfaces must be HISTORICAL_NON_AUTHORITATIVE"
        )
    excluded_claims = historical_raw.get("excluded_claims")
    if not isinstance(excluded_claims, list) or not excluded_claims:
        raise RegistryValidationError("historical excluded_claims must be a non-empty list")
    normalized_excluded = tuple(
        _require_string("historical excluded claim", claim) for claim in excluded_claims
    )

    global_exclusions = root.get("global_exclusions")
    if not isinstance(global_exclusions, list) or not global_exclusions:
        raise RegistryValidationError("global_exclusions must be a non-empty list")
    normalized_global_exclusions = tuple(
        _require_string("global exclusion", claim) for claim in global_exclusions
    )

    actions_raw = _require_mapping("repository_actions", root.get("repository_actions"))
    expected_action_keys = {"deleted", "archived", "renamed", "collapsed", "merged_by_this_pass"}
    if set(actions_raw) != expected_action_keys:
        raise RegistryValidationError("repository_actions keys are incomplete or unknown")
    if any(actions_raw[key] != 0 for key in expected_action_keys):
        raise RegistryValidationError("all repository_actions values must equal 0")

    return {
        "schema": SCHEMA,
        "evidence_state": EVIDENCE_STATE,
        "non_affiliation": True,
        "verified_sources": verified,
        "execution_blocked_candidates": candidates,
        "aggregate_executed_evidence": aggregate,
        "canonical_authorities": authorities,
        "historical_runtime_surfaces": {
            "classification": "HISTORICAL_NON_AUTHORITATIVE",
            "excluded_claims": list(normalized_excluded),
        },
        "global_exclusions": list(normalized_global_exclusions),
        "repository_actions": {key: 0 for key in sorted(expected_action_keys)},
    }


def load_registry(path: str | Path) -> dict:
    registry_path = Path(path)
    if not registry_path.is_file():
        raise RegistryValidationError(f"registry file not found: {registry_path}")
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryValidationError(f"invalid registry JSON: {exc}") from exc
    return validate_registry(raw)


class PortfolioReceiptRouter:
    """Read-only local routing over validated portfolio evidence metadata."""

    def __init__(self, registry: Mapping[str, Any]) -> None:
        self._registry = validate_registry(registry)

    @classmethod
    def from_path(cls, path: str | Path) -> "PortfolioReceiptRouter":
        return cls(load_registry(path))

    def summary(self) -> dict:
        aggregate = dict(self._registry["aggregate_executed_evidence"])
        candidates = self._registry["execution_blocked_candidates"]
        return {
            "schema": "glaciereq.public-portfolio-summary.v1",
            "evidence_state": EVIDENCE_STATE,
            **aggregate,
            "execution_blocked_candidate_count": len(candidates),
            "candidate_generated_test_contract_count": sum(
                item["generated_test_contract_count"] for item in candidates.values()
            ),
            "candidate_priority": [
                domain_id
                for domain_id, _ in sorted(
                    candidates.items(),
                    key=lambda item: (
                        item[1]["strategic_priority"],
                        item[0],
                    ),
                )
            ],
            "external_queries_executed": 0,
            "external_actions_executed": 0,
        }

    def domains(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(self._registry["verified_sources"])
                | set(self._registry["execution_blocked_candidates"])
            )
        )

    def route(self, domain_id: str) -> dict:
        normalized_id = _require_string("domain_id", domain_id)
        if normalized_id in self._registry["verified_sources"]:
            return {
                "domain_id": normalized_id,
                "classification": "VERIFIED_SOURCE_PROMOTION",
                **self._registry["verified_sources"][normalized_id],
            }
        if normalized_id in self._registry["execution_blocked_candidates"]:
            return {
                "domain_id": normalized_id,
                **self._registry["execution_blocked_candidates"][normalized_id],
            }
        raise KeyError(normalized_id)

    def promotion_ready(self, domain_id: str) -> bool:
        return bool(self.route(domain_id)["promotion_ready"])

    def public_claims(self) -> tuple[dict, ...]:
        return tuple(
            {
                "domain_id": domain_id,
                "evidence_state": item["evidence_state"],
                "bounded_tests_passed": item["bounded_tests_passed"],
                "artifact_id": item["artifact_id"],
                "claim": item["public_claim"],
            }
            for domain_id, item in sorted(self._registry["verified_sources"].items())
        )

    def canonical_authorities(self) -> dict:
        return dict(self._registry["canonical_authorities"])

    def to_dict(self) -> dict:
        return json.loads(json.dumps(self._registry, sort_keys=True))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read validated local portfolio evidence metadata"
    )
    parser.add_argument(
        "--registry", default="PORTFOLIO_REGISTRY.json", help="Local registry JSON"
    )
    parser.add_argument("--domain", help="Return one domain record")
    parser.add_argument(
        "--claims", action="store_true", help="Return only bounded public claims"
    )
    args = parser.parse_args()

    router = PortfolioReceiptRouter.from_path(args.registry)
    if args.domain:
        payload: Any = router.route(args.domain)
    elif args.claims:
        payload = router.public_claims()
    else:
        payload = router.summary()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
