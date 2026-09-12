"""Lossless outer-envelope reconciliation and a pinned six-response offline v5 prefix.

No auth, provider construction, JSON repair, or substantive judgment rewriting.
Original wire/output evidence is never normalized in place.
"""

from __future__ import annotations

import json
import os

import compass_jury as jury
from compass_jury_budget import JUDGMENT_LIMIT, REQUEST_LIMIT, RESPONSE_LIMIT

SEED_ROOT = jury.ROOT / ".compass/evaluations/glm53-jury-AK5673-subscription-v5"
SEED_STAGES = (
    *(("t059", field) for field in jury.OUTPUTS),
    ("t060", "juror_1_json"),
    ("t060", "juror_2_json"),
)
SEED_RESPONSE_SHA256 = (
    "333ac850b76502007c53c170bad79d70d27690f3bb46b6f8c57929867e3032bd",
    "3eb6f0f920a3c7b688a0ae9616696b3368dde231dd6f7b5d4290ae3528bf2d44",
    "3f0b658949a3d7afac98daa0643dea0f2e902e8e04ecdc3120845982ec450a0e",
    "909b30a44b71aec9f65cb79f9667e554de7b62e715d043b441bc3c6a7d4ef8b9",
    "9f4b6a4d40acaf357d29adda485039fe46bc0067f1c5be403f8e3b8e12f29e7b",
    "efb6ebe8365a8cb96042f15129d15e759c5ad6ef053fc1bdf3859ce201050093",
)
SEED_REQUEST_SHA256 = (
    "d8a49de67d26e7319a1c945b46a510b7e6edf5096739623f60748def5ec79e88",
    "31a1004221108e2f86cd4cf1ad4756f9dfc0cc7886ea3a3e0179efdf95382d0b",
    "199307ceec8021c4a1ceb9b7cacdd32940f18b4f1dfd13e721e9508221893e83",
    "f47d17f6314171c9692fb65a008fd7ebb756c57d2d4974adb59d967a3705b5cd",
    "1ae0d3d7507443c10e619ee056fac19f954cc55f27feee8ce5d398b3e99a76ce",
    "258606e8c2c587c369a35af62addc6ac427e37d9beea5e84ecd56505813b9456",
)
V2_ROOT = ".compass/evaluations/glm53-jury-AK5673-subscription-v2"
V3_ROOT = ".compass/evaluations/glm53-jury-AK5673-subscription-v3"
V4_ROOT = ".compass/evaluations/glm53-jury-AK5673-subscription-v4"
V5_ROOT = ".compass/evaluations/glm53-jury-AK5673-subscription-v5"
ORIGINAL_ROOTS = (V2_ROOT, V3_ROOT, V3_ROOT, V4_ROOT, V5_ROOT, V5_ROOT)
ALIASES = {
    "juror_1_json": "juror_1_",
    "juror_2_json": "juror_2_",
    "juror_3_json": "juror_3_",
    "adjudication_json": "adjudication_",
}


def encoded(value):
    # ASCII-escaped JSON is a conservative bound on UTF-8 message bytes.
    return json.dumps(value, ensure_ascii=True, allow_nan=False).encode()


