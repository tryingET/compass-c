"""Opt-in installed-host checks, with network disabled and no model turn.

COMPASS_HOST_DOGFOOD=1 and PI_CODING_AGENT_PACKAGE must be set explicitly.
These tests never read real host credentials or replace existing installations.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from install_skill import file_map, install

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.environ.get("COMPASS_HOST_DOGFOOD") != "1", reason="Opt-in real installed host probes"
)


def environment(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    cwd = home / "project"
    cwd.mkdir()
    # Keep only executable/scratch resolution; no auth, proxies, model settings,
    # telemetry flags or real HOME. Each subprocess also has no network devices.
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "TMPDIR": str(tmp_path),
        "PI_CODING_AGENT_DIR": str(home / ".pi/agent"),
        "PI_OFFLINE": "1",
        "CODEX_HOME": str(home / ".codex"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
    }
    subprocess.run(["git", "init", "-q", str(cwd)], env=env, check=True)
    return home, cwd, env


def offline(command, *, cwd, env, input=None):
    result = subprocess.run(
        ["unshare", "--user", "--map-root-user", "--net", *command],
        cwd=cwd,
        env=env,
        input=input,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def install_cli(root, cwd):
    result = subprocess.run(
        [sys.executable, str(ROOT / "install_skill.py"), "--root", str(root)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    installed = json.loads(result.stdout)
    assert installed["installed"] and not installed["account_installation"]
    destination = Path(installed["destination"])
    assert file_map(destination) == file_map(ROOT / "skills/compass")
    receipt = json.loads((destination / ".install-receipt.json").read_text())
    assert receipt["publication"] is None  # Local install, not public-head verification.
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(destination / "scripts/compass.py"),
            "calculate",
            "bundle",
            "--parameters",
            '{"test_accuracy":0.95,"test_cost":3,"gain":100,"loss":400}',
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["data"]["result"]["pair_value"] == pytest.approx(20.25)
    return destination


@pytest.mark.parametrize("location", ["global", "project"])
def test_pi_discovery_resource_read_and_withdrawal(tmp_path, location):
    package = os.environ["PI_CODING_AGENT_PACKAGE"]
    home, cwd, env = environment(tmp_path)
    root = (home if location == "global" else cwd) / ".agents/skills"
    destination = install_cli(root, cwd)

    def probe(expected, trusted="true"):
        output = offline(
            [
                "node",
                str(ROOT / "scripts/dogfood_pi.mjs"),
                package,
                str(cwd),
                env["PI_CODING_AGENT_DIR"],
                expected,
                trusted,
            ],
            cwd=cwd,
            env=env,
        )
        return json.loads(output)

    if location == "project":
        assert probe("absent", "false")["compassCount"] == 0
    assert probe(str(destination / "SKILL.md"))["compassCount"] == 1
    # Every invocation is a new process; no cached or forced --skill injection.
    assert probe(str(destination / "SKILL.md"))["modelInvoked"] is False
    with pytest.raises(FileExistsError):
        install(root)
    shutil.move(str(destination), str(home / "withdrawn-compass"))
    assert probe("absent")["compassCount"] == 0


async def codex_requests(requests, cwd, env):
    # Protocol read from this installed client's generate-json-schema surface.
    # Keep stdin open until each response arrives: EOF is server shutdown.
    process = await asyncio.create_subprocess_exec(
        "unshare",
        "--user",
        "--map-root-user",
        "--net",
        "codex",
        "app-server",
        "-c",
        "analytics.enabled=false",
        "-c",
        "feedback.enabled=false",
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        for request in requests:
            process.stdin.write((json.dumps(request) + "\n").encode())
            await process.stdin.drain()
            if "id" not in request:
                continue
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=30)
                assert line, "Codex exited without answering the local discovery request"
                response = json.loads(line)
                if response.get("id") == request["id"]:
                    assert "error" not in response, response
                    break
        return response
    finally:
        if process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(process.communicate(), timeout=10)
        except TimeoutError:
            process.kill()
            await process.communicate()


def test_codex_local_discovery_and_withdrawal(tmp_path):
    home, cwd, env = environment(tmp_path)
    destination = install_cli(cwd / ".agents/skills", cwd)

    def probe():
        requests = [
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "compass-local-dogfood", "version": "1"},
                },
            },
            {"method": "initialized", "params": {}},
            {
                "id": 2,
                "method": "skills/list",
                "params": {
                    "cwds": [str(cwd)],
                    "forceReload": True,
                },
            },
        ]
        response = asyncio.run(codex_requests(requests, cwd, env))
        assert "error" not in response, response
        (entry,) = response["result"]["data"]
        assert entry["cwd"] == str(cwd)
        assert entry["errors"] == []
        return [skill for skill in entry["skills"] if skill["name"] == "compass"]

    (found,) = probe()
    assert found["path"] == str(destination / "SKILL.md")
    assert found["enabled"]
    shutil.move(str(destination), str(home / "withdrawn-compass"))
    assert probe() == []
