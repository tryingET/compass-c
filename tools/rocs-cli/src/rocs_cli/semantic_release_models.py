"""Immutable checked-object models and digest registry for Semantic Release v0."""
from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

# Schema discriminator -> (domain suffix, omitted digest field).  Coordinate
# identity hashes its complete object and therefore has no omitted field.
DIGEST_SPECS: Mapping[str, tuple[str, str | None]] = MappingProxyType({
    "semantic-release-coordinate.v0": ("coordinate", None),
    "semantic-source-manifest.v0": ("source-manifest", "source_manifest_digest"),
    "semantic-material-manifest.v0": ("material-manifest", "material_manifest_digest"),
    "semantic-owner-set.v0": ("owner-set", "owner_set_digest"),
    "semantic-approval-predicate.v0": ("approval-predicate", "approval_predicate_digest"),
    "semantic-owner-policy.v0": ("owner-policy", "owner_policy_digest"),
    "semantic-trust-root.v0": ("trust-root", "trust_root_digest"),
    "semantic-trust-rotation.v0": ("trust-rotation", "trust_rotation_digest"),
    "semantic-trust-revocation.v0": ("trust-revocation", "trust_revocation_digest"),
    "semantic-compatibility-policy.v0": ("compatibility-policy", "compatibility_policy_digest"),
    "semantic-compatibility-report.v0": ("compatibility-report", "compatibility_report_digest"),
    "semantic-compatibility-override.v0": ("compatibility-override", "compatibility_override_digest"),
    "semantic-deprecation-record.v0": ("deprecation-record", "deprecation_record_digest"),
    "semantic-removal-record.v0": ("removal-record", "removal_record_digest"),
    "semantic-tombstone-registry.v0": ("tombstone-registry", "tombstone_registry_digest"),
    "semantic-tombstone-history-proof.v0": ("tombstone-history-proof", "semantic_tombstone_history_proof_digest"),
    "semantic-publication-ledger-head.v0": ("publication-ledger-head", "publication_ledger_head_digest"),
    "semantic-accepted-lifecycle-ledger-record.v0": ("accepted-lifecycle-ledger-record", "accepted_lifecycle_ledger_record_digest"),
    "semantic-payload-projection.v0": ("payload-projection", "payload_projection_digest"),
    "semantic-capsule-archive-linkage.v0": ("capsule-archive-linkage", "capsule_archive_linkage_digest"),
    "semantic-release-capsule.v0": ("capsule", "capsule_digest"),
    "semantic-ak-decision-reference.v0": ("ak-decision-reference", "ak_decision_reference_digest"),
    "semantic-owner-approval.v0": ("owner-approval", "owner_approval_digest"),
    "semantic-build-receipt.v0": ("build-receipt", "build_receipt_digest"),
    "semantic-publication-transaction.v0": ("publication-transaction", "publication_transaction_digest"),
    "semantic-publication-journal.v0": ("publication-journal", "publication_journal_digest"),
    "semantic-publication-recovery-intent-marker.v0": ("publication-recovery-intent-marker", "publication_recovery_intent_marker_digest"),
    "semantic-publication-commit-marker.v0": ("publication-commit-marker", "publication_commit_marker_digest"),
    "semantic-publication-recovery-state-receipt.v0": ("publication-recovery-state-receipt", "publication_recovery_state_receipt_digest"),
    "semantic-owner-publication.v0": ("owner-publication", "owner_publication_digest"),
    "semantic-publication-status-transition.v0": ("publication-status-transition", "publication_status_transition_digest"),
    "semantic-consumer-intent.v0": ("consumer-intent", "consumer_intent_digest"),
    "semantic-owner-acceptance.v0": ("owner-acceptance", "owner_acceptance_digest"),
    "semantic-materialization-verification-receipt.v0": ("materialization-verification", "materialization_verification_receipt_digest"),
    "semantic-activation-receipt.v0": ("activation", "activation_receipt_digest"),
    "semantic-rocs-generation-receipt.v0": ("rocs-generation", "rocs_generation_receipt_digest"),
    "semantic-pi-delivery-receipt.v0": ("pi-delivery", "pi_delivery_receipt_digest"),
    "semantic-ak-evidence-linkage.v0": ("ak-evidence-linkage", "ak_evidence_linkage_digest"),
    "semantic-rollback-request.v0": ("rollback-request", "rollback_request_digest"),
    "semantic-rollback-technical-receipt.v0": ("rollback-technical-receipt", "rollback_technical_receipt_digest"),
    "semantic-rollback-availability-receipt.v0": ("rollback-availability-receipt", "rollback_available_artifact_digest"),
    "semantic-rollback-availability-proof.v0": ("rollback-availability-proof", "rollback_availability_proof_digest"),
    "semantic-rollback-history-transition.v0": ("rollback-history-transition", "rollback_history_transition_digest"),
    "semantic-rollback-receipt.v0": ("rollback-receipt", "rollback_receipt_digest"),
    "semantic-non-authorizing-task-contract.v0": ("non-authorizing-task-contract", "non_authorizing_task_contract_digest"),
    "semantic-audit-envelope.v0": ("audit-envelope", "audit_envelope_digest"),
    "semantic-protocol-error.v0": ("error", "error_digest"),
    "semantic-owner-acquisition-capability-pin.v0": ("owner-acquisition-capability-pin", "capability_pin_digest"),
    "semantic-authority-acquisition-config.v0": ("authority-acquisition-config", "authority_acquisition_config_digest"),
    "semantic-owner-store-read-receipt.v0": ("owner-store-read-receipt", "owner_store_read_receipt_digest"),
    "semantic-authority-snapshot.v0": ("authority-snapshot", "authority_snapshot_digest"),
    "semantic-authority-rule-role-manifest.v0": ("authority-rule-role-manifest", "authority_rule_role_manifest_digest"),
    "semantic-authority-proof-bundle.v0": ("authority-proof-bundle", "authority_proof_bundle_digest"),
    "semantic-authority-verifier-input.v0": ("authority-verifier-input", "authority_verifier_input_digest"),
})