def durable(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    durable(path, encoded(value) + b"\n")


def read(path, limit=RESPONSE_LIMIT):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("retained byte limit exceeded")
    return raw


def parsed(path, limit=RESPONSE_LIMIT):
    return jury.strict_json(read(path, limit).decode("utf-8"), max_bytes=limit)


class FrozenInputs:
    """Rebuild from frozen source bytes; detect subsequent snapshot/source drift."""

    def __init__(self, root, captures):
        self.root = root / "inputs"
        self.prepared, self.copies = {}, {}
        for name in ("corpus.json", "rubric.json", *(f"{c}.json" for c in captures)):
            self.copies[name] = read(self.root / name, jury.LIMIT)
        for capture in captures:
            inputs = jury.prepare_inputs(
                self.root / "corpus.json", self.root / f"{capture}.json", self.root / "rubric.json"
            )
            if inputs != parsed(self.root / f"{capture}.inputs.json", jury.LIMIT):
                raise ValueError("frozen inputs mismatch")
            self.prepared[capture] = inputs

    def check(self):
        for name, raw in self.copies.items():
            if read(self.root / name, jury.LIMIT) != raw:
                raise ValueError("frozen source changed")
        for capture, inputs in self.prepared.items():
            if parsed(self.root / f"{capture}.inputs.json", jury.LIMIT) != inputs:
                raise ValueError("frozen inputs changed")


class RetainedPrefix:
    """Verify the entire prefix before execution; consume only its exact six ordinals."""

    def __init__(self):
        self.consumed, self.failed, self.verified = 0, False, False
        self.records, self.receipts = [], []
        for index, active in enumerate(SEED_STAGES):
            stage = SEED_ROOT / "--".join(active)
            origin = "retained_v4_response" if index < 4 else "live_http"
            if parsed(stage / "stage.json") != {
                "capture": active[0],
                "field": active[1],
                "origin": origin,
            }:
                raise ValueError("retained seed stage mismatch")
            if parsed(stage / "http.json") != {"status": 200}:
                raise ValueError("retained seed HTTP status mismatch")
            raw, request_raw = (
                read(stage / "response.raw"),
                read(stage / "request.body.json", REQUEST_LIMIT),
            )
            if jury.sha(raw) != SEED_RESPONSE_SHA256[index]:
                raise ValueError("retained seed response hash mismatch")
            if jury.sha(request_raw) != SEED_REQUEST_SHA256[index]:
                raise ValueError("retained seed request hash mismatch")
            value = jury.strict_json(raw.decode("utf-8"), max_bytes=RESPONSE_LIMIT)
            choices = value["choices"]
            if len(choices) != 1 or choices[0]["finish_reason"] != "stop":
                raise ValueError("incomplete retained seed")
            content = choices[0]["message"]["content"]
            if content.encode("utf-8") != read(stage / "output.txt"):
                raise ValueError("retained seed output mismatch")
            observed, inner, representation = extract_inner(content, active[1])
            original = jury.ROOT / ORIGINAL_ROOTS[index] / "--".join(active)
            if (
                read(original / "response.raw") != raw
                or read(original / "request.body.json", REQUEST_LIMIT) != request_raw
                or parsed(original / "http.json") != {"status": 200}
            ):
                raise ValueError("retained seed original source mismatch")
            self.records.append(
                {
                    "raw": raw,
                    "inner": inner,
                    "body": jury.strict_json(request_raw.decode("utf-8"), max_bytes=REQUEST_LIMIT),
                }
            )
            self.receipts.append(
                {
                    "capture": active[0],
                    "field": active[1],
                    "source_origin": origin,
                    "request_sha256": SEED_REQUEST_SHA256[index],
                    "response_sha256": SEED_RESPONSE_SHA256[index],
                    **reconciliation_receipt(observed, active[1], inner, representation),
                    "original_response_root": ORIGINAL_ROOTS[index],
                    "original_origin": "live_http",
                }
            )

    def verify_inputs(self, prepared, copies):
        protocol = parsed(SEED_ROOT / "protocol.json")
        prior_prefix = [
            {**r, "source_origin": "retained_v3_response" if i < 3 else "live_http"}
            for i, r in enumerate(self.receipts[:4])
        ]
        if protocol["seed_root"] != V4_ROOT or protocol["retained_prefix"] != prior_prefix:
            raise ValueError("retained seed lineage mismatch")
        if {k: jury.sha(v) for k, v in copies.items()} != protocol["input_sha256"]:
            raise ValueError("retained seed inputs mismatch")
        for name, raw in copies.items():
            if read(SEED_ROOT / "inputs" / name, jury.LIMIT) != raw:
                raise ValueError("retained seed source mismatch")
        for capture, inputs in prepared.items():
            if parsed(SEED_ROOT / "inputs" / f"{capture}.inputs.json", jury.LIMIT) != inputs:
                raise ValueError("retained seed prepared inputs mismatch")
        for path in (*jury.PROGRAM.glob("*.py"), jury.PROGRAM / "generation.json"):
            if (
                jury.sha(path.read_bytes())
                != protocol["code_sha256"][str(path.relative_to(jury.ROOT))]
            ):
                raise ValueError("retained seed generated graph mismatch")

        previous, previous_capture = {}, None
        for active, record in zip(SEED_STAGES, self.records, strict=True):
            if active[0] != previous_capture:
                previous, previous_capture = {}, active[0]
            judgment = jury.validate_judgment(
                record["inner"],
                prepared[active[0]],
                previous if active[1] == "adjudication_json" else None,
            )
            if active[1] in jury.JURORS:
                previous[active[1]] = judgment
        self.verified = True

    def response(self, active, index, body, request):
        import httpx

        if (
            self.failed
            or not self.verified
            or self.consumed >= len(SEED_STAGES)
            or index != self.consumed + 1
            or active != SEED_STAGES[self.consumed]
        ):
            self.failed = True
            raise ValueError("retained seed already consumed or wrong stage")
        record = self.records[self.consumed]
        self.consumed += 1  # A mismatch cannot be retried or fall through to HTTP.
        if jury.canonical(body) != jury.canonical(record["body"]):
            self.failed = True
            raise ValueError("retained seed request mismatch")
        return httpx.Response(200, content=record["raw"], request=request)


def load_seed():
    """Mandatory production prefix; narrow monkeypatch seam for all-live offline tests."""
    return RetainedPrefix()


def extract_inner(content, expected):
    outer = jury.strict_json(content, max_bytes=RESPONSE_LIMIT)
    if expected not in ALIASES or not isinstance(outer, dict) or len(outer) != 1:
        raise ValueError("output field mismatch")
    (observed,) = outer
    inner = outer[observed]
    if observed not in (expected, ALIASES[expected]) or not isinstance(inner, (str, dict)):
        raise ValueError("output field mismatch")
    representation = "json_string" if isinstance(inner, str) else "json_object"
    if representation == "json_object":
        inner = jury.canonical(inner)
    if len(inner.encode("utf-8")) > JUDGMENT_LIMIT:
        raise ValueError("judgment output byte limit exceeded")
    if not isinstance(jury.strict_json(inner), dict):
        raise ValueError("judgment must be a JSON object")
    return observed, inner, representation


def reconciliation_receipt(observed, expected, inner, representation):
    return {
        "input_representation": representation,
        "observed_key": observed,
        "expected_key": expected,
        "serialized_inner_sha256": jury.sha(inner.encode("utf-8")),
        "semantic_sha256": jury.sha(jury.canonical(jury.strict_json(inner)).encode("utf-8")),
        "reconciled": observed != expected or representation == "json_object",
        "inner_string_unchanged": representation == "json_string",
        "decoded_judgment_unchanged": True,
    }


def reconcile(content, active, inputs, root, save_record):
    capture, expected = active
    observed, inner, representation = extract_inner(content, expected)
    inputs.check()
    previous = None
    if expected == "adjudication_json":
        previous = {
            field: parsed(root / f"{capture}--{field}" / "validated.json") for field in jury.JURORS
        }
    validated = jury.validate_judgment(inner, inputs.prepared[capture], previous)
    stage = root / "--".join(active)
    save_record(stage / "validated.json", validated)
    receipt = reconciliation_receipt(observed, expected, inner, representation)
    save_record(stage / "envelope.json", receipt)
    return jury.canonical({expected: inner}) if receipt["reconciled"] else content


def capture_response(guard, response, request):
    import httpx

    raw = bytearray()
    try:
        save(guard.stage_dir / "http.json", {"status": response.status_code})
        chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
        for chunk in chunks:
            remaining = RESPONSE_LIMIT - len(raw)
            raw.extend(chunk[:remaining])
            if len(chunk) > remaining:
                raise ValueError("response byte limit exceeded; retained prefix only")
    finally:
        durable(guard.stage_dir / "response.raw", bytes(raw))
        response.close()
    if not 200 <= response.status_code < 300:
        raise ValueError("HTTP failure; no redirects/retries")
    if response.headers.get("content-encoding", "identity") != "identity":
        raise ValueError("encoded response rejected")
    # Read up to the HTTP cap, separately from the smaller judgment-input cap.
    value = jury.strict_json(raw.decode("utf-8"), max_bytes=RESPONSE_LIMIT)
    save(
        guard.stage_dir / "usage.json",
        {
            "usage": value.get("usage"),
            "reported_model": value.get("model"),
            "provider_identity_authenticated": False,
        },
    )
    choices = value["choices"]
    if len(choices) != 1 or choices[0]["finish_reason"] != "stop":
        raise ValueError("incomplete response")
    content = choices[0]["message"]["content"]
    durable(guard.stage_dir / "output.txt", content.encode("utf-8"))
    reconciled = reconcile(content, guard.active, guard.inputs, guard.root, save)
    if reconciled != content:
        choices[0]["message"]["content"] = reconciled
        returned_raw = encoded(value)
    else:
        returned_raw = bytes(raw)
    return httpx.Response(
        response.status_code,
        content=returned_raw,
        request=request,
        headers={"content-type": "application/json"},
    )
