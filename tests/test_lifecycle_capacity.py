"""A saved experiment must retain room for its observed evidence dependency."""

from pathlib import Path

import pytest

from compass_c import CompassError, Notebook
from compass_c.lifecycle import apply_observation, plan_experiment
from test_lifecycle import observation, parameters


@pytest.mark.parametrize("dependency_count", [63, 64])
def test_plan_reserves_a_dependency_link_for_its_observation(
    tmp_path: Path, dependency_count: int
) -> None:
    book = Notebook(tmp_path / "dependencies.sqlite3")
    did = book.start("Retain enough dependency capacity to finish the experiment")["decision_id"]
    dependencies = []
    for index in range(dependency_count):
        dependencies.append(
            book.record(did, index + 1, "assumption", f"Declared assumption {index}")["note_id"]
        )
    before = book.path.read_bytes()
    if dependency_count == 64:
        with pytest.raises(CompassError) as error:
            plan_experiment(book, did, dependency_count + 1, parameters(), dependencies)
        assert error.value.code == "CAPACITY"
        assert book.path.read_bytes() == before
    else:
        plan = plan_experiment(book, did, dependency_count + 1, parameters(), dependencies)
        result = apply_observation(
            book, plan["plan_id"], plan["revision"], "smoke", "event-at-boundary", observation()
        )
        notes = {note["id"]: note for note in book.get(did)["notes"]}
        assert notes[result["model_note_id"]]["depends_on"] == dependencies + [
            result["outcome_note_id"]
        ]