@dataclass(frozen=True)
class CheckedReleaseObject:
    """Immutable schema-and-recursive-digest checked object snapshot.

    This is intentionally not named a full authority validation token. Cross-owner
    currentness and transition invariants remain the job of the closed authority
    verifier and cannot be inferred from this value.
    """

    schema: str
    definition: str
    canonical_bytes: bytes
    computed_digest: str
    validation_scope: str = "schema_and_recursive_digest"

    def to_value(self) -> dict[str, Any]:
        value = json.loads(self.canonical_bytes.decode("utf-8"))
        if type(value) is not dict:
            raise ValueError("checked object snapshot is not an object")
        return value


@dataclass(frozen=True)
class CheckedCoordinate(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedAcquisitionObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedPublicationObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedConsumerObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedMaterializationObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedActivationObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedGenerationObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedDeliveryObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedEvidenceObject(CheckedReleaseObject):
    pass


@dataclass(frozen=True)
class CheckedRollbackObject(CheckedReleaseObject):
    pass



def checked_type(schema_name: str) -> type[CheckedReleaseObject]:
    if schema_name == "semantic-release-coordinate.v0":
        return CheckedCoordinate
    if schema_name in {
        "semantic-owner-acquisition-capability-pin.v0",
        "semantic-authority-acquisition-config.v0",
        "semantic-owner-store-read-receipt.v0",
        "semantic-authority-snapshot.v0",
        "semantic-authority-rule-role-manifest.v0",
        "semantic-authority-proof-bundle.v0",
        "semantic-authority-verifier-input.v0",
    }:
        return CheckedAcquisitionObject
    if schema_name.startswith("semantic-publication-") or schema_name in {
        "semantic-owner-publication.v0", "semantic-trust-root.v0",
        "semantic-trust-rotation.v0", "semantic-trust-revocation.v0",
    }:
        return CheckedPublicationObject
    if schema_name in {"semantic-consumer-intent.v0", "semantic-owner-acceptance.v0"}:
        return CheckedConsumerObject
    if schema_name == "semantic-materialization-verification-receipt.v0":
        return CheckedMaterializationObject
    if schema_name == "semantic-activation-receipt.v0":
        return CheckedActivationObject
    if schema_name == "semantic-rocs-generation-receipt.v0":
        return CheckedGenerationObject
    if schema_name == "semantic-pi-delivery-receipt.v0":
        return CheckedDeliveryObject
    if schema_name == "semantic-ak-evidence-linkage.v0":
        return CheckedEvidenceObject
    if schema_name.startswith("semantic-rollback-"):
        return CheckedRollbackObject
    return CheckedReleaseObject
