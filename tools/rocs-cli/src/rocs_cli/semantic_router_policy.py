"""Descriptor-anchored policy capture and closed local-Git provenance reads."""
from __future__ import annotations
import hashlib, os, resource, stat, subprocess, tempfile
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
from rocs_cli.semantic_protocol import ProtocolError
from rocs_cli.semantic_router_invariants import validate_invariants
from rocs_cli.semantic_router_protocol import (
    MAX_POLICY_BYTES, MAX_PROVENANCE_BYTES, RouteProtocolError, parse_policy_bytes,
    parse_provenance_bytes, validate_definition,
)
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
_STAT_FIELDS = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
_GIT = "/usr/bin/git"
_GIT_TIMEOUT = 30.0
_GIT_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C", "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "", "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat", "PAGER": "cat"}
_RESOURCE_FAILURES = {"groups_per_clause limit", "alternatives_per_group limit", "concepts limit",
    "clauses limit", "total_alternatives limit", "normalized_alternative_bytes limit", "joint_routes limit"}
def _race_hook(_stage: str) -> None: pass
def _same_stat(left: os.stat_result, right: os.stat_result) -> bool: return all(getattr(left, field) == getattr(right, field) for field in _STAT_FIELDS)
def _same_dir(left: os.stat_result, right: os.stat_result) -> bool: return (left.st_dev, left.st_ino, left.st_mode) == (right.st_dev, right.st_ino, right.st_mode)
def _identity(value: os.stat_result) -> tuple[int, int]: return value.st_dev, value.st_ino
def _close_nodes(nodes: list["_Node"]) -> None:
    for node in reversed(nodes):
        try: os.close(node.fd)
        except OSError: pass
    nodes.clear()
def _safe_text(value: os.PathLike[str] | str) -> str:
    raw = os.fspath(value)
    if type(raw) is not str or "\0" in raw:
        raise RouteProtocolError("invalid_policy")
    try:
        raw.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise RouteProtocolError("invalid_policy") from exc
    return raw
def _relative_parts(value: os.PathLike[str] | str) -> tuple[str, ...]:
    raw = _safe_text(value)
    if not raw or raw.startswith("/") or raw.endswith("/") or "\\" in raw:
        raise RouteProtocolError("invalid_policy")
    parts = tuple(raw.split("/"))
    if any(part in ("", ".", "..") for part in parts):
        raise RouteProtocolError("invalid_policy")
    return parts
@dataclass
class _Node:
    fd: int; parent_fd: int | None; name: str | None
    captured: os.stat_result; regular: bool = False
    def recheck(self) -> None:
        try:
            opened = os.fstat(self.fd)
            anchored = opened if self.parent_fd is None else os.stat(
                self.name, dir_fd=self.parent_fd, follow_symlinks=False,
            )
        except OSError as exc:
            raise RouteProtocolError("snapshot_changed") from exc
        same = _same_stat if self.regular else _same_dir
        if not same(self.captured, opened) or not same(self.captured, anchored):
            raise RouteProtocolError("snapshot_changed")
        if self.regular and (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1):
            raise RouteProtocolError("snapshot_changed")
        if not self.regular and not stat.S_ISDIR(opened.st_mode):
            raise RouteProtocolError("snapshot_changed")
class _Root:
    def __init__(self, nodes: list[_Node]): self.nodes = nodes
    @property
    def fd(self) -> int: return self.nodes[-1].fd
    def recheck(self) -> None:
        for node in self.nodes: node.recheck()
    def close(self) -> None: _close_nodes(self.nodes)
