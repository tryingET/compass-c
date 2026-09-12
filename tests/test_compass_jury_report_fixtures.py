"""Scratch-only 24-stage receipts using the unchanged generated scheduler, fake leaves.

No provider/auth imports or live runner execution. Pins are synthetic and scoped to
pytest monkeypatch; canonical receipts and sources are never written.
"""

import json
import shutil
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compass_jury_report as report  # noqa: E402

jury, live, envelope = report.jury, report.live, report.envelope
REPO = Path(__file__).resolve().parents[1]


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def judgment(inputs, field):
    contract = json.loads(inputs["judgment_contract_json"])
    verdicts = dict(zip(jury.JURORS, ("pass", "fail", "insufficient_evidence"), strict=True))
    verdict = verdicts.get(field, "insufficient_evidence")
    row = {
        "id": "quality",
        "verdict": verdict,
        "rationale": "PRIVATE synthetic judgment",
        "citations": [{"source": "tools", "quote": 'line one\n"line two"'}]
        if verdict != "insufficient_evidence"
        else [],
    }
    if field == "juror_2_json":
        row["citations"] = [{"source": "final", "quote": "PRIVATE final"}]
    if field == "adjudication_json":
        row.update(
            disagreement=True,
            addressed_jurors=[
                {
                    "juror": envelope.ALIASES[name],
                    "verdict": value,
                    "assessment": "PRIVATE synthetic assessment",
                }
                for name, value in verdicts.items()
            ],
        )
    value = {"binding": contract["binding"], "criteria": [row]}
    return (
        jury.canonical(value)
        if field == "adjudication_json"
        else json.dumps(value, ensure_ascii=False)
    )


def receipt(key, field, inner, object_value=False):
    return {
        "input_representation": "json_object" if object_value else "json_string",
        "observed_key": key,
        "expected_key": field,
        "serialized_inner_sha256": jury.sha(inner.encode("utf-8")),
        "semantic_sha256": jury.sha(jury.canonical(json.loads(inner)).encode("utf-8")),
        "reconciled": key != field or object_value,
        "inner_string_unchanged": not object_value,
        "decoded_judgment_unchanged": True,
    }


def bind(monkeypatch, base):
    source = base / live.SOURCE.relative_to(live.ROOT)
    program = base / jury.PROGRAM.relative_to(jury.ROOT)
    rubric = base / live.RUBRIC.relative_to(live.ROOT)
    prior = base / live.PRIOR_ATTEMPT_ROOT.relative_to(live.ROOT)
    seed = base / envelope.SEED_ROOT.relative_to(jury.ROOT)
    for obj in (report, live, jury):
        monkeypatch.setattr(obj, "ROOT", base)
    for key, value in {"SOURCE": source, "RUBRIC": rubric, "PRIOR_ATTEMPT_ROOT": prior}.items():
        monkeypatch.setattr(live, key, value)
    monkeypatch.setattr(jury, "PROGRAM", program)
    monkeypatch.setattr(envelope, "SEED_ROOT", seed)


