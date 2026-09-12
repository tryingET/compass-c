"""Offline custody proofs; optional owner environment exercises the real LM stack."""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import compass_jury_budget as budget  # noqa: E402
import compass_jury_live as live  # noqa: E402


def test_attempt_ledger_only_counts_requests_and_never_releases():
    ledger = budget.AttemptLedger()
    assert vars(ledger) == {"calls": 0, "message_bytes": 0}
    for _ in range(24):
        ledger.record(budget.MESSAGE_LIMIT)
    assert vars(ledger) == {"calls": 24, "message_bytes": 24 * budget.MESSAGE_LIMIT}
    with pytest.raises(ValueError, match="attempt cap"):
        ledger.record(1)
    assert ledger.calls == 24
    assert not any(
        hasattr(budget, name) for name in ("Budget", "ALLOWANCE", "PRIOR", "reservation")
    )


def test_one_shot_refuses_after_failure_and_concurrent(tmp_path):
    with pytest.raises(RuntimeError), live.one_shot(tmp_path):
        with pytest.raises((BlockingIOError, FileExistsError)), live.one_shot(tmp_path):
            pass
        raise RuntimeError("crash")
    with pytest.raises(FileExistsError), live.one_shot(tmp_path):
        pass
    assert (tmp_path / "ONE_SHOT").exists()


def test_cli_has_no_overrides_or_default_execution(monkeypatch):
    monkeypatch.setattr(live, "execute", lambda: pytest.fail("executed"))
    assert live.main([]) == 0
    for args in (["--output-root", "x"], ["--max-tokens", "1"], ["--budget", "20"]):
        with pytest.raises(SystemExit):
            live.main(args)


@pytest.fixture
def httpx():
    return pytest.importorskip("httpx")


def bounds():
    return {c: {f: budget.MESSAGE_LIMIT for f in live.jury.OUTPUTS} for c in live.CAPTURES}


def body():
    return live.request_body([{"role": "user", "content": "synthetic"}])


def require_private_evidence():
    if os.environ.get("COMPASS_JURY_PRIVATE_EVIDENCE") != "1":
        pytest.skip("private captures: opt in with COMPASS_JURY_PRIVATE_EVIDENCE=1")
    required = [
        live.SOURCE / "corpus.json",
        live.PRIOR_ATTEMPT_ROOT / "t059--juror_1_json/response.raw",
        *(
            live.envelope.SEED_ROOT / "--".join(s) / "response.raw"
            for s in live.envelope.SEED_STAGES
        ),
    ]
    if not all(path.is_file() for path in required):
        pytest.fail("explicit private-evidence verification requires retained capture files")


def test_private_evidence_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("COMPASS_JURY_PRIVATE_EVIDENCE", raising=False)
    with pytest.raises(pytest.skip.Exception, match="opt in"):
        require_private_evidence()


def test_private_evidence_opt_in_fails_if_files_are_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("COMPASS_JURY_PRIVATE_EVIDENCE", "1")
    monkeypatch.setattr(live, "SOURCE", tmp_path / "missing")
    with pytest.raises(pytest.fail.Exception, match="requires retained capture"):
        require_private_evidence()


def fixture_inputs(capture="t059"):
    require_private_evidence()
    return live.jury.prepare_inputs(
        live.SOURCE / "corpus.json", live.SOURCE / f"{capture}.json", live.RUBRIC
    )


def guard_root(root):
    require_private_evidence()
    frozen = root / "inputs"
    if not frozen.exists():
        frozen.mkdir()
        for path in (
            live.SOURCE / "corpus.json",
            live.RUBRIC,
            *(live.SOURCE / f"{c}.json" for c in live.CAPTURES),
        ):
            live.durable(frozen / path.name, path.read_bytes())
        for capture in live.CAPTURES:
            live.save(frozen / f"{capture}.inputs.json", fixture_inputs(capture))
    return root


@pytest.fixture(autouse=True)
def all_live_offline_only(monkeypatch):
    # Production has no opt-out: only this narrow offline test seam omits the seed.
    monkeypatch.setattr(live.envelope, "load_seed", lambda: None)