def _open_root(path: os.PathLike[str] | str) -> _Root:
    raw = _safe_text(path)
    if not raw or "\\" in raw:
        raise RouteProtocolError("invalid_policy")
    supplied = raw.split("/")[1:] if raw.startswith("/") else raw.split("/")
    if any(part in ("", ".", "..") for part in supplied):
        raise RouteProtocolError("invalid_policy")
    absolute = raw if raw.startswith("/") else os.path.join(os.getcwd(), raw)
    parts = tuple(part for part in absolute.split("/") if part)
    nodes: list[_Node] = []
    try:
        fd = os.open("/", _DIR_FLAGS)
        nodes.append(_Node(fd, None, None, os.fstat(fd)))
        for part in parts:
            parent = nodes[-1].fd
            before = os.stat(part, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise RouteProtocolError("invalid_policy")
            _race_hook("before_root_component_open")
            child = os.open(part, _DIR_FLAGS, dir_fd=parent)
            opened = os.fstat(child)
            if not _same_dir(before, opened):
                os.close(child)
                raise RouteProtocolError("snapshot_changed")
            nodes.append(_Node(child, parent, part, before))
        if len(nodes) == 1:
            raise RouteProtocolError("invalid_policy")
        return _Root(nodes)
    except RouteProtocolError:
        _close_nodes(nodes); raise
    except (OSError, UnicodeError) as exc:
        _close_nodes(nodes); raise RouteProtocolError("invalid_policy") from exc
def _read_limited(fd: int, maximum: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = maximum + 1
    while remaining:
        chunk = os.read(fd, min(remaining, 65_536))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
@dataclass
class _CapturedFile:
    nodes: list[_Node]; raw: bytes; maximum: int; digest: str
    @property
    def identity(self) -> tuple[int, int]: return _identity(self.nodes[-1].captured)
    def recheck(self) -> None:
        for node in self.nodes:
            node.recheck()
        final = self.nodes[-1]
        try:
            before = os.fstat(final.fd)
            raw = _read_limited(final.fd, self.maximum)
            after = os.fstat(final.fd)
        except OSError as exc:
            raise RouteProtocolError("snapshot_changed") from exc
        _race_hook("during_file_final_recheck")
        for node in self.nodes: node.recheck()
        if (
            not _same_stat(final.captured, before) or not _same_stat(before, after)
            or len(raw) > self.maximum or raw != self.raw
            or "sha256:" + hashlib.sha256(raw).hexdigest() != self.digest
        ):
            raise RouteProtocolError("snapshot_changed")
    def close(self) -> None: _close_nodes(self.nodes)
def _capture_file(root_fd: int, path: os.PathLike[str] | str, maximum: int, label: str) -> _CapturedFile:
    parts = _relative_parts(path)
    nodes: list[_Node] = []
    parent = root_fd
    try:
        for part in parts[:-1]:
            before = os.stat(part, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise RouteProtocolError("invalid_policy")
            child = os.open(part, _DIR_FLAGS, dir_fd=parent)
            opened = os.fstat(child)
            if not _same_dir(before, opened):
                os.close(child)
                raise RouteProtocolError("snapshot_changed")
            nodes.append(_Node(child, parent, part, before))
            parent = child
        name = parts[-1]
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RouteProtocolError("invalid_policy")
        if before.st_size > maximum:
            raise RouteProtocolError("resource_exhausted")
        _race_hook(f"before_{label}_open")
        fd = os.open(name, _FILE_FLAGS, dir_fd=parent)
        opened = os.fstat(fd)
        if not _same_stat(before, opened):
            os.close(fd)
            raise RouteProtocolError("snapshot_changed")
        nodes.append(_Node(fd, parent, name, before, regular=True))
        raw = _read_limited(fd, maximum)
        after = os.fstat(fd)
        anchored = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not _same_stat(before, after) or not _same_stat(before, anchored) or len(raw) != before.st_size:
            raise RouteProtocolError("snapshot_changed")
        if len(raw) > maximum:
            raise RouteProtocolError("resource_exhausted")
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        return _CapturedFile(nodes, raw, maximum, digest)
    except RouteProtocolError:
        _close_nodes(nodes); raise
    except (OSError, UnicodeError) as exc:
        _close_nodes(nodes); raise RouteProtocolError("invalid_policy") from exc
def _is_ancestor(ancestor_fd: int, child_fd: int) -> bool:
    wanted = _identity(os.fstat(ancestor_fd))
    current = os.dup(child_fd)
    try:
        for _ in range(1024):
            here = _identity(os.fstat(current))
            if here == wanted:
                return True
            parent = os.open("..", _DIR_FLAGS, dir_fd=current)
            parent_id = _identity(os.fstat(parent))
            os.close(current)
            current = parent
            if parent_id == here:
                return False
        raise RouteProtocolError("internal")
    finally:
        os.close(current)
def _reject_root_overlap(root: _Root, paths: Iterable[os.PathLike[str] | str]) -> None:
    for path in paths:
        other = _open_root(path)
        try:
            if _is_ancestor(root.fd, other.fd) or _is_ancestor(other.fd, root.fd):
                raise RouteProtocolError("invalid_policy")
        finally:
            other.close()
class _GitFailure(RuntimeError): pass
@dataclass(frozen=True)
class _Source:
    expression: str; digest: str; is_record: bool
@dataclass(frozen=True)
class _VerifiedSource:
    expression: str; oid: str; size: int; raw: bytes
class _GitRepository:
    def __init__(self, root: _Root, git_node: _Node | None, objects_node: _Node):
        self.root = root
        self.git_node = git_node
        self.objects_node = objects_node
        self.git_fd = git_node.fd if git_node else root.fd
        self.fingerprint = b""
        self.sources: tuple[_Source, ...] = ()
        self.verified: tuple[_VerifiedSource, ...] = ()
        self.policy_limit = 0
    @classmethod
    def open(cls, path: os.PathLike[str] | str) -> "_GitRepository":
        root = _open_root(path)
        git_node: _Node | None = None
        objects_node: _Node | None = None
        try:
            try:
                info = os.stat(".git", dir_fd=root.fd, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            if info is not None:
                if not stat.S_ISDIR(info.st_mode):
                    raise RouteProtocolError("invalid_policy")
                fd = os.open(".git", _DIR_FLAGS, dir_fd=root.fd)
                if not _same_dir(info, os.fstat(fd)):
                    os.close(fd)
                    raise RouteProtocolError("snapshot_changed")
                git_node = _Node(fd, root.fd, ".git", info)
                git_fd = fd
            else:
                git_fd = root.fd
            try: os.stat("commondir", dir_fd=git_fd, follow_symlinks=False)
            except FileNotFoundError: pass
            else: raise RouteProtocolError("invalid_policy")
            obj = os.stat("objects", dir_fd=git_fd, follow_symlinks=False)
            if not stat.S_ISDIR(obj.st_mode):
                raise RouteProtocolError("invalid_policy")
            obj_fd = os.open("objects", _DIR_FLAGS, dir_fd=git_fd)
            if not _same_dir(obj, os.fstat(obj_fd)):
                os.close(obj_fd)
                raise RouteProtocolError("snapshot_changed")
            objects_node = _Node(obj_fd, git_fd, "objects", obj)
            return cls(root, git_node, objects_node)
        except (RouteProtocolError, OSError) as exc:
            if objects_node: os.close(objects_node.fd)
            if git_node: os.close(git_node.fd)
            root.close()
            if isinstance(exc, RouteProtocolError): raise
            raise RouteProtocolError("invalid_policy") from exc
    def _command(self, args: Sequence[str], data: bytes = b"", limit: int = 1_048_576) -> bytes:
        command = [
            _GIT, "--no-replace-objects", f"--git-dir=/proc/self/fd/{self.git_fd}",
            "-c", "core.hooksPath=/dev/null", "-c", "credential.helper=",
            "-c", "protocol.allow=never", "-c", "maintenance.auto=false", *args,
        ]
        def bound_output() -> None: resource.setrlimit(resource.RLIMIT_FSIZE, (limit + 1, limit + 1))
        try:
            with tempfile.TemporaryFile(dir="/dev/shm") as output:
                result = subprocess.run(
                    command, cwd="/", env=dict(_GIT_ENV), pass_fds=(self.git_fd,), input=data,
                    stdout=output, stderr=subprocess.DEVNULL, timeout=_GIT_TIMEOUT, check=False,
                    preexec_fn=bound_output,
                )
                output.seek(0); raw = output.read(limit + 1)
        except (OSError, subprocess.SubprocessError) as exc:
            raise _GitFailure("git failure") from exc
        if result.returncode or len(raw) > limit:
            raise _GitFailure("git failure")
        return raw
    def _hazard_fingerprint(self, changed_kind: str) -> bytes:
        try:
            config = self._command(["config", "--local", "--no-includes", "--null", "--list"])
            keys: list[str] = []
            for item in config.split(b"\0"):
                if not item:
                    continue
                key = item.split(b"\n", 1)[0].decode("ascii", "strict").lower()
                keys.append(key)
            forbidden = any(
                key.startswith("include.") or key.startswith("includeif.")
                or key == "extensions.partialclone"
                or (key.startswith("remote.") and (key.endswith(".promisor") or key.endswith(".partialclonefilter")))
                for key in keys
            )
            refs = self._command(["for-each-ref", "--format=%(refname)", "refs/replace"], limit=65_536)
            paths = ("commondir", "shallow", "objects/info/alternates", "objects/info/http-alternates")
            present = []
            for path in paths:
                try:
                    os.stat(path, dir_fd=self.git_fd, follow_symlinks=False)
                    present.append(path)
                except FileNotFoundError:
                    pass
            if forbidden or refs.strip() or present:
                raise RouteProtocolError(changed_kind)
            return hashlib.sha256(config + b"\0" + refs).digest()
        except RouteProtocolError:
            raise
        except (UnicodeError, _GitFailure, OSError) as exc:
            if isinstance(exc, _GitFailure):
                raise RouteProtocolError("internal") from exc
            raise RouteProtocolError(changed_kind) from exc
    def verify(self, sources: Sequence[_Source], policy_limit: int) -> None:
        self.fingerprint = self._hazard_fingerprint("invalid_policy")
        self.sources = tuple(sources)
        self.policy_limit = policy_limit
        self.verified = self._read_sources(self.sources, policy_limit, "invalid_policy")
    def _read_sources(self, sources: Sequence[_Source], policy_limit: int, changed_kind: str) -> tuple[_VerifiedSource, ...]:
        data = b"".join(item.expression.encode("ascii") + b"\n" for item in sources)
        try:
            checked_raw = self._command(
                ["cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
                data, limit=len(data) + len(sources) * 128 + 1024,
            )
        except _GitFailure as exc:
            raise RouteProtocolError("internal") from exc
        lines = checked_raw.splitlines()
        checked: list[tuple[str, int]] = []
        if len(lines) != len(sources):
            raise RouteProtocolError(changed_kind)
        record_total = 0
        for source, line in zip(sources, lines):
            fields = line.split()
            if len(fields) != 3 or fields[1] != b"blob" or len(fields[0]) != 40 or not fields[2].isdigit():
                raise RouteProtocolError(changed_kind)
            try:
                oid = fields[0].decode("ascii")
                size = int(fields[2])
            except (UnicodeError, ValueError) as exc:
                raise RouteProtocolError(changed_kind) from exc
            if size > policy_limit:
                raise RouteProtocolError("resource_exhausted" if changed_kind == "invalid_policy" else changed_kind)
            if source.is_record:
                record_total += size
                if record_total > policy_limit:
                    raise RouteProtocolError("resource_exhausted" if changed_kind == "invalid_policy" else changed_kind)
            checked.append((oid, size))
        content_limit = sum(size for _, size in checked) + len(checked) * 128 + 1024
        try:
            content = self._command(["cat-file", "--batch"], data, limit=content_limit)
        except _GitFailure as exc:
            raise RouteProtocolError("internal") from exc
        offset = 0
        verified: list[_VerifiedSource] = []
        for source, (expected_oid, expected_size) in zip(sources, checked):
            end = content.find(b"\n", offset)
            if end < 0:
                raise RouteProtocolError(changed_kind)
            fields = content[offset:end].split()
            if len(fields) != 3 or fields[0].decode("ascii", "ignore") != expected_oid or fields[1] != b"blob" or fields[2] != str(expected_size).encode():
                raise RouteProtocolError(changed_kind)
            start = end + 1
            finish = start + expected_size
            if finish >= len(content) or content[finish:finish + 1] != b"\n":
                raise RouteProtocolError(changed_kind)
            raw = content[start:finish]
            if "sha256:" + hashlib.sha256(raw).hexdigest() != source.digest:
                raise RouteProtocolError(changed_kind)
            verified.append(_VerifiedSource(source.expression, expected_oid, expected_size, raw))
            offset = finish + 1
        if offset != len(content):
            raise RouteProtocolError(changed_kind)
        return tuple(verified)
    def recheck(self) -> None:
        self.root.recheck()
        if self.git_node: self.git_node.recheck()
        self.objects_node.recheck()
        fingerprint = self._hazard_fingerprint("snapshot_changed")
        verified = self._read_sources(self.sources, self.policy_limit, "snapshot_changed")
        _race_hook("during_git_final_recheck")
        self.root.recheck()
        if self.git_node: self.git_node.recheck()
        self.objects_node.recheck()
        after_fingerprint = self._hazard_fingerprint("snapshot_changed")
        if fingerprint != self.fingerprint or after_fingerprint != fingerprint or verified != self.verified:
            raise RouteProtocolError("snapshot_changed")
    def close(self) -> None:
        for node in (self.objects_node, self.git_node):
            if node:
                try: os.close(node.fd)
                except OSError: pass
        self.root.close()
@dataclass
class CapturedPolicyBundle:
    policy: dict[str, Any]; provenance: dict[str, Any]
    policy_raw: bytes; provenance_raw: bytes
    policy_content_digest: str; provenance_content_digest: str
    _root: _Root; _policy_file: _CapturedFile; _provenance_file: _CapturedFile
    _git: _GitRepository; _closed: bool = False
    def recheck(self) -> None:
        if self._closed: raise RouteProtocolError("internal")
        self._root.recheck(); self._policy_file.recheck(); self._provenance_file.recheck()
        self._git.recheck()
        _race_hook("before_bundle_post_recheck")
        self._root.recheck()
    def close(self) -> None:
        if not self._closed:
            self._policy_file.close(); self._provenance_file.close()
            self._root.close(); self._git.close(); self._closed = True
    def __enter__(self) -> "CapturedPolicyBundle":
        if self._closed: raise RouteProtocolError("internal")
        return self
    def __exit__(self, _type: object, _value: object, _traceback: object) -> bool:
        try:
            self.recheck()
        finally:
            self.close()
        return False
def _limits(request: Mapping[str, Any]) -> Mapping[str, int]:
    try:
        if validate_definition(request, "routeRequest"):
            raise RouteProtocolError("invalid_request")
        limits = request["route_limits"]
        if type(limits) is not dict:
            raise RouteProtocolError("invalid_request")
        return limits
    except RouteProtocolError:
        raise
    except (KeyError, TypeError, ProtocolError, ValueError) as exc:
        raise RouteProtocolError("invalid_request") from exc
def _sources(policy: Mapping[str, Any], provenance: Mapping[str, Any], owner_id: str) -> list[_Source]:
    authority = policy["authority"]
    if authority["owner_repo"] != owner_id or provenance["policy_owner_repo"] != owner_id:
        raise RouteProtocolError("invalid_policy")
    values = [(authority["revision"], authority["path"], authority["source_content_digest"], False)]
    for record in provenance["records"]:
        if record["source_owner_repo"] != owner_id:
            raise RouteProtocolError("invalid_policy")
        values.append((record["source_revision"], record["source_path"], record["source_content_digest"], True))
    result: list[_Source] = []
    for revision, path, digest, is_record in values:
        parts = _relative_parts(path)
        if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
            raise RouteProtocolError("invalid_policy")
        result.append(_Source(f"{revision}:{'/'.join(parts)}", digest, is_record))
    return result
def capture_policy_bundle(
    *, routing_policy_root: os.PathLike[str] | str, policy_path: os.PathLike[str] | str,
    provenance_path: os.PathLike[str] | str, owner_repo_id: str,
    owner_repo_root: os.PathLike[str] | str, request: Mapping[str, Any],
    isolated_roots: Iterable[os.PathLike[str] | str] = (),
) -> CapturedPolicyBundle:
    root: _Root | None = None; policy_file: _CapturedFile | None = None
    provenance_file: _CapturedFile | None = None; repository: _GitRepository | None = None
    try:
        root = _open_root(routing_policy_root)
        _reject_root_overlap(root, isolated_roots)
        policy_file = _capture_file(root.fd, policy_path, MAX_POLICY_BYTES, "policy")
        _race_hook("after_policy_capture")
        provenance_file = _capture_file(root.fd, provenance_path, MAX_PROVENANCE_BYTES, "provenance")
        if policy_file.identity == provenance_file.identity:
            raise RouteProtocolError("invalid_policy")
        _race_hook("before_intermediate_recheck")
        root.recheck(); policy_file.recheck(); provenance_file.recheck()
        policy = parse_policy_bytes(policy_file.raw)
        provenance = parse_provenance_bytes(provenance_file.raw)
        limits = _limits(request)
        policy = parse_policy_bytes(
            policy_file.raw, byte_limit=limits["policy_bytes"], parser_depth=limits["parser_depth"],
            collection_items=limits["collection_items"],
        )
        provenance = parse_provenance_bytes(
            provenance_file.raw, byte_limit=limits["provenance_bytes"], parser_depth=limits["parser_depth"],
            collection_items=limits["collection_items"],
        )
        failures = validate_invariants(policy, "routingPolicy", provenance=provenance, route_limits=limits)
        failures += validate_invariants(provenance, "provenanceManifest", policy=policy)
        request_failures = validate_invariants(request, "routeRequest", policy=policy, provenance=provenance)
        if any(item in _RESOURCE_FAILURES for item in failures) or "query UTF-8 byte limit" in request_failures:
            raise RouteProtocolError("resource_exhausted")
        if failures or request_failures: raise RouteProtocolError("invalid_policy")
        source_coordinates = _sources(policy, provenance, _safe_text(owner_repo_id))
        repository = _GitRepository.open(owner_repo_root)
        repository.verify(source_coordinates, limits["policy_bytes"])
        _race_hook("before_final_capture_recheck")
        root.recheck(); policy_file.recheck(); provenance_file.recheck()
        repository.recheck()
        return CapturedPolicyBundle(
            policy, provenance, policy_file.raw, provenance_file.raw,
            policy_file.digest, provenance_file.digest, root, policy_file, provenance_file, repository,
        )
    except (RouteProtocolError, OSError, KeyError, TypeError, ValueError, ProtocolError) as exc:
        for captured in (policy_file, provenance_file, root, repository):
            if captured: captured.close()
        if isinstance(exc, RouteProtocolError): raise
        raise RouteProtocolError("internal") from exc