@pytest.fixture
def full_run(tmp_path, monkeypatch):
    # Network block is installed BEFORE DSPy import, even its optional metadata fetches.
    def forbidden(*args, **kwargs):
        pytest.fail("network/provider/auth forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    dspy = pytest.importorskip("dspy")
    monkeypatch.setattr(dspy, "LM", forbidden)
    monkeypatch.setattr(live, "make_lm", forbidden)
    monkeypatch.setattr(live, "execute", forbidden)
    monkeypatch.setattr(live, "preflight", forbidden)
    base = tmp_path / "repository"
    bind(monkeypatch, base)
    root = base / ".compass/evaluations/glm53-jury-AK5673-subscription-v6"
    for path in [
        *REPO.joinpath("evals/dspx-jury/program").glob("*.py"),
        REPO / "evals/dspx-jury/program/generation.json",
        *(
            REPO / "scripts" / n
            for n in (
                "compass_jury.py",
                "compass_jury_live.py",
                "compass_jury_budget.py",
                "compass_jury_envelope.py",
            )
        ),
    ]:
        target = base / path.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    corpus = {
        "cases": [
            {
                "id": "synthetic",
                "prompt": "PRIVATE synthetic prompt",
                "expected_output": {"criteria": [{"id": "quality"}]},
            }
        ]
    }
    put(live.SOURCE / "corpus.json", corpus)
    put(live.RUBRIC, {"version": "offline", "rules": ["offline"], "common_criteria": []})
    # 290 is fixture size only. Reporter must derive the exact current glob, not guess.
    for index in range(1, 291):
        capture = {
            "caseId": "synthetic",
            "arm": "offline",
            "final": "**PRIVATE** final with  two spaces and `code`\n\nSecond **block**\n\n"
            "<span>hidden</span> marker\n\n![image](url) suffix",
            "messages": [],
            "tools": [{"text": 'line one\n"line two"'}],
            "status": "complete",
            "notebookCreated": False,
            "id": index,
        }
        put(live.SOURCE / f"t{index:03}.json", capture)
    frozen = root / "inputs"
    frozen.mkdir(parents=True)
    for path in (
        live.SOURCE / "corpus.json",
        live.RUBRIC,
        *(live.SOURCE / f"{c}.json" for c in report.CAPTURES),
    ):
        shutil.copyfile(path, frozen / path.name)
    prepared = {}
    for capture in report.CAPTURES:
        prepared[capture] = jury.prepare_inputs(
            frozen / "corpus.json", frozen / f"{capture}.json", frozen / "rubric.json"
        )
        put(frozen / f"{capture}.inputs.json", prepared[capture])
    generated = live.program_module()
    adapter = dspy.JSONAdapter(use_native_function_calling=False)
    ordinal, total, bounds = 0, 0, {}

    class FakeLeaf(dspy.Module):
        def __init__(self, capture, signature):
            super().__init__()
            self.capture, self.signature = capture, signature

        def forward(self, **values):
            nonlocal ordinal, total
            ordinal += 1
            (field,) = self.signature.output_fields
            capture = self.capture
            # Independently check generated dataflow before writing any fixture evidence.
            keys = ("evidence_json", "rubric_json", "judgment_contract_json")
            expected = {k: prepared[capture][k] for k in keys}
            if field == "adjudication_json":
                expected.pop("judgment_contract_json")
                expected["adjudication_contract_json"] = prepared[capture][
                    "adjudication_contract_json"
                ]
                expected.update({j: judgment(prepared[capture], j) for j in jury.JURORS})
            assert values == expected
            messages = adapter.format(self.signature, [], values)
            body = live.request_body(messages)
            # Real clients can elide stream=False; retained bodies are byte-preserved here.
            if ordinal % 2:
                body.pop("stream")
            size = len(envelope.encoded(messages))
            total += size
            bounds[capture][field] = size if field in jury.JURORS else report.budget.MESSAGE_LIMIT
            inner = judgment(prepared[capture], field)
            object_value = field == "adjudication_json"
            key = envelope.ALIASES[field] if ordinal % 2 or object_value else field
            content = json.dumps(
                {key: json.loads(inner) if object_value else inner}, ensure_ascii=False
            )
            response = {
                "id": f"offline-{ordinal}",
                "model": "glm-5.3",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 34,
                    "total_tokens": 46,
                    "completion_tokens_details": {"reasoning_tokens": 5},
                },
            }
            stage = root / f"{capture}--{field}"
            put(
                stage / "stage.json",
                {
                    "capture": capture,
                    "field": field,
                    "origin": "retained_v5_response"
                    if ordinal <= len(envelope.SEED_STAGES)
                    else "live_http",
                },
            )
            put(stage / "request.body.json", body)
            put(stage / "response.raw", response)
            (stage / "output.txt").write_bytes(content.encode("utf-8"))
            put(stage / "validated.json", json.loads(inner))
            put(stage / "http.json", {"status": 200})
            put(
                stage / "usage.json",
                {
                    "usage": response["usage"],
                    "reported_model": "glm-5.3",
                    "provider_identity_authenticated": False,
                },
            )
            put(
                stage / "attempt.json",
                {"attempt": ordinal, "message_bytes": size, "total_message_bytes": total},
            )
            put(stage / "envelope.json", receipt(key, field, inner, object_value))
            return dspy.Prediction(**{field: inner})

    for capture in report.CAPTURES:
        program = generated.build_program()
        bounds[capture] = {}
        for node in generated.MODULE_ORDER:
            setattr(program, node, FakeLeaf(capture, getattr(program, node).predict.signature))
        outputs = dict(program(**prepared[capture]))
        put(
            root / f"{capture}.outputs.json",
            {
                "requested_model": "openai/glm-5.3",
                "provider_model_authenticated": False,
                "raw_outputs": outputs,
                "judgments": {k: json.loads(v) for k, v in outputs.items()},
                "trace": program._last_runtime_trace,
                "semantic_correctness_established": False,
                "action_permission": "not_granted",
            },
        )
    assert ordinal == 24
    seed = envelope.SEED_ROOT
    shutil.copytree(frozen, seed / "inputs")
    receipts = []
    for index, active in enumerate(envelope.SEED_STAGES):
        name = "--".join(active)
        shutil.copytree(root / name, seed / name)
        origin = "retained_v4_response" if index < 4 else "live_http"
        put(
            seed / name / "stage.json", {"capture": active[0], "field": active[1], "origin": origin}
        )
        original = base / envelope.ORIGINAL_ROOTS[index] / name
        if original != seed / name:
            shutil.copytree(root / name, original)
            put(original / "stage.json", {"capture": active[0], "field": active[1]})
        receipts.append(
            {
                "capture": active[0],
                "field": active[1],
                "source_origin": origin,
                "request_sha256": jury.sha((seed / name / "request.body.json").read_bytes()),
                "response_sha256": jury.sha((seed / name / "response.raw").read_bytes()),
                **report.load(root / name / "envelope.json"),
                "original_response_root": envelope.ORIGINAL_ROOTS[index],
                "original_origin": "live_http",
            }
        )
    monkeypatch.setattr(
        envelope, "SEED_REQUEST_SHA256", tuple(r["request_sha256"] for r in receipts)
    )
    monkeypatch.setattr(
        envelope, "SEED_RESPONSE_SHA256", tuple(r["response_sha256"] for r in receipts)
    )
    prior = live.PRIOR_ATTEMPT_ROOT / "t059--juror_1_json/response.raw"
    put(prior, {"choices": [{"finish_reason": "length"}]})
    monkeypatch.setattr(live, "PRIOR_RESPONSE_SHA256", jury.sha(prior.read_bytes()))
    code_paths = [
        *jury.PROGRAM.glob("*.py"),
        jury.PROGRAM / "generation.json",
        *base.joinpath("scripts").glob("*.py"),
    ]
    inputs_hash = {
        p.name: jury.sha(p.read_bytes())
        for p in frozen.glob("*.json")
        if not p.name.endswith(".inputs.json")
    }
    code_hash = {str(p.relative_to(base)): jury.sha(p.read_bytes()) for p in code_paths}
    put(
        seed / "protocol.json",
        {
            "seed_root": envelope.V4_ROOT,
            "retained_prefix": [
                {**r, "source_origin": "retained_v3_response" if i < 3 else "live_http"}
                for i, r in enumerate(receipts[:4])
            ],
            "input_sha256": inputs_hash,
            "code_sha256": code_hash,
        },
    )
    put(
        root / "protocol.json",
        {
            "task": "AK5673",
            "captures": list(report.CAPTURES),
            "stages": list(jury.OUTPUTS),
            "model": "zai/glm-5.3",
            "endpoint": live.ENDPOINT,
            "temperature": 0.7,
            "max_tokens": 131072,
            "model_context": 1_000_000,
            "max_attempts": 24,
            "attempts_basis": "stage_attempts_including_retained_response",
            "planned_new_http_attempts": 24 - len(envelope.SEED_STAGES),
            "planned_reused_responses": len(envelope.SEED_STAGES),
            "planned_cumulative_unique_review_responses": 24,
            "unique_response_basis": "completed responses only; v1 truncated response excluded",
            "citation_matching": jury.CITATION_MATCHING,
            "representation_parser": {
                "package": "markdown-it-py",
                "version": "4.0.0",
                "preset": "commonmark",
            },
            "envelope_aliases": envelope.ALIASES,
            "juror_role_lookup_aliases": jury.JUROR_ALIASES,
            "envelope_policy": {
                "outer": "one string-or-object field; canonical key or its explicit alias only",
                "finish_reason": "stop",
                "inner": "validate frozen bindings/schema/citations and prior jurors before rename",
                "repair": False,
                "original_bytes": "response.raw and output.txt remain unchanged",
                "receipt": "envelope.json records representation, keys, serialized "
                "and semantic hashes",
            },
            "seed_root": str(seed.relative_to(base)),
            "retained_prefix": receipts,
            "timeout_seconds": 3600,
            "request_limit": 1_000_000,
            "response_limit": 8_000_000,
            "judgment_limit": 512_000,
            "cache": False,
            "retries": 0,
            "store": False,
            "store_wire_via_extra_body": True,
            "response_format": "json_object",
            "thinking_override": None,
            "billing_basis": "operator-confirmed subscription",
            "monetary_gate": False,
            "prior_attempt_root": str(live.PRIOR_ATTEMPT_ROOT.relative_to(base)),
            "prior_response_sha256": live.PRIOR_RESPONSE_SHA256,
            "original_sha256": {
                str(p.relative_to(base)): jury.sha(p.read_bytes())
                for p in sorted(live.SOURCE.glob("t*.json"))
            },
            "message_bounds": bounds,
            "input_sha256": inputs_hash,
            "code_sha256": code_hash,
        },
    )
    put(
        root / "complete.json",
        {
            "attempts": 24,
            "attempts_basis": "stage_attempts_including_retained_response",
            "stages": 24,
            "new_http_attempts": 24 - len(envelope.SEED_STAGES),
            "reused_responses": len(envelope.SEED_STAGES),
            "cumulative_unique_review_responses": 24,
            "message_bytes": total,
            "action_permission": "not_granted",
        },
    )
    return SimpleNamespace(root=root, base=base, seed=seed, prepared=prepared)