def response_payload(field="juror_1_json", text=None):
    if text is None:
        text = synthetic_judgment(fixture_inputs(), field)
    return {
        "id": "offline",
        "object": "chat.completion",
        "created": 0,
        "model": "glm-5.3",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({field: text})},
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46},
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "method",
        "url",
        "query",
        "model",
        "store",
        "tokens",
        "bool_tokens",
        "lower_tokens",
        "n",
        "stream",
        "schema",
        "nonjson",
        "duplicate",
        "oversize",
        "unknown",
        "messages",
        "type",
    ],
)
def test_guard_rejects_before_network(httpx, tmp_path, mutation):
    calls = []
    guard = live.GuardTransport(
        httpx.MockTransport(lambda r: calls.append(r)), guard_root(tmp_path), bounds()
    )
    guard.begin_stage("t059", "juror_1_json")
    data, method, url, content_type = body(), "POST", live.ENDPOINT, "application/json"
    if mutation == "method":
        method = "GET"
    elif mutation == "url":
        url = "https://api.z.ai/api/paas/v4/chat/completions"
    elif mutation == "query":
        url += "?other=1"
    elif mutation == "model":
        data["model"] = "glm-5.3-flash"
    elif mutation == "store":
        del data["store"]
    elif mutation == "tokens":
        data["max_tokens"] = budget.MAX_TOKENS + 1
    elif mutation == "lower_tokens":
        data["max_tokens"] = budget.MAX_TOKENS - 1
    elif mutation == "bool_tokens":
        data["max_tokens"] = True
    elif mutation == "n":
        data["n"] = 2
    elif mutation == "stream":
        data["stream"] = True
    elif mutation == "schema":
        data["response_format"] = {"type": "json_schema"}
    elif mutation == "unknown":
        data["tools"] = []
    elif mutation == "messages":
        data["messages"][0]["content"] = []
    elif mutation == "type":
        content_type = "text/plain"
    raw = live.encoded(data)
    if mutation == "nonjson":
        raw = b"not JSON"
    elif mutation == "duplicate":
        raw = raw[:-1] + b',"store":false}'
    elif mutation == "oversize":
        raw += b" " * budget.REQUEST_LIMIT
    with pytest.raises(ValueError):
        guard.handle_request(
            httpx.Request(method, url, content=raw, headers={"content-type": content_type})
        )
    assert not calls
    assert guard.failed
    expected = "JSONDecodeError" if mutation == "nonjson" else "ValueError"
    assert json.loads((guard.stage_dir / "error.json").read_text()) == {"error_type": expected}


