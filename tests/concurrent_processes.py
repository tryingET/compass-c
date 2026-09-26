"""Release separate operating-system processes into one COMPASS-C call together.

Thread-level races share one interpreter; these workers share only the notebook
file, as a CLI, portable script and MCP server do on one machine.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

_PRELUDE = """
import json
import sys
import time
from pathlib import Path


def released():
    Path(sys.argv[1]).touch()
    deadline = time.monotonic() + 30
    while not Path(sys.argv[2]).exists():
        if time.monotonic() > deadline:
            raise SystemExit("start gate timed out")
        time.sleep(0.001)


arguments = json.loads(sys.argv[3])
"""


def race(directory: Path, body: str, arguments: list[dict]) -> list[dict]:
    """Run ``body`` once per argument set; ``released()`` waits for the shared gate.

    Each worker must print one JSON object. Imports belong before ``released()`` so
    the processes contend on the notebook operation rather than interpreter start-up.
    """
    gate = directory / "release"
    workers = []
    for index, values in enumerate(arguments):
        ready = directory / f"ready-{index}"
        command = [sys.executable, "-B", "-c", _PRELUDE + body, str(ready), str(gate)]
        workers.append(
            (
                ready,
                subprocess.Popen(  # ubs:ignore -- this interpreter running test-defined code
                    [*command, json.dumps(values)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                ),
            )
        )
    try:
        deadline = time.monotonic() + 30
        while not all(ready.exists() for ready, _ in workers):
            assert all(process.poll() is None for _, process in workers), "a worker exited early"
            assert time.monotonic() < deadline, "workers did not reach the start gate"
            time.sleep(0.005)
        gate.touch()
        results = []
        for _, process in workers:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            assert not stderr, stderr
            results.append(json.loads(stdout))
        return results
    finally:
        for _, process in workers:
            if process.poll() is None:
                process.kill()
                process.communicate()
