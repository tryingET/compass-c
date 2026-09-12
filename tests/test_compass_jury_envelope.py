"""Offline proofs of lossless envelopes and the mandatory, non-resampled v5 prefix."""

import json
import shutil

import pytest
import test_compass_jury_live as fixtures
from test_compass_jury_live import (
    body,
    bounds,
    fixture_inputs,
    guard_root,
    live,
    response_payload,
    synthetic_judgment,
)

httpx = fixtures.httpx
owner_stack = fixtures.owner_stack
envelope = live.envelope


@pytest.fixture(autouse=True)
def private_evidence_only():
    fixtures.require_private_evidence()


def snapshot(root):
    return {
        str(p.relative_to(root)): live.jury.sha(p.read_bytes())
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def prefix_parser():
    pytest.importorskip("markdown_it")


def test_production_prefix_six_real_stages_then_one_mock(
    owner_stack, prefix_parser, httpx, tmp_path, monkeypatch
):
    from importlib.metadata import version

    histories = {root: snapshot(live.ROOT / root) for root in envelope.ORIGINAL_ROOTS}
    protocol, prepared, _ = live.preflight()
    assert protocol["planned_new_http_attempts"] == 18
    assert protocol["planned_reused_responses"] == 6
    assert protocol["planned_cumulative_unique_review_responses"] == 24
    assert protocol["citation_matching"] == live.jury.CITATION_MATCHING
    assert protocol["representation_parser"] == {
        "package": "markdown-it-py",
        "version": version("markdown-it-py"),
        "preset": "commonmark",
    }
    calls = []

    def seventh_only(request):
        assert guard.active == ("t060", "juror_3_json")
        assert guard.reused_responses == 6 and guard.ledger.calls == 7
        calls.append(request)
        return httpx.Response(
            200,
            json=response_payload("juror_3_", synthetic_judgment(prepared["t060"], "juror_3_json")),
        )

    guard = live.GuardTransport(
        httpx.MockTransport(seventh_only), guard_root(tmp_path), protocol["message_bounds"]
    )
    seed = guard.seed
    assert seed.verified and seed.consumed == 0
    assert protocol["retained_prefix"] == seed.receipts
    assert [r["source_origin"] for r in seed.receipts] == [
        *(["retained_v4_response"] * 4),
        "live_http",
        "live_http",
    ]
    monkeypatch.setattr(live.jury, "load_program", live.program_module)
    lm = live.make_lm(guard)  # Auth storage is synthetic; owner_stack forbids sockets.

    class ProofComplete(Exception):
        pass

    def second_capture_stage(field):
        if field == "adjudication_json":
            raise ProofComplete  # End this bounded proof before an eighth stage or dispatch.
        guard.begin_stage("t060", field)

    try:
        result = live.jury.evaluate(
            prepared["t059"], lm, stage_callback=lambda field: guard.begin_stage("t059", field)
        )
        assert not calls and guard.new_http_attempts == 0
        with pytest.raises(ProofComplete):
            live.jury.evaluate(prepared["t060"], lm, stage_callback=second_capture_stage)
        for index, (capture, field) in enumerate(envelope.SEED_STAGES):
            stage = tmp_path / f"{capture}--{field}"
            record = seed.records[index]
            if capture == "t059":
                assert result["raw_outputs"][field] == record["inner"]
            assert envelope.parsed(stage / "request.body.json") == record["body"]
            assert (stage / "response.raw").read_bytes() == record["raw"]
            assert (stage / "output.txt").read_bytes() == (
                envelope.SEED_ROOT / f"{capture}--{field}" / "output.txt"
            ).read_bytes()
            validated = envelope.parsed(stage / "validated.json")
            assert len(validated["criteria"]) == 6
            verdicts = [row["verdict"] for row in validated["criteria"]]
            assert verdicts.count("pass") == (5 if capture == "t059" else 4)
            assert verdicts.count("insufficient_evidence") == (1 if capture == "t059" else 2)
            previous = {j: result["judgments"][j] for j in live.jury.JURORS} if index == 3 else None
            assert validated == live.jury.validate_judgment(
                record["inner"], prepared[capture], previous
            )
            receipt = envelope.parsed(stage / "envelope.json")
            assert receipt["serialized_inner_sha256"] == live.jury.sha(
                record["inner"].encode("utf-8")
            )
            assert receipt["inner_string_unchanged"] is (index != 3)
            assert receipt["decoded_judgment_unchanged"] is True
            assert receipt["input_representation"] == (
                "json_object" if index == 3 else "json_string"
            )
            assert receipt["semantic_sha256"] == live.jury.sha(
                live.jury.canonical(validated).encode("utf-8")
            )
            assert envelope.parsed(stage / "stage.json")["origin"] == "retained_v5_response"
        assert len(calls) == guard.new_http_attempts == 1
        assert guard.reused_responses == seed.consumed == 6 and guard.ledger.calls == 7
        assert len(list(tmp_path.glob("*/validated.json"))) == 7
        with pytest.raises(ValueError, match="consumed or wrong stage"):
            seed.response(envelope.SEED_STAGES[0], 1, seed.records[0]["body"], calls[0])
        with pytest.raises(ValueError, match="out-of-order"):
            guard.begin_stage("t059", "juror_1_json")
        assert len(calls) == 1
    finally:
        lm.kwargs["client"].close()
    assert all(snapshot(live.ROOT / root) == before for root, before in histories.items())


@pytest.mark.parametrize("mutation", ["request", "consumed", "stage", "frozen", "source"])
@pytest.mark.usefixtures("prefix_parser")
def test_seed_fail_closed_before_inner_transport(httpx, tmp_path, mutation):
    calls = []
    guard = live.GuardTransport(
        httpx.MockTransport(lambda r: calls.append(r)), guard_root(tmp_path), bounds()
    )
    request_body = json.loads(json.dumps(guard.seed.records[0]["body"]))
    if mutation == "stage":
        with pytest.raises(ValueError, match="out-of-order"):
            guard.begin_stage("t059", "juror_2_json")
    else:
        guard.begin_stage(*envelope.SEED_STAGES[0])
        if mutation == "request":
            request_body["messages"][1]["content"] = "changed input"
        elif mutation == "consumed":
            guard.seed.consumed = 6
        elif mutation == "frozen":
            (tmp_path / "inputs/t059.inputs.json").write_text("{}")
        else:
            with (tmp_path / "inputs/t059.json").open("ab") as stream:
                stream.write(b" ")
        with pytest.raises(ValueError):
            guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=request_body))
        with pytest.raises(ValueError):
            guard.handle_request(
                httpx.Request("POST", live.ENDPOINT, json=guard.seed.records[0]["body"])
            )
    assert guard.failed and not calls
    assert guard.new_http_attempts == guard.reused_responses == 0
    assert not list(tmp_path.glob("*/validated.json"))