def test_single_attempt_hidden_retry_and_duplicate_stage(httpx, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.extensions["timeout"]["read"] == 3600
        return httpx.Response(200, json=response_payload())

    guard = live.GuardTransport(httpx.MockTransport(handler), guard_root(tmp_path), bounds())
    guard.begin_stage("t059", "juror_1_json")
    request = httpx.Request(
        "POST", live.ENDPOINT, json=body(), headers={"authorization": "Bearer synthetic-secret"}
    )
    guard.handle_request(request)
    with pytest.raises(ValueError):
        guard.handle_request(request)
    with pytest.raises(ValueError):
        guard.begin_stage("t059", "juror_1_json")
    assert len(calls) == 1
    assert guard.ledger.calls == 1
    assert all(b"synthetic-secret" not in p.read_bytes() for p in guard.stage_dir.iterdir())


@pytest.mark.parametrize("status", [301, 307, 400, 429, 500, 503])
def test_http_failures_raw_retained_no_redirect(httpx, tmp_path, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, content=b"forensic raw failure", headers={"location": live.ENDPOINT}
        )

    guard = live.GuardTransport(httpx.MockTransport(handler), guard_root(tmp_path), bounds())
    guard.begin_stage("t059", "juror_1_json")
    with httpx.Client(transport=guard, follow_redirects=True) as client:
        with pytest.raises(ValueError):
            client.post(live.ENDPOINT, json=body())
    assert len(calls) == 1
    assert (guard.stage_dir / "response.raw").read_bytes() == b"forensic raw failure"
    assert guard.ledger.calls == 1


@pytest.mark.parametrize(
    "kind",
    [
        "oversize",
        "disconnect",
        "timeout",
        "malformed",
        "length",
        "long_juror",
        "duplicate_wire",
        "duplicate_outer",
    ],
)
def test_response_failures_stop_and_retain(httpx, tmp_path, kind):
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"partial"
            raise httpx.ReadError("synthetic-secret")

    def handler(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("synthetic-secret")
        if kind == "disconnect":
            return httpx.Response(200, stream=Stream())
        if kind == "oversize":
            return httpx.Response(200, content=b"x" * (budget.RESPONSE_LIMIT + 1))
        if kind == "malformed":
            return httpx.Response(200, content=b"not JSON")
        payload = response_payload(
            text="x" * (budget.JUDGMENT_LIMIT + 1) if kind == "long_juror" else "{}"
        )
        if kind == "length":
            payload["choices"][0]["finish_reason"] = "length"
        if kind == "duplicate_outer":
            payload["choices"][0]["message"]["content"] = (
                '{"juror_1_json":"{}","juror_1_json":"{}"}'
            )
        if kind == "duplicate_wire":
            raw = live.encoded(payload)[:-1] + b',"choices":[]}'
            return httpx.Response(200, content=raw)
        return httpx.Response(200, json=payload)

    guard = live.GuardTransport(httpx.MockTransport(handler), guard_root(tmp_path), bounds())
    guard.begin_stage("t059", "juror_1_json")
    with pytest.raises((ValueError, httpx.TransportError)):
        guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=body()))
    assert guard.failed and guard.ledger.calls == 1
    error = (guard.stage_dir / "error.json").read_text()
    assert "synthetic-secret" not in error
    if kind == "oversize":
        assert (guard.stage_dir / "response.raw").stat().st_size == budget.RESPONSE_LIMIT
    if kind == "disconnect":
        assert (guard.stage_dir / "response.raw").read_bytes() == b"partial"
    with pytest.raises(ValueError):
        guard.begin_stage("t059", "juror_2_json")


@pytest.fixture
def owner_stack(monkeypatch):
    require_private_evidence()
    # This boundary stub prevents ALL auth resolution; constructor/route remain real.
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    pytest.importorskip("dspy_lm_auth")
    import importlib
    import socket

    lm_module = importlib.import_module("dspy_lm_auth.lm")

    class FakeStorage:
        def get_api_key(self, provider):
            assert provider == "zai"
            return "synthetic-offline-key"

    monkeypatch.setattr(lm_module, "_coerce_auth_storage", lambda storage: FakeStorage())
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("network forbidden"))
    monkeypatch.setattr(
        socket.socket, "connect_ex", lambda *a, **k: pytest.fail("network forbidden")
    )
    return lm_module


def synthetic_judgment(inputs, field, previous=None):
    contract = json.loads(inputs["judgment_contract_json"])
    sources = json.loads(inputs["evidence_json"])["sources"]
    rows = []
    for key in contract["criteria"]:
        verdict = (
            "fail"
            if key == "final_delivery" and not sources["final"].strip()
            else "insufficient_evidence"
        )
        row = {
            "id": key,
            "verdict": verdict,
            "rationale": "Offline fixture only.",
            "citations": [{"source": "status", "quote": sources["status"]}]
            if verdict == "fail"
            else [],
        }
        if field == "adjudication_json":
            row.update(
                disagreement=False,
                addressed_jurors=[
                    {"juror": j, "verdict": verdict, "assessment": "Offline fixture only."}
                    for j in live.jury.JURORS
                ],
            )
        if previous is not None:
            verdicts = {
                j: next(r["verdict"] for r in record["criteria"] if r["id"] == key)
                for j, record in previous.items()
            }
            row["disagreement"] = len(set(verdicts.values())) > 1
            for addressed in row["addressed_jurors"]:
                addressed["verdict"] = verdicts[addressed["juror"]]
        rows.append(row)
    return json.dumps({"binding": contract["binding"], "criteria": rows})


