"""Fixed, non-resumable AK5673 pilot. --preflight is offline; only --execute calls LM.

Run with the maintained dspy-lm-auth owner interpreter. No auth implementation,
CLI limit/root overrides, automatic replay, or backend-capacity claims.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import logging
import os
import sys
from pathlib import Path

import compass_jury as jury
import compass_jury_envelope as envelope
from compass_jury_budget import (
    JUDGMENT_LIMIT,
    MAX_CALLS,
    MAX_TOKENS,
    MESSAGE_LIMIT,
    MODEL_CONTEXT,
    REQUEST_LIMIT,
    RESPONSE_LIMIT,
    AttemptLedger,
    validate_capacity,
)
from compass_jury_envelope import durable, encoded, save, sync_directory

ROOT = jury.ROOT
SOURCE = ROOT / ".compass/evaluations/2026-09-11-glm-v06"
DEST = ROOT / ".compass/evaluations/glm53-jury-AK5673-subscription-v6"
PRIOR_ATTEMPT_ROOT = ROOT / ".compass/evaluations/glm53-jury-AK5673"
PRIOR_RESPONSE_SHA256 = "c5d4edaf611b5d693b1afb96158ac7b781d553433b04b9d010098d556c222112"
CAPTURES = ("t059", "t060", "t075", "t076", "t089", "t090")
RUBRIC = ROOT / "evals/dspx-jury/rubric.json"
BASE = "https://api.z.ai/api/coding/paas/v4"
ENDPOINT = BASE + "/chat/completions"
TIMEOUT = 3600
_program = None
_program_hash = None
_original_load = jury.load_program


@contextlib.contextmanager
def one_shot(root):
    """Marker is never removed, including on preflight failure or interruption."""
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.resolve() != root.absolute():
        raise ValueError("symlink root")
    parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    fd = os.open(root / "LOCK", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        durable(root / "ONE_SHOT", b"AK5673: no resume or replay\n")
        yield
    finally:
        os.close(fd)


def program_module():
    """Cache only our verified generated module; never clear foreign sys.modules."""
    global _program, _program_hash
    receipt = json.loads((jury.PROGRAM / "generation.json").read_text())
    for name, expected in receipt["source_sha256"].items():
        if jury.sha((jury.PROGRAM / name).read_bytes()) != expected:
            raise ValueError("generated source drift")
    fingerprint = jury.sha(encoded(receipt))
    if _program is None:
        _program = _original_load()
        _program_hash = fingerprint
    elif fingerprint != _program_hash:
        raise ValueError("cached generation receipt drift")
    return _program


def request_body(messages):
    return {
        "model": "glm-5.3",
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
        "n": 1,
        "store": False,
        "stream": False,
        "response_format": {"type": "json_object"},
    }


def preflight():
    """Format all 24 prompts without constructing an LM or resolving auth."""
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    import dspy

    program = program_module().build_program()
    adapter = dspy.JSONAdapter(use_native_function_calling=False)
    prepared, copies, bounds = {}, {}, {}
    for path in (SOURCE / "corpus.json", RUBRIC, *(SOURCE / f"{c}.json" for c in CAPTURES)):
        copies[path.name] = jury.read_json(path)[0]
    for capture in CAPTURES:
        inputs = jury.prepare_inputs(SOURCE / "corpus.json", SOURCE / f"{capture}.json", RUBRIC)
        bindings = jury.strict_json(inputs["judgment_contract_json"])["binding"]
        for key, name in (
            ("source_sha256", f"{capture}.json"),
            ("corpus_sha256", "corpus.json"),
            ("rubric_file_sha256", "rubric.json"),
        ):
            if bindings[key] != jury.sha(copies[name]):
                raise ValueError("input changed during preflight")
        prepared[capture] = inputs
        bounds[capture] = {}
        for field, node in zip(
            jury.OUTPUTS, ("juror_1", "juror_2", "juror_3", "adjudicator"), strict=True
        ):
            signature = getattr(program, node).predict.signature
            values = {**inputs, **{j: "" for j in jury.JURORS}}
            messages = adapter.format(signature, [], {k: values[k] for k in signature.input_fields})
            size = len(encoded(messages))
            validate_capacity(size)
            if len(encoded(request_body(messages))) > REQUEST_LIMIT:
                raise ValueError("projected request byte bound")
            bounds[capture][field] = size if field in jury.JURORS else MESSAGE_LIMIT
    prior_raw = PRIOR_ATTEMPT_ROOT / "t059--juror_1_json/response.raw"
    if jury.sha(prior_raw.read_bytes()) != PRIOR_RESPONSE_SHA256:
        raise ValueError("prior response hash mismatch")
    seed = envelope.load_seed()
    if seed is not None:
        seed.verify_inputs(prepared, copies)
    protocol = {
        "task": "AK5673",
        "captures": CAPTURES,
        "stages": jury.OUTPUTS,
        "model": "zai/glm-5.3",
        "endpoint": ENDPOINT,
        "temperature": 0.7,
        "max_tokens": MAX_TOKENS,
        "model_context": MODEL_CONTEXT,
        "max_attempts": MAX_CALLS,
        "attempts_basis": "stage_attempts_including_retained_response",
        "planned_new_http_attempts": MAX_CALLS - len(envelope.SEED_STAGES),
        "planned_reused_responses": len(envelope.SEED_STAGES),
        "planned_cumulative_unique_review_responses": MAX_CALLS,
        "unique_response_basis": "completed responses only; v1 truncated response excluded",
        "citation_matching": jury.CITATION_MATCHING,
        "representation_parser": jury.citation_parser_metadata(),
        "envelope_aliases": envelope.ALIASES,
        "juror_role_lookup_aliases": jury.JUROR_ALIASES,
        "envelope_policy": {
            "outer": "one string-or-object field; canonical key or its explicit alias only",
            "finish_reason": "stop",
            "inner": "validate frozen bindings/schema/citations and prior jurors before rename",
            "repair": False,
            "original_bytes": "response.raw and output.txt remain unchanged",
            "receipt": "envelope.json records representation, keys, serialized and semantic hashes",
        },
        "seed_root": str(envelope.SEED_ROOT.relative_to(ROOT)),
        "retained_prefix": seed.receipts if seed is not None else [],
        "timeout_seconds": TIMEOUT,
        "request_limit": REQUEST_LIMIT,
        "response_limit": RESPONSE_LIMIT,
        "judgment_limit": JUDGMENT_LIMIT,
        "cache": False,
        "retries": 0,
        "store": False,
        "store_wire_via_extra_body": True,
        "response_format": "json_object",
        "thinking_override": None,
        "billing_basis": "operator-confirmed subscription",
        "monetary_gate": False,
        "limits_source": "installed Pi local pi-ai/dist/providers/data/zai.json "
        "['openai-completions']['glm-5.3'] metadata; not provider-verified backend limits",
        "prior_attempt_root": str(PRIOR_ATTEMPT_ROOT.relative_to(ROOT)),
        "prior_response_sha256": PRIOR_RESPONSE_SHA256,
        "original_sha256": {
            str(p.relative_to(ROOT)): jury.sha(p.read_bytes())
            for p in sorted(SOURCE.glob("t*.json"))
        },
        "message_bounds": bounds,
        "input_sha256": {k: jury.sha(v) for k, v in copies.items()},
        "code_sha256": {
            str(p.relative_to(ROOT)): jury.sha(p.read_bytes())
            for p in (
                *jury.PROGRAM.glob("*.py"),
                jury.PROGRAM / "generation.json",
                Path(__file__),
                ROOT / "scripts/compass_jury_budget.py",
                ROOT / "scripts/compass_jury_envelope.py",
                ROOT / "scripts/compass_jury.py",
            )
        },
        "limitations": "byte-based context bound is conservative; historical inputs "
        "not authenticated; structural checks not semantic correctness; advisory only",
    }
    return protocol, prepared, copies


class GuardTransport:
    """Consume each stage once; first six responses are retained, not a new HTTP attempt."""

    def __init__(self, inner, root, bounds):
        self.inner, self.root, self.bounds = inner, root, bounds
        self.ledger = AttemptLedger()
        self.inputs = envelope.FrozenInputs(root, CAPTURES)
        self.seed = envelope.load_seed()
        if self.seed is not None:
            self.seed.verify_inputs(self.inputs.prepared, self.inputs.copies)
        self.new_http_attempts, self.reused_responses = 0, 0
        self.sequence = [(c, f) for c in CAPTURES for f in jury.OUTPUTS]
        self.index, self.active, self.spent, self.failed = 0, None, True, False

    def begin_stage(self, capture, field):
        if (
            self.failed
            or not self.spent
            or self.index >= len(self.sequence)
            or (capture, field) != self.sequence[self.index]
        ):
            self.failed = True
            raise ValueError("duplicate/out-of-order stage")
        self.active = (capture, field)
        self.index += 1
        self.spent = False
        self.stage_dir.mkdir()
        sync_directory(self.root)
        save(
            self.stage_dir / "stage.json",
            {
                "capture": capture,
                "field": field,
                "origin": "retained_v5_response"
                if self.seed is not None and self.index <= len(envelope.SEED_STAGES)
                else "live_http",
            },
        )

    @property
    def stage_dir(self):
        return self.root / ("--".join(self.active))

    def record_error(self, error):
        self.failed = True
        target = self.stage_dir if self.active else self.root
        path = target / "error.json"
        if not path.exists():
            save(path, {"error_type": type(error).__name__})

    def handle_request(self, request):
        try:
            if self.failed or self.spent or self.active is None:
                raise ValueError("undeclared or repeated HTTP attempt")
            self.spent = True
            raw = request.content
            if (
                request.method != "POST"
                or str(request.url) != ENDPOINT
                or request.headers.get("content-type", "").split(";")[0] != "application/json"
                or len(raw) > REQUEST_LIMIT
            ):
                raise ValueError("request envelope rejected")
            body = jury.strict_json(raw.decode("utf-8"), max_bytes=REQUEST_LIMIT)
            self.validate_body(body)
            size = len(encoded(body["messages"]))
            validate_capacity(size)
            if size > self.bounds[self.active[0]][self.active[1]]:
                raise ValueError("projected message bound exceeded")
            durable(self.stage_dir / "request.body.json", raw)  # Never headers/client/LM kwargs.
            self.inputs.check()
            self.ledger.record(size)
            save(
                self.stage_dir / "attempt.json",
                {
                    "message_bytes": size,
                    "total_message_bytes": self.ledger.message_bytes,
                    "attempt": self.ledger.calls,
                },
            )
            request.headers["accept-encoding"] = "identity"
            request.extensions["timeout"] = dict.fromkeys(
                ("connect", "read", "write", "pool"), TIMEOUT
            )
            if self.seed is not None and self.index <= len(envelope.SEED_STAGES):
                response = self.seed.response(self.active, self.index, body, request)
                self.reused_responses += 1
            else:
                if self.seed is not None and (
                    self.seed.failed or self.seed.consumed != len(envelope.SEED_STAGES)
                ):
                    raise ValueError("required seed not consumed")
                self.new_http_attempts += 1
                response = self.inner.handle_request(request)
            return envelope.capture_response(self, response, request)
        except BaseException as error:
            self.record_error(error)
            raise

    def validate_body(self, body):
        allowed = set(request_body([]))
        if not isinstance(body, dict) or set(body) - allowed:
            raise ValueError("request keys rejected")
        tokens = body.get("max_tokens")
        if (
            body.get("model") != "glm-5.3"
            or body.get("store") is not False
            or type(tokens) is not int
            or tokens != MAX_TOKENS
            or body.get("temperature") != 0.7
            or type(body.get("n")) is not int
            or body["n"] != 1
            or body.get("stream", False) is not False
            or body.get("response_format") != {"type": "json_object"}
        ):
            raise ValueError("model/policy rejected")
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages rejected")
        for message in messages:
            if (
                not isinstance(message, dict)
                or set(message) != {"role", "content"}
                or message["role"] not in {"system", "user", "assistant"}
                or not isinstance(message["content"], str)
            ):
                raise ValueError("message rejected")

    def close(self):
        self.inner.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def make_lm(guard):
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    import httpx
    import openai
    from dspy_lm_auth import LM

    class JsonOnlyLM(LM):
        @property
        def supports_response_schema(self):
            return False

    lm = JsonOnlyLM(
        "zai/glm-5.3",
        cache=False,
        num_retries=0,
        max_retries=0,
        max_tokens=MAX_TOKENS,
        temperature=0.7,
        n=1,
        store=False,
        drop_params=False,
    )
    if lm.model != "openai/glm-5.3" or lm.kwargs["api_base"] != BASE:
        raise ValueError("maintained LM route mismatch")
    # LiteLLM elides default store=False; supported extra_body preserves the wire flag.
    lm.kwargs["extra_body"] = {"store": False}
    lm.kwargs["client"] = openai.OpenAI(
        api_key=lm.kwargs["api_key"],
        base_url=lm.kwargs["api_base"],
        max_retries=0,
        timeout=TIMEOUT,
        http_client=httpx.Client(
            transport=guard, follow_redirects=False, timeout=TIMEOUT, trust_env=False
        ),
    )
    return lm


def run_captures(prepared, lm, guard):
    guard.inputs.check()
    if prepared != guard.inputs.prepared:
        raise ValueError("execution inputs differ from frozen inputs")
    # Scope the loader substitution to this single runner's already verified module.
    with contextlib.ExitStack() as stack:
        old = jury.load_program
        stack.callback(setattr, jury, "load_program", old)
        jury.load_program = program_module
        for capture in CAPTURES:
            try:
                result = jury.evaluate(
                    prepared[capture],
                    lm,
                    stage_callback=lambda field, c=capture: guard.begin_stage(c, field),
                )
                save(guard.root / f"{capture}.outputs.json", result)
            except BaseException as error:
                guard.record_error(error)
                raise
    reused = len(envelope.SEED_STAGES) if guard.seed is not None else 0
    if (
        guard.ledger.calls != MAX_CALLS
        or guard.failed
        or guard.reused_responses != reused
        or guard.new_http_attempts != MAX_CALLS - reused
    ):
        raise ValueError("incomplete pilot")


def execute():
    import httpx

    os.umask(0o077)
    # Third-party exception/log renderers may include request headers. Only our type
    # receipts and CLI status are emitted; raw response/body evidence stays private.
    logging.disable(logging.CRITICAL)
    with one_shot(DEST):
        guard = None
        try:
            protocol, prepared, copies = preflight()
            save(DEST / "protocol.json", protocol)
            frozen = DEST / "inputs"
            frozen.mkdir()
            sync_directory(DEST)
            for name, raw in copies.items():
                durable(frozen / name, raw)
            for capture, inputs in prepared.items():
                save(frozen / f"{capture}.inputs.json", inputs)
            guard = GuardTransport(
                httpx.HTTPTransport(retries=0, trust_env=False), DEST, protocol["message_bounds"]
            )
            # Suppress library stdout/stderr, never exception text or credentials in logs.
            with (
                open(os.devnull, "w") as sink,
                contextlib.redirect_stdout(sink),
                contextlib.redirect_stderr(sink),
            ):
                lm = make_lm(guard)
                try:
                    run_captures(prepared, lm, guard)
                finally:
                    lm.kwargs["client"].close()
            save(
                DEST / "complete.json",
                {
                    "attempts": guard.ledger.calls,
                    "attempts_basis": "stage_attempts_including_retained_response",
                    "stages": guard.ledger.calls,
                    "new_http_attempts": guard.new_http_attempts,
                    "reused_responses": guard.reused_responses,
                    "cumulative_unique_review_responses": guard.new_http_attempts
                    + guard.reused_responses,
                    "message_bytes": guard.ledger.message_bytes,
                    "action_permission": "not_granted",
                },
            )
        except BaseException as error:
            if guard is not None:
                guard.record_error(error)
            save(DEST / "failed.json", {"error_type": type(error).__name__})
            raise
        finally:
            if guard is not None:
                guard.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute and not args.preflight:
        parser.print_help()
        return 0
    try:
        if args.preflight:
            protocol, _, _ = preflight()
            print(json.dumps(protocol, indent=2))
            return 0
        execute()
        print("Pilot completed; retained evidence is advisory, not grade replacement.")
        return 0
    except BaseException as error:
        print(json.dumps({"status": "blocked_or_failed", "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