@pytest.mark.parametrize("ordinal", range(6))
@pytest.mark.parametrize(
    "mutation", ["hash", "request_hash", "missing", "http", "stage", "output", "inputs", "prepared"]
)
@pytest.mark.usefixtures("prefix_parser")
def test_retained_source_mismatch_blocks_constructor(
    httpx, tmp_path, monkeypatch, mutation, ordinal
):
    destination = tmp_path / "new"
    destination.mkdir()
    prepared_root = guard_root(destination)
    root = tmp_path / "retained"
    shutil.copytree(envelope.SEED_ROOT, root)
    stage = root / "--".join(envelope.SEED_STAGES[ordinal])
    target, raw = {
        "hash": (stage / "response.raw", b"{}"),
        "request_hash": (stage / "request.body.json", b"{}"),
        "missing": (stage / "response.raw", b"{}"),
        "http": (stage / "http.json", b'{"status":201}'),
        "stage": (stage / "stage.json", b'{"capture":"t060","field":"juror_1_json"}'),
        "output": (stage / "output.txt", b"{}"),
        "inputs": (root / "inputs/t060.json", b"{}"),
        "prepared": (root / "inputs/t060.inputs.json", b"{}"),
    }[mutation]
    target.write_bytes(raw)
    if mutation == "missing":
        target.unlink()
    monkeypatch.setattr(envelope, "SEED_ROOT", root)
    with pytest.raises((ValueError, FileNotFoundError)):
        live.GuardTransport(
            httpx.MockTransport(lambda r: pytest.fail("HTTP forbidden")),
            prepared_root,
            bounds(),
        )


