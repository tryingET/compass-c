from __future__ import annotations

from rocs_cli.repo_view import RepoView
from rocs_cli.rules import Finding
from rocs_cli.validate import enforce_budget, validate_layers_exist, validate_manifest_placeholders, validate_reference_schema

def _schema_validation_result(
    view: RepoView,
    *,
    strict_placeholders: bool,
    validate_deps: bool,
) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    findings.extend(validate_manifest_placeholders(view.repo, strict_placeholders=strict_placeholders))
    findings.extend(validate_layers_exist(view.layers))
    schema_findings, _meta2 = validate_reference_schema(
        view.layers,
        strict_placeholders=strict_placeholders,
        validate_deps=validate_deps,
        concepts=view.concepts,
        relations=view.relations,
    )
    findings.extend(schema_findings)

    budget = None
    profile_def = view.meta.get("profile_def") or {}
    if isinstance(profile_def, dict) and profile_def.get("budget") is not None:
        budget_raw = profile_def.get("budget")
        if isinstance(budget_raw, (int, str)):
            try:
                budget = int(budget_raw)
            except Exception:
                findings.append(
                    Finding(
                        rule_id="BUD001",
                        severity="error",
                        message=f"invalid profile budget (expected int): {budget_raw!r}",
                    )
                )
        else:
            findings.append(
                Finding(
                    rule_id="BUD001",
                    severity="error",
                    message=f"invalid profile budget (expected int): {budget_raw!r}",
                )
            )
    ok_budget, budget_payload = enforce_budget(view.concepts, view.relations, budget=budget)
    if not ok_budget:
        findings.append(
            Finding(
                rule_id="BUD010",
                severity="error",
                message=f"budget exceeded: units={budget_payload['units']} budget={budget_payload['budget']}",
            )
        )

    return findings, budget_payload