@pytest.mark.parametrize("prefix", [False, True])
def test_real_lm_injection_all_six_captures(owner_stack, httpx, tmp_path, monkeypatch, prefix):
    if prefix:
        monkeypatch.setattr(live.envelope, "load_seed", live.envelope.RetainedPrefix)
    protocol, prepared, copies = live.preflight()
    assert protocol["billing_basis"] == "operator-confirmed subscription"
    assert protocol["monetary_gate"] is False
    assert len(copies) == 8
    calls = []
    guard = None

    def handler(request):
        calls.append(request)
        capture, field = guard.active
        previous = None
        if field == "adjudication_json":
            previous = {
                j: live.envelope.parsed(tmp_path / f"{capture}--{j}/validated.json")
                for j in live.jury.JURORS
            }
        return httpx.Response(
            200,
            json=response_payload(field, synthetic_judgment(prepared[capture], field, previous)),
        )

    guard = live.GuardTransport(
        httpx.MockTransport(handler), guard_root(tmp_path), protocol["message_bounds"]
    )
    lm = live.make_lm(guard)
    assert isinstance(lm, owner_stack.LM)
    assert lm.supports_response_schema is False
    assert lm.cache is False and lm.num_retries == 0
    assert lm.kwargs["client"].max_retries == 0
    try:
        live.run_captures(prepared, lm, guard)
    finally:
        lm.kwargs["client"].close()
    assert guard.ledger.calls == 24
    assert len(calls) == (18 if prefix else 24)
    assert len(list(tmp_path.glob("*.outputs.json"))) == 6
    assert len(list(tmp_path.glob("*/response.raw"))) == 24
    assert len(list(tmp_path.glob("*/usage.json"))) == 24
    assert len(list(tmp_path.glob("*/validated.json"))) == 24
    assert guard.new_http_attempts == (18 if prefix else 24)
    assert guard.reused_responses == (6 if prefix else 0)
    for request in calls:
        data = json.loads(request.content)
        assert data["store"] is False and data["model"] == "glm-5.3"
        assert data["response_format"] == {"type": "json_object"}
        assert data["max_tokens"] == 131072
    assert len(list(tmp_path.glob("*/attempt.json"))) == 24
    assert not list(tmp_path.rglob("*reservation*"))
    assert set(vars(guard.ledger)) == {"calls", "message_bytes"}
    assert all(
        b"synthetic-offline-key" not in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    )


@pytest.mark.parametrize("failure", ["http", "validation", "adjudication", "timeout", "length"])
def test_real_lm_first_failure_stops_entire_pilot(owner_stack, httpx, tmp_path, failure):
    protocol, prepared, _ = live.preflight()
    calls = []
    guard = None

    def handler(request):
        calls.append(request)
        capture, field = guard.active
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic-secret")
        if failure == "http":
            return httpx.Response(429, content=b"retained failure")
        if failure == "length":
            payload = response_payload(field)
            payload["choices"][0]["finish_reason"] = "length"
            payload["choices"][0]["message"]["content"] = '{"juror_1_json": "unfinished'
            payload["usage"] = {
                "prompt_tokens": 6272,
                "completion_tokens": budget.MAX_TOKENS,
                "completion_tokens_details": {"reasoning_tokens": 7458},
            }
            return httpx.Response(200, json=payload)
        text = synthetic_judgment(prepared[capture], field)
        if failure == "validation" or field == "adjudication_json":
            text = "{}"
        return httpx.Response(200, json=response_payload(field, text))

    guard = live.GuardTransport(
        httpx.MockTransport(handler), guard_root(tmp_path), protocol["message_bounds"]
    )
    lm = live.make_lm(guard)
    try:
        from dspy import LMError

        with pytest.raises((ValueError, LMError)):
            live.run_captures(prepared, lm, guard)
    finally:
        lm.kwargs["client"].close()
    assert len(calls) == (4 if failure == "adjudication" else 1)
    assert guard.failed
    assert not list(tmp_path.glob("*.outputs.json"))
    assert (guard.stage_dir / "error.json").exists()


@pytest.mark.parametrize("size", [-1, True, 864833, 1.5])
def test_invalid_request_capacity(size):
    ledger = budget.AttemptLedger()
    with pytest.raises(ValueError):
        ledger.record(size)
    assert ledger.calls == ledger.message_bytes == 0