@pytest.mark.parametrize(
    "active,index",
    [
        (("t059", "juror_2_json"), 1),
        (("t060", "juror_1_json"), 1),
        (("t059", "adjudication_json"), 4),
        (envelope.SEED_STAGES[0], 2),
    ],
)
@pytest.mark.usefixtures("prefix_parser")
def test_seed_cannot_be_used_under_wrong_identity(httpx, tmp_path, active, index):
    seed = envelope.load_seed()
    inputs = envelope.FrozenInputs(guard_root(tmp_path), live.CAPTURES)
    seed.verify_inputs(inputs.prepared, inputs.copies)
    with pytest.raises(ValueError, match="wrong stage"):
        seed.response(active, index, seed.records[0]["body"], httpx.Request("POST", live.ENDPOINT))


@pytest.fixture
def all_live(monkeypatch):
    monkeypatch.setattr(envelope, "load_seed", lambda: None)


@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("object_value", [False, True])
def test_all_four_envelopes_validate_before_lossless_rename(
    all_live, httpx, tmp_path, alias, object_value
):
    inputs = fixture_inputs()
    calls, original, inner = [], {}, {}

    def response(request):
        capture, field = guard.active
        text = " \n" + synthetic_judgment(inputs, field) + "\n "
        value = json.loads(text) if object_value else text
        inner[field] = live.jury.canonical(value) if object_value else text
        payload = response_payload(envelope.ALIASES[field] if alias else field, value)
        raw = live.encoded(payload) + b" \n"
        original[field] = raw
        calls.append(request)
        return httpx.Response(200, content=raw)

    guard = live.GuardTransport(httpx.MockTransport(response), guard_root(tmp_path), bounds())
    for field in live.jury.OUTPUTS:
        guard.begin_stage("t059", field)
        returned = guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=body()))
        content = returned.json()["choices"][0]["message"]["content"]
        assert live.jury.strict_json(content) == {field: inner[field]}
        assert (guard.stage_dir / "response.raw").read_bytes() == original[field]
        original_content = json.loads(original[field])["choices"][0]["message"]["content"]
        assert (guard.stage_dir / "output.txt").read_bytes() == original_content.encode("utf-8")
        if not alias and not object_value:
            assert returned.content == original[field]
        receipt = envelope.parsed(guard.stage_dir / "envelope.json")
        assert receipt["reconciled"] is (alias or object_value)
        assert receipt["inner_string_unchanged"] is (not object_value)
        assert receipt["decoded_judgment_unchanged"] is True
        assert receipt["input_representation"] == ("json_object" if object_value else "json_string")
        assert receipt["semantic_sha256"] == live.jury.sha(
            live.jury.canonical(json.loads(inner[field])).encode("utf-8")
        )
        assert receipt["serialized_inner_sha256"] == live.jury.sha(inner[field].encode("utf-8"))
        assert envelope.parsed(guard.stage_dir / "validated.json") == json.loads(inner[field])
    assert len(calls) == 4


@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "citation",
        "binding",
        "duplicate_inner",
        "invalid_json",
        "duplicate_outer",
        "unknown_alias",
        "wrong_juror",
        "ambiguous",
        "array_value",
        "scalar_value",
        "null_value",
        "bool_value",
        "string_array",
        "string_scalar",
        "nonobject",
        "length",
    ],
)
def test_invalid_output_never_normalized(all_live, httpx, tmp_path, alias, mutation):
    field = "juror_1_json"
    key = envelope.ALIASES[field] if alias else field
    value = json.loads(synthetic_judgment(fixture_inputs(), field))
    if mutation == "schema":
        value["criteria"][0]["extra"] = True
    elif mutation == "citation":
        value["criteria"][0]["citations"] = [{"source": "final", "quote": "invented-citation-foo"}]
    elif mutation == "binding":
        value["binding"]["source_sha256"] = "0" * 64
    text = json.dumps(value)
    if mutation == "invalid_json":
        text = text[:-1]
    elif mutation == "duplicate_inner":
        text = text[:-1] + ',"criteria":[]}'
    outer = {key: text}
    if mutation == "unknown_alias":
        outer = {"juror_1": text}
    elif mutation == "wrong_juror":
        outer = {"juror_2_": text}
    elif mutation == "ambiguous":
        outer = {field: text, envelope.ALIASES[field]: text}
    elif mutation in (
        "array_value",
        "scalar_value",
        "null_value",
        "bool_value",
        "string_array",
        "string_scalar",
    ):
        outer = {
            key: {
                "array_value": [value],
                "scalar_value": 42,
                "null_value": None,
                "bool_value": True,
                "string_array": "[]",
                "string_scalar": "42",
            }[mutation]
        }
    elif mutation == "nonobject":
        outer = [text]
    payload = response_payload()
    content = json.dumps(outer)
    if mutation == "duplicate_outer":
        content = content[:-1] + f',"{key}":"{{}}"}}'
    payload["choices"][0]["message"]["content"] = content
    if mutation == "length":
        payload["choices"][0]["finish_reason"] = "length"
    raw, calls = live.encoded(payload), []

    def response(request):
        calls.append(request)
        return httpx.Response(200, content=raw)

    guard = live.GuardTransport(httpx.MockTransport(response), guard_root(tmp_path), bounds())
    guard.begin_stage("t059", field)
    with pytest.raises(ValueError):
        guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=body()))
    assert (guard.stage_dir / "response.raw").read_bytes() == raw
    if mutation != "length":
        assert (guard.stage_dir / "output.txt").read_bytes() == content.encode("utf-8")
    assert not (guard.stage_dir / "validated.json").exists()
    assert not (guard.stage_dir / "envelope.json").exists()
    with pytest.raises(ValueError):
        guard.begin_stage("t059", "juror_2_json")
    assert len(calls) == 1 and guard.failed


