from __future__ import annotations

from typing import Any

import dspy
from metadata import (
    CONSTRAINTS as CONSTRAINTS,
)
from metadata import (
    DECLARED_TOPOLOGY as DECLARED_TOPOLOGY,
)
from metadata import (
    EDGES as EDGES,
)
from metadata import (
    INFERRED_TOPOLOGY as INFERRED_TOPOLOGY,
)
from metadata import (
    MATERIALIZATION_SCOPE as MATERIALIZATION_SCOPE,
)
from metadata import (
    MATERIALIZED_TOPOLOGY as MATERIALIZED_TOPOLOGY,
)
from metadata import (
    METRIC as METRIC,
)
from metadata import (
    MODULE_ORDER as MODULE_ORDER,
)
from metadata import (
    MODULE_PRIMITIVES as MODULE_PRIMITIVES,
)
from metadata import (
    MODULE_SIGNATURES as MODULE_SIGNATURES,
)
from metadata import (
    OBJECTIVE as OBJECTIVE,
)
from metadata import (
    PROGRAM_OUTPUTS as PROGRAM_OUTPUTS,
)
from metadata import (
    PROGRAM_TEMPLATE_VERSION as PROGRAM_TEMPLATE_VERSION,
)
from metadata import (
    QUALITY_CRITERIA as QUALITY_CRITERIA,
)
from metadata import (
    SCHEDULER_PLAN as SCHEDULER_PLAN,
)
from metadata import (
    TOPOLOGY_EXECUTION_STATUS as TOPOLOGY_EXECUTION_STATUS,
)
from module import (
    CompassAdjudicatorModule,
    CompassJurorOneModule,
    CompassJurorThreeModule,
    CompassJurorTwoModule,
    io_spec,
)


def load_manifest() -> dict[str, Any]:
    return {}


def _manifest_hash() -> str:
    return ""


def configure_observability(
    *,
    run_name: str = "program-runtime",
    run_kind: str = "program-runtime",
) -> bool:
    return False


def end_observability_run(started: bool, *, status: str = "FINISHED") -> None:
    return None


def _prediction_mapping(prediction: object) -> dict[str, object]:
    return dict(prediction)


def _edge_condition_matches(edge: dict[str, object], state: dict[str, object]) -> bool:
    when = edge.get("when")
    if not isinstance(when, dict):
        return True
    field = str(when.get("field") or "")
    return str(state.get(field, "")) == str(when.get("equals"))


def _edge_source_ready(edge: dict[str, object], executed: set[str]) -> bool:
    source = str(edge.get("from") or "")
    return source == "input" or source in executed


def _module_ready(module_id: str, state: dict[str, object], executed: set[str]) -> bool:
    inputs = list(MODULE_SIGNATURES[module_id]["inputs"])
    if any(name not in state for name in inputs):
        return False
    inbound = [edge for edge in EDGES if edge.get("to") == module_id]
    if not inbound:
        return False
    return any(
        _edge_source_ready(edge, executed) and _edge_condition_matches(edge, state)
        for edge in inbound
    )


def _output_edges_ready(module_id: str, state: dict[str, object], executed: set[str]) -> bool:
    outbound = [
        edge for edge in EDGES if edge.get("from") == module_id and edge.get("to") == "output"
    ]
    return any(
        _edge_source_ready(edge, executed) and _edge_condition_matches(edge, state)
        for edge in outbound
    )


def _missing_declared_outputs(outputs: dict[str, object]) -> list[str]:
    return [name for name in PROGRAM_OUTPUTS if name not in outputs]