@pytest.mark.parametrize("success", [False, True])
def test_execute_freezes_before_auth_and_refuses_replay(
    owner_stack, httpx, tmp_path, monkeypatch, success
):
    monkeypatch.setattr(live, "DEST", tmp_path)
    original = live.make_lm
    calls = []
    active_guard = None

    def make_lm(guard):
        nonlocal active_guard
        active_guard = guard
        assert (tmp_path / "ONE_SHOT").is_file()
        protocol = json.loads((tmp_path / "protocol.json").read_text())
        for name, digest in protocol["input_sha256"].items():
            assert live.jury.sha((tmp_path / "inputs" / name).read_bytes()) == digest
        for name, digest in protocol["original_sha256"].items():
            assert live.jury.sha((ROOT / name).read_bytes()) == digest
        for capture in live.CAPTURES:
            assert (tmp_path / "inputs" / f"{capture}.inputs.json").is_file()
        return original(guard)

    def response(request):
        calls.append(request)
        if success:
            capture, field = active_guard.active
            inputs = json.loads((tmp_path / "inputs" / f"{capture}.inputs.json").read_text())
            return httpx.Response(
                200, json=response_payload(field, synthetic_judgment(inputs, field))
            )
        return httpx.Response(503, content=b"frozen execution failure")

    monkeypatch.setattr(live, "make_lm", make_lm)
    monkeypatch.setattr(httpx, "HTTPTransport", lambda **kw: httpx.MockTransport(response))
    # execute changes process logging/umask intentionally; restore them for tests.
    import logging
    import os

    mask, level = os.umask(0o077), logging.root.manager.disable
    try:
        assert live.main(["--execute"]) == (0 if success else 1)
        frozen = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        assert live.main(["--execute"]) == 1
        assert frozen == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    finally:
        os.umask(mask)
        logging.disable(level)
    assert len(calls) == (24 if success else 1)
    assert (tmp_path / "failed.json").exists() is not success
    if success:
        assert json.loads((tmp_path / "complete.json").read_text()) == {
            "attempts": 24,
            "attempts_basis": "stage_attempts_including_retained_response",
            "stages": 24,
            "new_http_attempts": 24,
            "reused_responses": 0,
            "cumulative_unique_review_responses": 24,
            "message_bytes": active_guard.ledger.message_bytes,
            "action_permission": "not_granted",
        }
        assert not list(tmp_path.rglob("*reservation*"))
    else:
        assert not (tmp_path / "complete.json").exists()


def test_preflight_never_constructs_lm(owner_stack, monkeypatch, capsys):
    monkeypatch.setattr(live, "make_lm", lambda *a: pytest.fail("auth forbidden"))
    monkeypatch.setattr(
        owner_stack, "_coerce_auth_storage", lambda *a: pytest.fail("auth forbidden")
    )
    protocol, prepared, _ = live.preflight()
    assert len(prepared) == 6
    assert sum(len(v) for v in protocol["message_bounds"].values()) == 24
    assert live.main(["--preflight"]) == 0
    assert json.loads(capsys.readouterr().out)["monetary_gate"] is False


def test_guard_stage_order_and_cap(httpx, tmp_path):
    guard = live.GuardTransport(httpx.MockTransport(lambda r: None), guard_root(tmp_path), bounds())
    with pytest.raises(ValueError):
        guard.begin_stage("t060", "juror_1_json")
    guard = live.GuardTransport(httpx.MockTransport(lambda r: None), guard_root(tmp_path), bounds())
    for capture in live.CAPTURES:
        for field in live.jury.OUTPUTS:
            guard.begin_stage(capture, field)
            guard.spent = True
    with pytest.raises(ValueError):
        guard.begin_stage("t059", "juror_1_json")


def test_marker_survives_process_crash(tmp_path):
    import subprocess

    code = (
        "import os,sys;sys.path.insert(0,sys.argv[1]);"
        "import compass_jury_live as live;from pathlib import Path;"
        "ctx=live.one_shot(Path(sys.argv[2]));ctx.__enter__();os._exit(17)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "scripts"), str(tmp_path)], check=False
    )
    assert result.returncode == 17
    with pytest.raises(FileExistsError), live.one_shot(tmp_path):
        pass