@pytest.mark.parametrize("correct", [False, True])
def test_adjudication_uses_actual_saved_jurors(all_live, httpx, tmp_path, correct):
    inputs, previous = fixture_inputs(), {}

    def response(request):
        _, field = guard.active
        record = json.loads(synthetic_judgment(inputs, field))
        if field == "juror_2_json":
            record["criteria"][0].update(
                verdict="fail",
                citations=[
                    {
                        "source": "status",
                        "quote": json.loads(inputs["evidence_json"])["sources"]["status"],
                    }
                ],
            )
        if field in live.jury.JURORS:
            previous[field] = record
        elif correct:
            record["criteria"][0]["disagreement"] = True
            record["criteria"][0]["addressed_jurors"][1]["verdict"] = "fail"
        return httpx.Response(
            200, json=response_payload(envelope.ALIASES[field], json.dumps(record))
        )

    guard = live.GuardTransport(httpx.MockTransport(response), guard_root(tmp_path), bounds())
    for field in live.jury.JURORS:
        guard.begin_stage("t059", field)
        guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=body()))
        assert envelope.parsed(guard.stage_dir / "validated.json") == previous[field]
    guard.begin_stage("t059", "adjudication_json")
    request = httpx.Request("POST", live.ENDPOINT, json=body())
    if correct:
        returned = guard.handle_request(request)
        text = json.loads(returned.json()["choices"][0]["message"]["content"])["adjudication_json"]
        assert live.jury.validate_judgment(text, inputs, previous)["criteria"][0]["disagreement"]
    else:
        with pytest.raises(ValueError, match="disagreement"):
            guard.handle_request(request)
        assert not (guard.stage_dir / "envelope.json").exists()
    assert len(list(tmp_path.glob("*/validated.json"))) == (4 if correct else 3)


@pytest.mark.parametrize("ordinal", range(6))
@pytest.mark.usefixtures("prefix_parser")
def test_each_prefix_request_must_match_before_any_http(httpx, tmp_path, ordinal):
    calls = []
    guard = live.GuardTransport(
        httpx.MockTransport(lambda r: calls.append(r)), guard_root(tmp_path), bounds()
    )
    for index in range(ordinal + 1):
        guard.begin_stage(*envelope.SEED_STAGES[index])
        request_body = json.loads(json.dumps(guard.seed.records[index]["body"]))
        if index == ordinal:
            request_body["messages"][1]["content"] = "wrong request"
            with pytest.raises(ValueError, match="request mismatch"):
                guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=request_body))
        else:
            guard.handle_request(httpx.Request("POST", live.ENDPOINT, json=request_body))
    assert not calls and guard.failed and guard.seed.failed
    assert guard.reused_responses == ordinal and guard.new_http_attempts == 0
    assert len(list(tmp_path.glob("*/validated.json"))) == ordinal
    with pytest.raises(ValueError):
        guard.handle_request(
            httpx.Request("POST", live.ENDPOINT, json=guard.seed.records[ordinal]["body"])
        )