class CompassCaptureJuryPipelineProgram(dspy.Module):
    """Composed explicit pipeline topology program."""

    def __init__(self, use_cot: bool = False) -> None:
        super().__init__()
        self.juror_1 = CompassJurorOneModule(use_cot=use_cot)
        self.juror_2 = CompassJurorTwoModule(use_cot=use_cot)
        self.juror_3 = CompassJurorThreeModule(use_cot=use_cot)
        self.adjudicator = CompassAdjudicatorModule(use_cot=use_cot)

    def forward(
        self,
        evidence_json: str,
        rubric_json: str,
        judgment_contract_json: str,
        adjudication_contract_json: str,
    ) -> dspy.Prediction:
        state: dict[str, object] = {
            "evidence_json": evidence_json,
            "rubric_json": rubric_json,
            "judgment_contract_json": judgment_contract_json,
            "adjudication_contract_json": adjudication_contract_json,
        }
        delivered_outputs: dict[str, object] = {}
        self._last_runtime_trace = {
            "schema_version": "program-runtime-trace-fragment-v1",
            "module_calls": [],
            "final_outputs": {},
            "scheduler_events": [],
        }
        executed: set[str] = set()
        pending: set[str] = set(MODULE_ORDER)
        while pending:
            progressed = False
            for module_id in MODULE_ORDER:
                if module_id not in pending:
                    continue
                if not _module_ready(module_id, state, executed):
                    continue
                signature = MODULE_SIGNATURES[module_id]
                kwargs = {name: state[name] for name in signature["inputs"]}
                if module_id == "juror_1":
                    prediction = self.juror_1(**kwargs)
                elif module_id == "juror_2":
                    prediction = self.juror_2(**kwargs)
                elif module_id == "juror_3":
                    prediction = self.juror_3(**kwargs)
                elif module_id == "adjudicator":
                    prediction = self.adjudicator(**kwargs)
                else:
                    raise RuntimeError(f"unknown pipeline module: {module_id}")
                executed.add(module_id)
                pending = pending - {module_id}
                progressed = True
                mapped = _prediction_mapping(prediction)
                call_outputs: dict[str, object] = {}
                for output_name in signature["outputs"]:
                    if output_name in mapped:
                        state[output_name] = mapped[output_name]
                    if output_name in state:
                        call_outputs[output_name] = state[output_name]
                self._last_runtime_trace["module_calls"].append(
                    {
                        "module_id": module_id,
                        "primitive": MODULE_PRIMITIVES.get(module_id, "Predict"),
                        "inputs": _jsonable(kwargs),
                        "outputs": _jsonable(call_outputs),
                        "status": "executed",
                        "react_steps": [],
                        "react_v2_steps": [],
                        "program_of_thought_steps": [],
                        "tool_call_intents": [],
                        "tool_call_results": [],
                    }
                )
                if _output_edges_ready(module_id, state, executed):
                    for output_name in signature["outputs"]:
                        if output_name in PROGRAM_OUTPUTS and output_name in state:
                            delivered_outputs[output_name] = state[output_name]
            if not progressed:
                missing_outputs = _missing_declared_outputs(delivered_outputs)
                if missing_outputs:
                    self._last_runtime_trace["scheduler_events"].append(
                        {
                            "status": "scheduler_stalled",
                            "missing_outputs": list(missing_outputs),
                            "pending": sorted(pending),
                        }
                    )
                    raise RuntimeError(
                        "pipeline topology scheduler stalled before producing declared outputs: "
                        f"missing_outputs={missing_outputs} pending={sorted(pending)}"
                    )
                break
        missing_outputs = _missing_declared_outputs(delivered_outputs)
        if missing_outputs:
            self._last_runtime_trace["scheduler_events"].append(
                {
                    "status": "completed_missing_outputs",
                    "missing_outputs": list(missing_outputs),
                    "pending": sorted(pending),
                }
            )
            raise RuntimeError(
                "pipeline topology completed without declared outputs: "
                f"missing_outputs={missing_outputs}"
            )
        self._last_runtime_trace["scheduler_events"].append(
            {"status": "completed", "missing_outputs": [], "pending": []}
        )
        self._last_runtime_trace["final_outputs"] = _jsonable(delivered_outputs)
        return dspy.Prediction(
            juror_1_json=_jsonable(delivered_outputs["juror_1_json"]),
            juror_2_json=_jsonable(delivered_outputs["juror_2_json"]),
            juror_3_json=_jsonable(delivered_outputs["juror_3_json"]),
            adjudication_json=_jsonable(delivered_outputs["adjudication_json"]),
        )


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def build_program() -> dspy.Module:
    return CompassCaptureJuryPipelineProgram()


def build_student(*, use_cot: bool = False) -> dspy.Module:
    return CompassCaptureJuryPipelineProgram(use_cot=use_cot)


def intent_summary() -> dict[str, object]:
    return {
        "name": "CompassCaptureJury",
        "objective": OBJECTIVE,
        "constraints": list(CONSTRAINTS),
        "metric": METRIC,
        "quality_criteria": list(QUALITY_CRITERIA),
        "io": io_spec(),
        "declared_topology": dict(DECLARED_TOPOLOGY),
        "inferred_topology": dict(INFERRED_TOPOLOGY),
        "materialized_topology": dict(MATERIALIZED_TOPOLOGY),
        "topology_execution_status": TOPOLOGY_EXECUTION_STATUS,
        "materialization_scope": dict(MATERIALIZATION_SCOPE),
        "scheduler_plan": dict(SCHEDULER_PLAN),
        "module_order": list(MODULE_ORDER),
        "program_class": "CompassCaptureJuryPipelineProgram",
    }
