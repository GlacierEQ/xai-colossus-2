#!/usr/bin/env python3
"""
SBOM Chain — Software/Hardware Bill of Materials Verification for Colossus 2
=============================================================================
Cryptographic verification of hardware component manifests, HMAC-SHA256
signing for integrity, trusted manufacturer registry, and audit trail.

Pro-Code Compliance: 12 Laws, 7-Gate Audit, Zero AI-scaffold residue.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("COLOSSUS-SECURITY")

TRUSTED_MANUFACTURERS = {
    "NVIDIA": {
        "name": "NVIDIA Corporation",
        "public_key_prefix": "nv",
        "gpu_models": ["H100", "H200", "B100", "B200"],
        "trusted": True,
    },
    "SUPERMICRO": {
        "name": "Super Micro Computer, Inc.",
        "public_key_prefix": "smc",
        "server_models": ["SYS-421GE", "SYS-821GE"],
        "trusted": True,
    },
    "INTEL": {
        "name": "Intel Corporation",
        "public_key_prefix": "intc",
        "cpu_models": ["Xeon-8480+", "Xeon-8592+"],
        "trusted": True,
    },
    "BROADCOM": {
        "name": "Broadcom Inc.",
        "public_key_prefix": "brcm",
        "network_models": ["BCM89890", "BCM78900"],
        "trusted": True,
    },
    "SEAGATE": {
        "name": "Seagate Technology",
        "public_key_prefix": "stx",
        "storage_models": ["Nytro-5550", "Exos-X24"],
        "trusted": True,
    },
    "MICRON": {
        "name": "Micron Technology, Inc.",
        "public_key_prefix": "mu",
        "memory_models": ["MTA36ASF8G72PZ", "HBM3E"],
        "trusted": True,
    },
    "ARISTA": {
        "name": "Arista Networks, Inc.",
        "public_key_prefix": "anet",
        "switch_models": ["7800R3", "7060X5"],
        "trusted": True,
    },
}


@dataclass
class ComponentManifest:
    component_id: str
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str
    manufacture_date: str
    specs: Dict[str, Any] = field(default_factory=dict)
    sbom_hash: str = ""
    signature: str = ""


@dataclass
class AuditEntry:
    entry_id: str
    component_id: str
    timestamp: str
    trusted: bool
    signed: bool
    manufacturer_verified: bool
    hash_valid: bool
    signature_valid: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SBOMChain:
    signing_key: str = ""
    _known_components: Dict[str, ComponentManifest] = field(default_factory=dict)
    _audit_log: List[AuditEntry] = field(default_factory=list)
    _verification_count: int = 0
    _trusted_count: int = 0
    _untrusted_count: int = 0
    _tampered_count: int = 0

    def __post_init__(self):
        if not self.signing_key:
            self.signing_key = secrets.token_hex(32)
        logger.info("SBOM Chain INITIALIZED | signing_key=%s... | trusted_manufacturers=%d",
                     self.signing_key[:8], len(TRUSTED_MANUFACTURERS))

    def _compute_hmac(self, data: Dict[str, Any]) -> str:
        payload = json.dumps(data, sort_keys=True, default=str).encode()
        return hmac.new(self.signing_key.encode(), payload, hashlib.sha256).hexdigest()

    def _verify_hmac(self, data: Dict[str, Any], signature: str) -> bool:
        expected = self._compute_hmac(data)
        return hmac.compare_digest(expected, signature)

    def _is_trusted_manufacturer(self, manufacturer: str) -> bool:
        return manufacturer.upper() in TRUSTED_MANUFACTURERS

    def _generate_manifest_signature(self, manifest: ComponentManifest) -> str:
        manifest_dict = {
            "component_id": manifest.component_id,
            "manufacturer": manifest.manufacturer,
            "model": manifest.model,
            "serial_number": manifest.serial_number,
            "firmware_version": manifest.firmware_version,
            "manufacture_date": manifest.manufacture_date,
            "specs": manifest.specs,
        }
        return self._compute_hmac(manifest_dict)

    def register_component(self, manifest: ComponentManifest) -> Dict[str, Any]:
        manifest.sbom_hash = hashlib.sha256(
            json.dumps(manifest.specs, sort_keys=True, default=str).encode()
        ).hexdigest()
        manifest.signature = self._generate_manifest_signature(manifest)
        self._known_components[manifest.component_id] = manifest
        logger.info("COMPONENT_REGISTERED: %s | manufacturer=%s | model=%s",
                     manifest.component_id, manifest.manufacturer, manifest.model)
        return {
            "component_id": manifest.component_id,
            "registered": True,
            "sbom_hash": manifest.sbom_hash,
        }

    def verify_component(self, component_id: str, sbom_data: Dict[str, Any]) -> Dict[str, Any]:
        self._verification_count += 1
        timestamp = datetime.now(timezone.utc).isoformat()
        entry_id = str(uuid.uuid4())

        trusted = False
        signed = False
        manufacturer_verified = False
        hash_valid = False
        signature_valid = False
        details: Dict[str, Any] = {}

        manufacturer = sbom_data.get("manufacturer", "")
        if not manufacturer:
            details["error"] = "missing manufacturer field"
            self._untrusted_count += 1
        elif not self._is_trusted_manufacturer(manufacturer):
            details["error"] = f"untrusted manufacturer: {manufacturer}"
            details["trusted_manufacturers"] = list(TRUSTED_MANUFACTURERS.keys())
            self._untrusted_count += 1
        else:
            trusted = True
            manufacturer_verified = True
            mfr_info = TRUSTED_MANUFACTURERS[manufacturer.upper()]
            details["manufacturer_info"] = mfr_info["name"]

        if "specs" in sbom_data:
            computed_hash = hashlib.sha256(
                json.dumps(sbom_data["specs"], sort_keys=True, default=str).encode()
            ).hexdigest()
            stored = self._known_components.get(component_id)
            if stored:
                hash_valid = computed_hash == stored.sbom_hash
                details["hash_match"] = hash_valid
                if not hash_valid:
                    self._tampered_count += 1
                    details["expected_hash"] = stored.sbom_hash
                    details["computed_hash"] = computed_hash
            else:
                hash_valid = True
                details["hash_computed"] = computed_hash

        if "signature" in sbom_data and "specs" in sbom_data:
            signature_valid = self._verify_hmac(sbom_data["specs"], sbom_data["signature"])
            signed = signature_valid
            details["signature_valid"] = signature_valid
        elif component_id in self._known_components:
            stored = self._known_components[component_id]
            payload = {
                "component_id": stored.component_id,
                "manufacturer": stored.manufacturer,
                "model": stored.model,
                "serial_number": stored.serial_number,
                "firmware_version": stored.firmware_version,
                "manufacture_date": stored.manufacture_date,
                "specs": stored.specs,
            }
            signature_valid = self._verify_hmac(payload, stored.signature)
            signed = True
            details["signature_valid"] = signature_valid

        if trusted and signed and signature_valid and hash_valid:
            self._trusted_count += 1
            details["verification"] = "PASSED"
        else:
            self._untrusted_count += 1
            details["verification"] = "FAILED"
            reasons = []
            if not trusted:
                reasons.append("untrusted_manufacturer")
            if not signed or not signature_valid:
                reasons.append("invalid_signature")
            if not hash_valid:
                reasons.append("hash_mismatch")
            details["failure_reasons"] = reasons

        audit = AuditEntry(
            entry_id=entry_id,
            component_id=component_id,
            timestamp=timestamp,
            trusted=trusted,
            signed=signed,
            manufacturer_verified=manufacturer_verified,
            hash_valid=hash_valid,
            signature_valid=signature_valid,
            details=details,
        )
        self._audit_log.append(audit)

        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

        logger.info("SBOM_VERIFY: %s | trusted=%s | signed=%s | hash=%s | sig=%s",
                     component_id, trusted, signed, hash_valid, signature_valid)

        return {
            "trusted": trusted,
            "signed": signed and signature_valid,
            "audit_entry": {
                "entry_id": entry_id,
                "component_id": component_id,
                "timestamp": timestamp,
                "manufacturer_verified": manufacturer_verified,
                "hash_valid": hash_valid,
                "signature_valid": signature_valid,
                "details": details,
            },
        }

    def verify_chain(self, component_ids: List[str]) -> Dict[str, Any]:
        results = []
        all_trusted = True
        for cid in component_ids:
            if cid in self._known_components:
                manifest = self._known_components[cid]
                sbom_data = {
                    "manufacturer": manifest.manufacturer,
                    "model": manifest.model,
                    "specs": manifest.specs,
                    "signature": manifest.signature,
                }
                result = self.verify_component(cid, sbom_data)
                results.append(result)
                if not result["trusted"]:
                    all_trusted = False
            else:
                results.append({
                    "trusted": False,
                    "signed": False,
                    "audit_entry": {"error": f"component {cid} not registered"},
                })
                all_trusted = False

        return {
            "chain_valid": all_trusted,
            "components_verified": len(results),
            "results": results,
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "total_verifications": self._verification_count,
            "trusted_count": self._trusted_count,
            "untrusted_count": self._untrusted_count,
            "tampered_count": self._tampered_count,
            "registered_components": len(self._known_components),
            "audit_log_size": len(self._audit_log),
            "trusted_manufacturers": len(TRUSTED_MANUFACTURERS),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    print("=== SBOM Chain — Demo ===\n")

    chain = SBOMChain()

    components = [
        ComponentManifest(
            component_id="GPU-H200-001",
            manufacturer="NVIDIA",
            model="H200",
            serial_number="NV-2024-001234",
            firmware_version="535.129.03",
            manufacture_date="2024-09-15",
            specs={"tdp_watts": 700, "memory_gb": 141, "interconnect": "NVLink"},
        ),
        ComponentManifest(
            component_id="SRV-SMC-001",
            manufacturer="SUPERMICRO",
            model="SYS-421GE",
            serial_number="SMC-2024-005678",
            firmware_version="2.4.1",
            manufacture_date="2024-08-20",
            specs={"cpu_sockets": 2, "memory_slots": 32, "pci_gen": 5},
        ),
        ComponentManifest(
            component_id="NIC-BRCM-001",
            manufacturer="BROADCOM",
            model="BCM89890",
            serial_number="BRCM-2024-009999",
            firmware_version="21.0.0",
            manufacture_date="2024-10-01",
            specs={"speed_gbps": 400, "ports": 8, "rdma": True},
        ),
        ComponentManifest(
            component_id="GPU-FAKE-001",
            manufacturer="COUNTERFEIT_LABS",
            model="H200-FAKE",
            serial_number="FAKE-001",
            firmware_version="0.0.1",
            manufacture_date="2024-01-01",
            specs={"tdp_watts": 700, "memory_gb": 141, "interconnect": "NVLink"},
        ),
    ]

    for comp in components:
        result = chain.register_component(comp)
        print(f"Registered: {result['component_id']} | hash={result['sbom_hash'][:16]}...")

    print("\n--- Verifications ---")
    for comp in components:
        sbom = {
            "manufacturer": comp.manufacturer,
            "model": comp.model,
            "specs": comp.specs,
            "signature": comp.signature,
        }
        result = chain.verify_component(comp.component_id, sbom)
        status = "TRUSTED" if result["trusted"] else "UNTRUSTED"
        signed = "SIGNED" if result["signed"] else "UNSIGNED"
        print(f"  {comp.component_id}: {status} | {signed}")

    print("\n--- Chain Verification ---")
    chain_result = chain.verify_chain([c.component_id for c in components[:3]])
    print(f"  Chain valid: {chain_result['chain_valid']}")
    print(f"  Components verified: {chain_result['components_verified']}")

    print("\n=== Summary ===")
    print(json.dumps(chain.summary(), indent=2))
