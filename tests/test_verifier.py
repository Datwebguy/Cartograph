"""Verifier + workspace tests. No Duck harness needed."""
from pathlib import Path

import pytest

from cartograph.verifier import verify_exact_replay
from cartograph.workspace import NO_MODEL, STUB_SOURCE, UNVERIFIED, VERIFIED, WorldModelWorkspace

# A 3x3 world: "X" is a cursor on a "." background; LEFT/RIGHT move it along the top row.
def _frame(col):
    row = ["."] * 3
    row[col] = "X"
    return ("".join(row), "...", "...")


GOOD = '''
def transition(state, action):
    top = state[0]
    c = top.index("X")
    if action == "RIGHT" and c < 2: c += 1
    elif action == "LEFT" and c > 0: c -= 1
    row = ["."] * 3
    row[c] = "X"
    return ("".join(row), state[1], state[2])
'''

# initial, RIGHT, RIGHT, LEFT  (level 1 throughout)
HIST = [("", _frame(0), 1), ("RIGHT", _frame(1), 1), ("RIGHT", _frame(2), 1), ("LEFT", _frame(1), 1)]


def test_correct_model_verifies():
    r = verify_exact_replay(GOOD, HIST)
    assert r.verified and r.n_checked == 3 and r.n_anchored == 0 and r.error is None


def test_wrong_model_fails_with_first_mismatch():
    bad = GOOD.replace('action == "LEFT" and c > 0: c -= 1', 'action == "LEFT" and c > 0: c -= 2')
    r = verify_exact_replay(bad, HIST)
    assert not r.verified
    m = r.first_mismatch
    assert m["kind"] == "cells" and m["index"] == 3 and m["action"] == "LEFT" and m["n_diff"] == 2


def test_identity_model_fails():
    r = verify_exact_replay("def transition(s, a):\n    return s\n", HIST)
    assert not r.verified and r.first_mismatch["index"] == 1


def test_vacuous_replay_is_not_verified():
    r = verify_exact_replay(GOOD, HIST[:1])           # no transitions at all
    assert not r.verified and "vacuous" in r.reason


def test_stub_never_verifies():
    r = verify_exact_replay(STUB_SOURCE, HIST)
    assert not r.verified and "not written yet" in (r.error or "")


def test_exception_wrong_type_and_missing_function():
    assert "raised" in verify_exact_replay("def transition(s, a):\n    return 1/0\n", HIST).error
    r = verify_exact_replay("def transition(s, a):\n    return 'abc'\n", HIST)
    assert not r.verified and r.first_mismatch["kind"] == "bad_return_type"
    assert not verify_exact_replay("x = 1\n", HIST).verified


def test_shape_mismatch():
    r = verify_exact_replay("def transition(s, a):\n    return ('..',)\n", HIST)
    assert r.first_mismatch["kind"] == "shape"


def test_timeout_is_a_failure_not_a_hang():
    r = verify_exact_replay("def transition(s, a):\n    while True: pass\n", HIST, timeout_s=1)
    assert not r.verified and r.error


def test_import_allowlist_and_print_safety():
    r = verify_exact_replay("import os\ndef transition(s, a):\n    return s\n", HIST)
    assert not r.verified and "not allowed" in r.error
    noisy = "import math\n" + GOOD.replace("    top = state[0]", "    print('noise')\n    top = state[0]")
    assert verify_exact_replay(noisy, HIST).verified          # print() must not corrupt the result


def test_level_change_and_reset_are_anchored_not_checked():
    hist = HIST + [("RIGHT", _frame(2), 2),                   # level 1 -> 2: new level layout
                   ("LEFT", _frame(1), 2),                    # checked on the new level
                   ("RESET", _frame(0), 2)]                   # RESET: anchored
    r = verify_exact_replay(GOOD, hist)
    assert r.verified and r.n_anchored == 2 and r.n_checked == 4
    # The model predicts frame(2)->RIGHT clamp, observed new-level frame(2): equal here, so make them differ:
    hist2 = HIST + [("RIGHT", ("X..", "...", "..."), 2)]
    assert verify_exact_replay(GOOD, hist2).verified          # anchored, so not held against the model
    assert not verify_exact_replay(GOOD, hist2, strict=True).verified   # strict checks it


def test_min_checked_threshold():
    assert not verify_exact_replay(GOOD, HIST, min_checked=4).verified


# --- workspace ------------------------------------------------------------------
def test_workspace_persistence_gate_and_log(tmp_path: Path):
    ws = WorldModelWorkspace(tmp_path / "g1", "g1")
    assert ws.path.exists() and ws.gate() == NO_MODEL
    assert ws.write("def transition(state, action):\n    return state\n") is None
    assert ws.verify(HIST, event="edit").verified is False and ws.gate() == UNVERIFIED
    assert not ws.planning_enabled()
    assert ws.write(GOOD) is None
    assert ws.verify(HIST, event="edit").verified and ws.gate() == VERIFIED and ws.planning_enabled()
    # persistence across "turns"/restarts: a new object on the same dir keeps the model
    ws2 = WorldModelWorkspace(tmp_path / "g1", "g1")
    assert ws2.source().strip() == GOOD.strip() and ws2.gate() == UNVERIFIED   # must re-verify first
    ws2.verify(HIST, event="init")
    assert ws2.gate() == VERIFIED
    lines = [l for l in (tmp_path / "g1" / "verification_log.jsonl").read_text().splitlines()]
    assert len(lines) == 3


def test_workspace_rejects_bad_writes(tmp_path: Path):
    ws = WorldModelWorkspace(tmp_path / "g", "g", max_model_chars=50)
    assert "syntax" in ws.write("def transition(:\n")
    assert "transition" in ws.write("x = 1\n")
    assert "limit" in ws.write("def transition(s, a):\n    return s\n" + "# pad\n" * 20)
    assert ws.source() == STUB_SOURCE                  # failed writes leave the file untouched