def test_stage_callback_runs_once_before_adapter_and_duplicate_rejected(owner_stack, monkeypatch):
    import dspy

    _, prepared, _ = live.preflight()
    inputs = prepared["t059"]
    lm = type("FakeLM", (), {"model": "openai/glm-5.3"})()
    calls = []
    adapter_calls = []
    signature = live.program_module().build_program().juror_1.predict.signature

    class DuplicateProgram:
        def __call__(self, **kw):
            adapter = dspy.settings.adapter
            adapter(lm, {}, signature, [], inputs)
            return adapter(lm, {}, signature, [], inputs)

    monkeypatch.setattr(
        live.jury,
        "load_program",
        lambda: type("Generated", (), {"build_program": staticmethod(DuplicateProgram)})(),
    )

    def response(self, *args):
        assert calls == ["juror_1_json"]
        adapter_calls.append(1)
        return [{"juror_1_json": synthetic_judgment(inputs, "juror_1_json")}]

    monkeypatch.setattr(dspy.JSONAdapter, "__call__", response)
    with pytest.raises(ValueError, match="duplicate"):
        live.jury.evaluate(inputs, lm, stage_callback=calls.append)
    assert len(calls) == len(adapter_calls) == 1


def test_subscription_limits_and_readonly_history(owner_stack, monkeypatch):
    prior = ROOT / ".compass/evaluations/glm53-jury-AK5673"
    assert live.DEST == ROOT / ".compass/evaluations/glm53-jury-AK5673-subscription-v6"
    assert live.PRIOR_ATTEMPT_ROOT == prior
    history = {p: p.read_bytes() for p in prior.rglob("*") if p.is_file()}
    originals = {p: live.jury.sha(p.read_bytes()) for p in live.SOURCE.glob("t*.json")}
    import dspy

    original_format = dspy.JSONAdapter.format
    formatted = []

    def check_format(self, signature, demos, inputs, **kwargs):
        for field in live.jury.JURORS:
            if field in inputs:
                assert inputs[field] == ""  # No fictional worst-case outputs.
        messages = original_format(self, signature, demos, inputs, **kwargs)
        formatted.append((next(iter(signature.output_fields)), len(live.encoded(messages))))
        return messages

    monkeypatch.setattr(dspy.JSONAdapter, "format", check_format)
    protocol, prepared, copies = live.preflight()
    assert budget.MAX_TOKENS == protocol["max_tokens"] == 131072
    assert budget.MODEL_CONTEXT == protocol["model_context"] == 1_000_000
    assert budget.RESPONSE_LIMIT == protocol["response_limit"] == 8_000_000
    assert budget.REQUEST_LIMIT == protocol["request_limit"] == 1_000_000
    assert budget.JUDGMENT_LIMIT == live.jury.LIMIT == protocol["judgment_limit"] == 512_000
    assert budget.MESSAGE_LIMIT == 1_000_000 - 131072 - 4096
    assert protocol["timeout_seconds"] == 3600
    assert protocol["monetary_gate"] is False
    assert protocol["billing_basis"] == "operator-confirmed subscription"
    assert (
        "local" in protocol["limits_source"]
        and "not provider-verified" in protocol["limits_source"]
    )
    assert protocol["prior_attempt_root"] == str(prior.relative_to(ROOT))
    assert protocol["prior_response_sha256"] == (
        "c5d4edaf611b5d693b1afb96158ac7b781d553433b04b9d010098d556c222112"
    )
    assert (
        live.jury.sha(history[prior / "t059--juror_1_json/response.raw"])
        == protocol["prior_response_sha256"]
    )
    assert protocol["original_sha256"] == {
        str(p.relative_to(ROOT)): h for p, h in originals.items()
    }
    for name in ("allowance", "remaining", "prior_reservations", "projected_reservation", "fits"):
        assert name not in protocol
    assert len(formatted) == 24
    for capture, entries in zip(live.CAPTURES, range(0, 24, 4), strict=True):
        for field, size in formatted[entries : entries + 4]:
            expected = size if field in live.jury.JURORS else budget.MESSAGE_LIMIT
            assert protocol["message_bounds"][capture][field] == expected
        assert set(prepared[capture]) == {
            "evidence_json",
            "rubric_json",
            "judgment_contract_json",
            "adjudication_contract_json",
        }
    assert not any("grade" in name or "judge" in name for name in copies)
    assert history == {p: p.read_bytes() for p in prior.rglob("*") if p.is_file()}
    assert originals == {p: live.jury.sha(p.read_bytes()) for p in live.SOURCE.glob("t*.json")}