@pytest.mark.parametrize("ordinal", range(6))
@pytest.mark.usefixtures("prefix_parser")
def test_all_prefix_inner_judgments_checked_before_consumption(
    httpx, tmp_path, monkeypatch, ordinal
):
    seed = envelope.load_seed()
    seed.records[ordinal]["inner"] = "{}"  # Test validation independent of wire/hash pinning.
    monkeypatch.setattr(envelope, "load_seed", lambda: seed)
    with pytest.raises(ValueError, match="binding/schema"):
        live.GuardTransport(
            httpx.MockTransport(lambda r: pytest.fail("HTTP forbidden")),
            guard_root(tmp_path),
            bounds(),
        )
    assert not seed.verified and seed.consumed == 0


@pytest.mark.parametrize(
    "mutation", [None, "schema", "citation", "duplicate", "missing", "unknown", "verdict"]
)
def test_object_adjudication_preserves_values_and_stops_invalid_substance(
    all_live, httpx, tmp_path, mutation
):
    inputs, originals = fixture_inputs(), {}

    def response(request):
        _, field = guard.active
        value = json.loads(synthetic_judgment(inputs, field))
        if field == "adjudication_json":
            for row in value["criteria"]:
                for addressed in row["addressed_jurors"]:
                    addressed["juror"] = envelope.ALIASES[addressed["juror"]]
            first = value["criteria"][0]
            if mutation == "schema":
                first["extra"] = True
            elif mutation == "citation":
                first["citations"] = [
                    {"source": "final", "quote": "unsupported-quote-not-in-evidence"}
                ]
            elif mutation == "duplicate":
                first["addressed_jurors"][1]["juror"] = "juror_1_json"
            elif mutation == "missing":
                first["addressed_jurors"].pop()
            elif mutation == "unknown":
                first["addressed_jurors"][0]["juror"] = "juror_1"
            elif mutation == "verdict":
                first["addressed_jurors"][0]["verdict"] = "pass"
        raw = live.encoded(response_payload(envelope.ALIASES[field], value))
        originals[field] = (raw, value)
        return httpx.Response(200, content=raw)

    guard = live.GuardTransport(httpx.MockTransport(response), guard_root(tmp_path), bounds())
    for field in live.jury.OUTPUTS:
        guard.begin_stage("t059", field)
        request = httpx.Request("POST", live.ENDPOINT, json=body())
        if field == "adjudication_json" and mutation is not None:
            with pytest.raises(ValueError):
                guard.handle_request(request)
            assert guard.failed
            assert not (guard.stage_dir / "validated.json").exists()
            assert not (guard.stage_dir / "envelope.json").exists()
        else:
            returned = guard.handle_request(request)
            text = json.loads(returned.json()["choices"][0]["message"]["content"])[field]
            assert json.loads(text) == originals[field][1]
            receipt = envelope.parsed(guard.stage_dir / "envelope.json")
            assert receipt["input_representation"] == "json_object"
            assert receipt["inner_string_unchanged"] is False
            assert receipt["decoded_judgment_unchanged"] is True
        raw, _ = originals[field]
        assert (guard.stage_dir / "response.raw").read_bytes() == raw
        assert (guard.stage_dir / "output.txt").read_bytes() == json.loads(raw)["choices"][0][
            "message"
        ]["content"].encode("utf-8")
    assert len(list(tmp_path.glob("*/validated.json"))) == (4 if mutation is None else 3)


@pytest.mark.parametrize("index", [0, 1, 2, 3])
@pytest.mark.parametrize("artifact", ["response.raw", "request.body.json"])
@pytest.mark.usefixtures("prefix_parser")
def test_prefix_binds_original_response_and_request_bytes(
    httpx, tmp_path, monkeypatch, index, artifact
):
    original = (
        live.ROOT
        / envelope.ORIGINAL_ROOTS[index]
        / "--".join(envelope.SEED_STAGES[index])
        / artifact
    )
    read = envelope.read

    def changed(path, *args):
        raw = read(path, *args)
        return raw + b" " if path == original else raw

    monkeypatch.setattr(envelope, "read", changed)
    with pytest.raises(ValueError, match="original source mismatch"):
        live.GuardTransport(
            httpx.MockTransport(lambda r: pytest.fail("HTTP forbidden")),
            guard_root(tmp_path),
            bounds(),
        )
