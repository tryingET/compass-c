"""Bounded, deterministic, proposal-only constitutional analysis."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

SCHEMA_VERSION = 1
DIGEST_PREFIX = "sha256:"
METRICS = ("mutation_radius", "owner_crossings", "rollback_cost", "verification_cost", "maintenance_burden")
OPS = {"literal", "get", "eq", "ne", "lt", "le", "gt", "ge", "in", "contains", "exists", "and", "or", "not"}
MAX_BYTES = 262_144
MAX_DEPTH = 32
MAX_NODES = 10_000
MAX_COLLECTION = 1_000
MAX_STRING = 16_384
MAX_EVALUATION_STEPS = 10_000
INTEGRITY_NOTICE = "Hashing proves integrity, not truth; evidence records remain unverified claims."


class ConstitutionError(ValueError):
    pass


def _plain(value: Any, where: str = "input", *, max_bytes: int = MAX_BYTES) -> Any:
    """Require an exact, bounded plain JSON tree (not merely JSON-like Python objects)."""
    nodes = 0
    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_NODES:
            raise ConstitutionError(f"{where} exceeds maximum node count")
        if depth > MAX_DEPTH:
            raise ConstitutionError(f"{where} exceeds maximum depth")
        if item is None or type(item) is bool or type(item) is int:
            return
        if type(item) is float:
            if item != item or item in (float("inf"), float("-inf")):
                raise ConstitutionError(f"{where} contains a non-finite number")
            return
        if type(item) is str:
            if len(item.encode("utf-8")) > MAX_STRING:
                raise ConstitutionError(f"{where} contains an oversized string")
            return
        if type(item) is list:
            if len(item) > MAX_COLLECTION:
                raise ConstitutionError(f"{where} contains an oversized collection")
            for child in item: visit(child, depth + 1)
            return
        if type(item) is dict:
            if len(item) > MAX_COLLECTION:
                raise ConstitutionError(f"{where} contains an oversized collection")
            for key, child in item.items():
                if type(key) is not str:
                    raise ConstitutionError(f"{where} object keys must be strings")
                visit(key, depth + 1); visit(child, depth + 1)
            return
        raise ConstitutionError(f"{where} must be a plain JSON tree")
    visit(value, 0)
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise ConstitutionError(f"{where} must be canonical JSON") from exc
    if len(encoded) > max_bytes:
        raise ConstitutionError(f"{where} exceeds maximum byte size")
    return value


def strict_json_load(handle: Any) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out: raise ConstitutionError(f"duplicate JSON key: {key}")
            out[key] = value
        return out
    try:
        raw = handle.read(MAX_BYTES + 1)
        if type(raw) is not str or len(raw.encode("utf-8")) > MAX_BYTES:
            raise ConstitutionError("JSON input exceeds maximum byte size")
        value = json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(ConstitutionError(f"invalid JSON number: {x}")))
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ConstitutionError("invalid or excessively deep JSON input") from exc
    return _plain(value)


def canonical_json(value: Any) -> bytes:
    _plain(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value: Any, field: str | None = None) -> str:
    item = deepcopy(value)
    if field and type(item) is dict: item.pop(field, None)
    return DIGEST_PREFIX + hashlib.sha256(canonical_json(item)).hexdigest()


def _exact(obj: Any, keys: set[str], where: str) -> dict[str, Any]:
    _plain(obj, where)
    if type(obj) is not dict or set(obj) != keys:
        raise ConstitutionError(f"{where}: expected exactly {sorted(keys)}")
    return obj


def _identity(value: Any, where: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ConstitutionError(f"{where} must be a non-empty canonical string")
    return value


def _sorted_strings(value: Any, where: str, *, nonempty: bool = True) -> list[str]:
    if type(value) is not list or (nonempty and not value) or any(type(x) is not str or not x or x != x.strip() for x in value):
        raise ConstitutionError(f"{where} must be a canonical string list")
    if value != sorted(set(value)):
        raise ConstitutionError(f"{where} must be sorted and unique")
    return value


def _evidence_manifest(value: Any, where: str) -> set[str]:
    if type(value) is not list or not value: raise ConstitutionError(f"{where} must be non-empty")
    ids, digests = set(), set()
    for i, raw in enumerate(value):
        r = _exact(raw, {"evidence_id", "status", "provenance_locator", "payload", "evidence_digest"}, f"{where}[{i}]")
        eid = _identity(r["evidence_id"], "evidence_id")
        _identity(r["provenance_locator"], "provenance_locator")
        if r["status"] != "unverified_claim": raise ConstitutionError("evidence status must be unverified_claim")
        if eid in ids or r["evidence_digest"] in digests: raise ConstitutionError("duplicate global evidence identity")
        if r["evidence_digest"] != digest(r, "evidence_digest"): raise ConstitutionError("evidence digest mismatch")
        ids.add(eid); digests.add(r["evidence_digest"])
    if [r["evidence_digest"] for r in value] != sorted(digests): raise ConstitutionError(f"{where} must be digest-sorted")
    return digests


def _path(value: Any, path: Any) -> Any:
    if type(path) is not str or not path or any(p in {"", "__class__", "__dict__"} for p in path.split(".")):
        raise ConstitutionError("invalid closed data path")
    current = value
    for part in path.split("."):
        if type(current) is not dict or part not in current: raise KeyError(path)
        current = current[part]
    return current


def evaluate(expr: Any, subject: Any) -> Any:
    _plain(expr, "predicate"); _plain(subject, "subject")
    steps = 0
    def run(node: Any) -> Any:
        nonlocal steps
        steps += 1
        if steps > MAX_EVALUATION_STEPS: raise ConstitutionError("predicate exceeds maximum evaluation steps")
        if type(node) is not dict or set(node) - {"op", "args", "path", "value"}: raise ConstitutionError("predicate must be a closed AST object")
        op = node.get("op")
        if op not in OPS: raise ConstitutionError(f"predicate operator is not allowed: {op!r}")
        if op == "literal": _exact(node, {"op", "value"}, "literal"); return node["value"]
        if op in {"get", "exists"}:
            _exact(node, {"op", "path"}, op)
            try: value = _path(subject, node["path"])
            except KeyError: return False if op == "exists" else None
            return True if op == "exists" else value
        _exact(node, {"op", "args"}, op)
        args = node["args"]
        if type(args) is not list: raise ConstitutionError(f"{op}.args must be a list")
        values = [run(x) for x in args]
        if op == "not":
            if len(values) != 1 or type(values[0]) is not bool: raise ConstitutionError("not requires one boolean")
            return not values[0]
        if op in {"and", "or"}:
            if not values or any(type(x) is not bool for x in values): raise ConstitutionError(f"{op} requires booleans")
            return all(values) if op == "and" else any(values)
        if len(values) != 2: raise ConstitutionError(f"{op} requires two arguments")
        a, b = values
        if op in {"eq", "ne"}:
            same = type(a) is type(b) and a == b
            return same if op == "eq" else not same
        if type(a) is bool or type(b) is bool or type(a) is not type(b): raise ConstitutionError(f"invalid operands for {op}")
        try:
            return {"lt": lambda:a < b, "le":lambda:a <= b, "gt":lambda:a > b, "ge":lambda:a >= b,
                    "in":lambda:a in b, "contains":lambda:b in a}[op]()
        except (TypeError, KeyError) as exc: raise ConstitutionError(f"invalid operands for {op}") from exc
    return run(expr)


def _fixture(raw: Any, group: str, i: int) -> tuple[str, Any, bool]:
    schemas = {
        "positive_fixtures": ({"fixture_id", "subject", "must_match"}, "must_match", True),
        "negative_fixtures": ({"fixture_id", "subject", "must_not_match"}, "must_not_match", True),
        "adversarial_counterexamples": ({"fixture_id", "subject", "counterexample_must_not_match"}, "counterexample_must_not_match", True),
        "false_positive_challenges": ({"fixture_id", "subject", "acceptable_must_not_match"}, "acceptable_must_not_match", True),
    }
    keys, flag, exact = schemas[group]; f = _exact(raw, keys, f"{group}[{i}]")
    if type(f[flag]) is not bool or f[flag] is not exact: raise ConstitutionError(f"{group}[{i}].{flag} must be true")
    return _identity(f["fixture_id"], "fixture_id"), f["subject"], group == "positive_fixtures"


def validate_candidate(packet: Any) -> dict[str, Any]:
    keys = {"schema_version","candidate_id","owner","adoption_scope","rationale","predicate","positive_fixtures","negative_fixtures","adversarial_counterexamples","severity","suppression_policy","false_positive_challenges","evidence_digests","evidence_manifest","candidate_digest"}
    p = _exact(packet, keys, "candidate")
    if type(p["schema_version"]) is not int or p["schema_version"] != 1: raise ConstitutionError("unsupported candidate schema")
    for name in ("candidate_id","owner","rationale"): _identity(p[name], name)
    _sorted_strings(p["adoption_scope"], "adoption_scope")
    if p["severity"] not in {"info","warning","error"}: raise ConstitutionError("invalid severity")
    if p["suppression_policy"] not in {"none","owner-explicit"}: raise ConstitutionError("invalid suppression policy")
    evidence = _evidence_manifest(p["evidence_manifest"], "evidence_manifest")
    if set(_sorted_strings(p["evidence_digests"], "evidence_digests")) != evidence: raise ConstitutionError("evidence manifest mismatch")
    failures, fixture_ids = [], set()
    for group in ("positive_fixtures","negative_fixtures","adversarial_counterexamples","false_positive_challenges"):
        if type(p[group]) is not list or not p[group]: raise ConstitutionError(f"{group} must be non-empty")
        group_ids = [raw.get("fixture_id") if type(raw) is dict else None for raw in p[group]]
        if group_ids != sorted(group_ids) or len(group_ids) != len(set(group_ids)):
            raise ConstitutionError(f"{group} must be canonically fixture-id sorted")
        for i, raw in enumerate(p[group]):
            fid, subject, expected = _fixture(raw, group, i)
            if fid in fixture_ids: raise ConstitutionError("duplicate global fixture identity")
            fixture_ids.add(fid)
            result = evaluate(p["predicate"], subject)
            if type(result) is not bool or result is not expected: failures.append(f"{group}:{fid}")
    expected = digest(p, "candidate_digest")
    if p["candidate_digest"] != expected: raise ConstitutionError("candidate digest mismatch")
    return {"schema_version":1,"schema_conformant":True,"fixtures_consistent":not failures,"candidate_digest":expected,"failures":sorted(failures),"certifies_validity":False,"authority":"proposal-only","integrity_notice":INTEGRITY_NOTICE}


def challenge_candidate(packet: Any) -> dict[str, Any]:
    out = validate_candidate(packet)
    out["challenge_digest"] = digest({"candidate_digest":out["candidate_digest"],"failures":out["failures"]})
    return out


def differential(candidate_a: Any, candidate_b: Any, subjects_packet: Any) -> dict[str, Any]:
    va, vb = validate_candidate(candidate_a), validate_candidate(candidate_b)
    if not va["fixtures_consistent"] or not vb["fixtures_consistent"]: raise ConstitutionError("differential rejects fixture-inconsistent candidates")
    sp = _exact(subjects_packet, {"schema_version","subjects","subjects_digest"}, "subjects")
    if type(sp["schema_version"]) is not int or sp["schema_version"] != 1 or sp["subjects_digest"] != digest(sp, "subjects_digest"): raise ConstitutionError("invalid subjects packet")
    if type(sp["subjects"]) is not list: raise ConstitutionError("subjects must be a list")
    ordered = sorted(sp["subjects"], key=canonical_json)
    encoded_subjects = [canonical_json(subject) for subject in ordered]
    if sp["subjects"] != ordered or len(encoded_subjects) != len(set(encoded_subjects)):
        raise ConstitutionError("subjects must be canonically sorted and unique")
    differences=[]
    for s in ordered:
        a,b=evaluate(candidate_a["predicate"],s),evaluate(candidate_b["predicate"],s)
        if type(a) is not bool or type(b) is not bool: raise ConstitutionError("candidate predicate must return boolean")
        if a != b: differences.append({"subject_digest":digest(s),"a":a,"b":b})
    out={"schema_version":1,"candidate_a_digest":candidate_a["candidate_digest"],"candidate_b_digest":candidate_b["candidate_digest"],"subjects_digest":sp["subjects_digest"],"differences":differences,"certifies_validity":False,"authority":"proposal-only","integrity_notice":INTEGRITY_NOTICE}
    out["result_digest"]=digest(out); return out


def generate_mutants(contract: Any, acceptance: Any, corpus: Any) -> dict[str, Any]:
    c=_exact(contract,{"schema_version","contract_id","capabilities","operations","contract_digest"},"contract")
    if type(c["schema_version"]) is not int or c["schema_version"] != 1: raise ConstitutionError("invalid contract schema")
    _identity(c["contract_id"],"contract_id"); _sorted_strings(c["capabilities"],"capabilities",nonempty=False); _sorted_strings(c["operations"],"operations",nonempty=False)
    if c["contract_digest"] != digest(c,"contract_digest"): raise ConstitutionError("contract digest mismatch")
    a=_exact(acceptance,{"schema_version","acceptance_id","generation_id","nonce","actor_type","actor_id","assertion","contract_digest","acceptance_digest"},"acceptance")
    if type(a["schema_version"]) is not int or a["schema_version"] != 1 or a["actor_type"] != "operator" or a["assertion"] != "accepted-for-mutation-testing": raise ConstitutionError("exact operator acceptance required")
    _identity(a["acceptance_id"],"acceptance_id"); _identity(a["generation_id"],"generation_id"); _identity(a["nonce"],"nonce"); actor_id = _identity(a["actor_id"],"actor_id")
    if (not actor_id.startswith("operator:") or actor_id == "operator:"
            or a["acceptance_id"] in {c["contract_id"],actor_id}
            or a["contract_digest"] != c["contract_digest"]
            or a["acceptance_digest"] != digest(a,"acceptance_digest")):
        raise ConstitutionError("stale, self, reused, non-operator, or mismatched acceptance")
    cp=_exact(corpus,{"schema_version","generation_id","acceptance_nonce","consumed_acceptance_digests","tests","corpus_digest"},"corpus")
    if type(cp["schema_version"]) is not int or cp["schema_version"] != 1 or cp["corpus_digest"] != digest(cp,"corpus_digest"): raise ConstitutionError("invalid closed corpus")
    _identity(cp["generation_id"],"generation_id"); _identity(cp["acceptance_nonce"],"acceptance_nonce")
    consumed=_sorted_strings(cp["consumed_acceptance_digests"],"consumed_acceptance_digests",nonempty=False)
    if a["generation_id"] != cp["generation_id"] or a["nonce"] != cp["acceptance_nonce"] or a["acceptance_digest"] in consumed: raise ConstitutionError("stale or reused acceptance")
    if type(cp["tests"]) is not list or not cp["tests"]: raise ConstitutionError("closed corpus must be non-empty")
    ordered_test_ids = [test.get("test_id") if type(test) is dict else None for test in cp["tests"]]
    if ordered_test_ids != sorted(ordered_test_ids) or len(ordered_test_ids) != len(set(ordered_test_ids)):
        raise ConstitutionError("closed corpus tests must be canonically test-id sorted")
    test_ids=set()
    for i,t in enumerate(cp["tests"]):
        t=_exact(t,{"test_id","required_capabilities","required_operations","ambiguous_capabilities","ambiguous_operations"},f"tests[{i}]"); tid=_identity(t["test_id"],"test_id")
        if tid in test_ids: raise ConstitutionError("duplicate test identity")
        test_ids.add(tid)
        required_capabilities = _sorted_strings(t["required_capabilities"],"required_capabilities",nonempty=False)
        required_operations = _sorted_strings(t["required_operations"],"required_operations",nonempty=False)
        ambiguous_capabilities = _sorted_strings(t["ambiguous_capabilities"],"ambiguous_capabilities",nonempty=False)
        ambiguous_operations = _sorted_strings(t["ambiguous_operations"],"ambiguous_operations",nonempty=False)
        if (not set(required_capabilities).issubset(c["capabilities"])
                or not set(required_operations).issubset(c["operations"])
                or not set(ambiguous_capabilities).issubset(c["capabilities"])
                or not set(ambiguous_operations).issubset(c["operations"])):
            raise ConstitutionError("closed corpus must pass against and be bounded by the baseline contract")
    mutants=[]
    for kind,collection in (("capability","capabilities"),("operation","operations")):
        for value in c[collection]:
            packet=deepcopy(c); packet[collection]=[x for x in packet[collection] if x != value]; packet["contract_digest"]=digest(packet,"contract_digest")
            outcomes=[]
            for t in cp["tests"]:
                missing=(set(t["required_capabilities"])-set(packet["capabilities"])) | (set(t["required_operations"])-set(packet["operations"]))
                outcomes.append({"test_id":t["test_id"],"outcome":"fail" if missing else "pass"})
            if any(x["outcome"]=="fail" for x in outcomes): classification="killed"
            elif any(value in t[f"ambiguous_{collection}"] for t in cp["tests"]): classification="spec-ambiguous"
            else: classification="survived"
            m={"mutation":f"remove-{kind}","value":value,"mutated_contract":packet,"mutated_contract_digest":packet["contract_digest"],"test_outcomes":outcomes,"classification":classification}; m["mutant_digest"]=digest(m); mutants.append(m)
    out={"schema_version":1,"contract_digest":c["contract_digest"],"acceptance_digest":a["acceptance_digest"],"corpus_digest":cp["corpus_digest"],"mutants":mutants,"installed":False,"certifies_validity":False,"authority":"test-generation-only","integrity_notice":INTEGRITY_NOTICE}; out["result_digest"]=digest(out); return out


def pareto_frontier(market: Any) -> dict[str, Any]:
    m=_exact(market,{"schema_version","market_id","metric_definition","evidence_manifest","bids","market_digest"},"market")
    if type(m["schema_version"]) is not int or m["schema_version"] != 1: raise ConstitutionError("invalid market")
    _identity(m["market_id"],"market_id")
    md=_exact(m["metric_definition"],{"name","version","metrics"},"metric_definition"); _identity(md["name"],"metric name"); _identity(md["version"],"metric version")
    if md["metrics"] != list(METRICS): raise ConstitutionError("unsupported metric definition")
    evidence=_evidence_manifest(m["evidence_manifest"],"evidence_manifest")
    if type(m["bids"]) is not list or not m["bids"]: raise ConstitutionError("bids must be non-empty")
    bids=[]; ids=set(); digests=set()
    plan_keys={"summary","steps","affected_repositories","verification_commands","rollback_steps"}
    for raw in m["bids"]:
        b=_exact(raw,{"schema_version","bid_id","proposer","plan",*METRICS,"convergence_evidence_digests","bid_digest"},"bid")
        if type(b["schema_version"]) is not int or b["schema_version"] != 1 or b["bid_digest"] != digest(b,"bid_digest"): raise ConstitutionError("invalid bid identity")
        bid_id=_identity(b["bid_id"],"bid_id"); _identity(b["proposer"],"proposer"); _exact(b["plan"],plan_keys,"plan")
        _identity(b["plan"]["summary"],"plan.summary")
        for k in ("steps","affected_repositories","verification_commands","rollback_steps"): _sorted_strings(b["plan"][k],f"plan.{k}")
        if bid_id in ids or b["bid_digest"] in digests: raise ConstitutionError("duplicate global bid identity")
        ids.add(bid_id); digests.add(b["bid_digest"])
        if any(type(b[x]) is not int or b[x] < 0 for x in METRICS): raise ConstitutionError("bid metrics must be exact non-negative integers")
        if not set(_sorted_strings(b["convergence_evidence_digests"],"convergence_evidence_digests",nonempty=False)).issubset(evidence): raise ConstitutionError("unbound evidence claim")
        bids.append(b)
    bids.sort(key=lambda x:x["bid_digest"])
    if m["bids"] != bids: raise ConstitutionError("bids must be digest-sorted")
    if m["market_digest"] != digest(m,"market_digest"): raise ConstitutionError("market digest mismatch")
    def dominates(a:dict[str,Any],b:dict[str,Any])->bool:
        av=tuple(a[x] for x in METRICS); bv=tuple(b[x] for x in METRICS)
        return all(x<=y for x,y in zip(av,bv)) and any(x<y for x,y in zip(av,bv))
    frontier=[b["bid_digest"] for b in bids if not any(dominates(o,b) for o in bids if o is not b)]
    out={"schema_version":1,"market_id":m["market_id"],"market_digest":m["market_digest"],"bid_digests":[b["bid_digest"] for b in bids],"evidence_manifest_digest":digest(m["evidence_manifest"]),"metric_definition":md,"pareto_frontier":frontier,"evidence_annotations":{b["bid_digest"]:b["convergence_evidence_digests"] for b in bids},"winner":None,"applied":False,"certifies_validity":False,"authority":"owner-decision-required","integrity_notice":INTEGRITY_NOTICE}; out["result_digest"]=digest(out); return out