@pytest.mark.parametrize("over", [False, True])
@pytest.mark.parametrize("char", ["x", "é", "😀"])
def test_actual_message_capacity_boundary(httpx, tmp_path, over, char):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response_payload())

    guard = live.GuardTransport(httpx.MockTransport(handler), guard_root(tmp_path), bounds())
    guard.begin_stage("t059", "juror_1_json")
    messages = [{"role": "user", "content": ""}]
    fill = budget.MESSAGE_LIMIT - len(live.encoded(messages)) + int(over)
    width = len(live.encoded(char)) - 2
    messages[0]["content"] = char * (fill // width) + "x" * (fill % width)
    assert len(live.encoded(messages)) == budget.MESSAGE_LIMIT + int(over)
    raw = json.dumps(live.request_body(messages), ensure_ascii=False).encode()
    assert len(raw) < budget.REQUEST_LIMIT
    request = httpx.Request(
        "POST", live.ENDPOINT, content=raw, headers={"content-type": "application/json"}
    )
    if over:
        with pytest.raises(ValueError, match="context"):
            guard.handle_request(request)
        assert not calls and guard.failed
    else:
        guard.handle_request(request)
        assert len(calls) == guard.ledger.calls == 1
        attempt = json.loads((guard.stage_dir / "attempt.json").read_text())
        assert attempt == {
            "attempt": 1,
            "message_bytes": budget.MESSAGE_LIMIT,
            "total_message_bytes": budget.MESSAGE_LIMIT,
        }


@pytest.mark.parametrize("over", [False, True])
def test_real_lm_large_adjudication_actual_context(owner_stack, httpx, tmp_path, over):
    protocol, prepared, _ = live.preflight()
    calls = []
    guard = None

    def handler(request):
        calls.append(request)
        capture, field = guard.active
        record = json.loads(synthetic_judgment(prepared[capture], field))
        if field in live.jury.JURORS:
            record["criteria"][0]["rationale"] = "x" * (300_000 if over else 200_000)
        return httpx.Response(200, json=response_payload(field, json.dumps(record)))

    guard = live.GuardTransport(
        httpx.MockTransport(handler), guard_root(tmp_path), protocol["message_bounds"]
    )
    lm = live.make_lm(guard)
    try:
        if over:
            from dspy import LMError

            with pytest.raises((ValueError, LMError)):
                live.run_captures(prepared, lm, guard)
            assert len(calls) == guard.ledger.calls == 3 and guard.failed
        else:
            live.run_captures(prepared, lm, guard)
            assert len(calls) == 24
            for request in calls[3::4]:
                data = json.loads(request.content)
                assert live.jury.LIMIT < len(live.encoded(data["messages"])) <= budget.MESSAGE_LIMIT
                assert data["max_tokens"] == 131072
    finally:
        lm.kwargs["client"].close()


@pytest.mark.parametrize("at_wire_limit", [False, True])
def test_full_response_and_escaped_judgment_allowed(httpx, tmp_path, at_wire_limit):
    record = json.loads(synthetic_judgment(fixture_inputs(), "juror_1_json"))
    record["criteria"][0]["rationale"] = "😀" * 100_000
    text = json.dumps(record, ensure_ascii=False)
    assert len(text.encode()) < budget.JUDGMENT_LIMIT
    payload = response_payload(text=text)
    payload["choices"][0]["message"]["reasoning_content"] = "x" * 3_000_000
    raw = live.encoded(payload)
    assert 2_000_000 < len(raw) < budget.RESPONSE_LIMIT
    if at_wire_limit:
        raw += b" " * (budget.RESPONSE_LIMIT - len(raw))
    guard = live.GuardTransport(
        httpx.MockTransport(lambda r: httpx.Response(200, content=raw)),
        guard_root(tmp_path),
        bounds(),
    )
    guard.begin_stage("t059", "juror_1_json")
    guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=body()))
    assert (guard.stage_dir / "response.raw").read_bytes() == raw
    assert (
        json.loads((guard.stage_dir / "usage.json").read_text())["usage"]["completion_tokens"] == 34
    )
