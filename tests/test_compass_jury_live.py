"""Offline custody proofs; optional owner environment exercises the real LM stack."""

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import compass_jury_budget as budget  # noqa: E402
import compass_jury_live as live  # noqa: E402


def test_budget_never_releases_and_blocks():
    ledger = budget.Budget()
    assert ledger.remaining == Decimal("2.135484075")
    cost = budget.reservation(1000)
    assert cost == Decimal("0.0431792")
    for _ in range(24):
        ledger.reserve(1000)
    assert ledger.remaining == Decimal("2.135484075") - cost * 24
    with pytest.raises(ValueError):
        ledger.reserve(1000)
    ledger = budget.Budget()
    for _ in range(8):
        ledger.reserve(160000)
    with pytest.raises(ValueError):
        ledger.reserve(160000)


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
    return {c: {f: budget.REQUEST_LIMIT for f in live.jury.OUTPUTS} for c in live.CAPTURES}


def body():
    return live.request_body([{"role": "user", "content": "synthetic"}])


def response_payload(field="juror_1_json", text="{}"):
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
    guard = live.GuardTransport(httpx.MockTransport(lambda r: calls.append(r)), tmp_path, bounds())
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
        data["max_tokens"] = 8193
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
        assert request.extensions["timeout"]["read"] == 600
        return httpx.Response(200, json=response_payload())

    guard = live.GuardTransport(httpx.MockTransport(handler), tmp_path, bounds())
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

    guard = live.GuardTransport(httpx.MockTransport(handler), tmp_path, bounds())
    guard.begin_stage("t059", "juror_1_json")
    with httpx.Client(transport=guard, follow_redirects=True) as client:
        with pytest.raises(ValueError):
            client.post(live.ENDPOINT, json=body())
    assert len(calls) == 1
    assert (guard.stage_dir / "response.raw").read_bytes() == b"forensic raw failure"
    assert guard.ledger.calls == 1


@pytest.mark.parametrize(
    "kind", ["oversize", "disconnect", "timeout", "malformed", "length", "long_juror"]
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
            text="x" * budget.JUDGMENT_LIMIT if kind == "long_juror" else "{}"
        )
        if kind == "length":
            payload["choices"][0]["finish_reason"] = "length"
        return httpx.Response(200, json=payload)

    guard = live.GuardTransport(httpx.MockTransport(handler), tmp_path, bounds())
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


def synthetic_judgment(inputs, field):
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
        rows.append(row)
    return json.dumps({"binding": contract["binding"], "criteria": rows})


def test_real_lm_injection_all_six_captures(owner_stack, httpx, tmp_path):
    protocol, prepared, copies = live.preflight()
    assert protocol["fits"]
    assert Decimal(protocol["projected_reservation"]) <= budget.ALLOWANCE - budget.PRIOR
    assert len(copies) == 8
    calls = []
    guard = None

    def handler(request):
        calls.append(request)
        capture, field = guard.active
        return httpx.Response(
            200, json=response_payload(field, synthetic_judgment(prepared[capture], field))
        )

    guard = live.GuardTransport(httpx.MockTransport(handler), tmp_path, protocol["message_bounds"])
    lm = live.make_lm(guard)
    assert isinstance(lm, owner_stack.LM)
    assert lm.supports_response_schema is False
    assert lm.cache is False and lm.num_retries == 0
    assert lm.kwargs["client"].max_retries == 0
    try:
        live.run_captures(prepared, lm, guard)
    finally:
        lm.kwargs["client"].close()
    assert len(calls) == guard.ledger.calls == 24
    assert len(list(tmp_path.glob("*.outputs.json"))) == 6
    assert len(list(tmp_path.glob("*/response.raw"))) == 24
    assert len(list(tmp_path.glob("*/usage.json"))) == 24
    for request in calls:
        data = json.loads(request.content)
        assert data["store"] is False and data["model"] == "glm-5.3"
        assert data["response_format"] == {"type": "json_object"}
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
                "completion_tokens": 8192,
                "completion_tokens_details": {"reasoning_tokens": 7458},
            }
            return httpx.Response(200, json=payload)
        text = synthetic_judgment(prepared[capture], field)
        if failure == "validation" or field == "adjudication_json":
            text = "{}"
        return httpx.Response(200, json=response_payload(field, text))

    guard = live.GuardTransport(httpx.MockTransport(handler), tmp_path, protocol["message_bounds"])
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


@pytest.mark.parametrize("size", [-1, True, 160001, 1.5])
def test_invalid_reservation_size(size):
    with pytest.raises(ValueError):
        budget.reservation(size)


def test_execute_freezes_before_auth_and_refuses_replay(owner_stack, httpx, tmp_path, monkeypatch):
    monkeypatch.setattr(live, "DEST", tmp_path)
    original = live.make_lm
    calls = []

    def make_lm(guard):
        assert (tmp_path / "ONE_SHOT").is_file()
        protocol = json.loads((tmp_path / "protocol.json").read_text())
        for name, digest in protocol["input_sha256"].items():
            assert live.jury.sha((tmp_path / "inputs" / name).read_bytes()) == digest
        for capture in live.CAPTURES:
            assert (tmp_path / "inputs" / f"{capture}.inputs.json").is_file()
        return original(guard)

    def failure(request):
        calls.append(request)
        return httpx.Response(503, content=b"frozen execution failure")

    monkeypatch.setattr(live, "make_lm", make_lm)
    monkeypatch.setattr(httpx, "HTTPTransport", lambda **kw: httpx.MockTransport(failure))
    # execute changes process logging/umask intentionally; restore them for tests.
    import logging
    import os

    mask, level = os.umask(0o077), logging.root.manager.disable
    try:
        assert live.main(["--execute"]) == 1
        assert live.main(["--execute"]) == 1
    finally:
        os.umask(mask)
        logging.disable(level)
    assert len(calls) == 1
    assert (tmp_path / "failed.json").exists()
    assert not (tmp_path / "complete.json").exists()


def test_preflight_never_constructs_lm(owner_stack, monkeypatch):
    monkeypatch.setattr(live, "make_lm", lambda *a: pytest.fail("auth forbidden"))
    monkeypatch.setattr(
        owner_stack, "_coerce_auth_storage", lambda *a: pytest.fail("auth forbidden")
    )
    protocol, prepared, _ = live.preflight()
    assert len(prepared) == 6
    assert sum(len(v) for v in protocol["message_bounds"].values()) == 24


def test_guard_stage_order_and_cap(httpx, tmp_path):
    guard = live.GuardTransport(httpx.MockTransport(lambda r: None), tmp_path, bounds())
    with pytest.raises(ValueError):
        guard.begin_stage("t060", "juror_1_json")
    guard = live.GuardTransport(httpx.MockTransport(lambda r: None), tmp_path, bounds())
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
