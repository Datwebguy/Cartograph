"""Gate behaviour inside the REAL Duck ToolAgent.analyze loop (scripted LLM, fake 1-D env).

Skipped when the Duck harness is not importable (put ARC3-Inference on PYTHONPATH).
"""
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("inference.agent.tool_agent")

from inference.agent.runtime_state import (  # noqa: E402
    RUNTIME_STATE_FILENAME, Frame, HistoryEntry, write_runtime_state)

from cartograph.agent import WM_TOOL, CartographToolAgent, history_from_state  # noqa: E402
from cartograph.testing import scripted  # noqa: E402

# Harness legend (ARC_COLOR_CHARS): 'W' = color 0, 'B' = color 5. Grid is 4x4; a white cursor moves on the top row.
GOOD = '''
def transition(state, action):
    c = state[0].index("W")
    if action == "RIGHT" and c < 3: c += 1
    elif action == "LEFT" and c > 0: c -= 1
    row = ["B"] * 4
    row[c] = "W"
    return ("".join(row), state[1], state[2], state[3])
'''
WRONG = "def transition(state, action):\n    return state\n"


class FakeEnv:
    def __init__(self, state_path: Path):
        self.state_path, self.col, self.left_step, self.hist = state_path, 0, 1, []
        self._record("")

    def _grid(self):
        g = [[5] * 4 for _ in range(4)]
        g[0][self.col] = 0
        return tuple(tuple(r) for r in g)

    def _record(self, action):
        frame = Frame(self._grid(), max(0, len(self.hist)), 1)
        self.hist.append(HistoryEntry(action=action, frame=frame))
        write_runtime_state(self.state_path, current_frame=frame, history=self.hist)

    def step_env(self, arguments):
        for a in arguments["actions"]:
            name = a["action"]
            if name == "RIGHT":
                self.col = min(3, self.col + 1)
            elif name == "LEFT":
                self.col = max(0, self.col - self.left_step)
            self._record(name)
        names = [x["action"] for x in arguments["actions"]]
        return {"executed": True, "action_num": len(self.hist) - 1, "level": 1, "score": 0, "reward": 0.0,
                "state": "NOT_FINISHED", "valid_actions": ["LEFT", "RIGHT"], "board_changed": True,
                "done": False, "level_completed": False, "game_over": False, "run_complete": False,
                "executed_actions": names, "action_display": names[-1], "action_name": names[-1],
                "action_data": {}, "batch_index": 1, "batch_size": len(names)}


def _make(tmp_path, policy):
    agent = scripted(CartographToolAgent, policy)(
        model="local", base_url="http://127.0.0.1:1/v1", provider="vllm", workspace_root=tmp_path / "ws")
    state_path = tmp_path / f"g_{RUNTIME_STATE_FILENAME}"
    return agent, FakeEnv(state_path), state_path


def _turn(agent, env, state_path, n):
    return agent.analyze(state_path, n, valid_actions=["LEFT", "RIGHT"], step_env=env.step_env)


def _last_tool_result(agent) -> str:
    return next(m["content"] for m in reversed(agent.scripted_messages) if m.get("role") == "tool")


def test_stub_gate_is_no_model_then_full_cycle(tmp_path):
    seen: dict = {}
    calls = {"n": 0}

    def policy(agent, prompt):
        i, calls["n"] = calls["n"], calls["n"] + 1
        ws = agent._cg_ws
        if i == 0:
            return "", [("python", {"code": "action(['RIGHT'])"})]
        if i == 1:
            return "", [(WM_TOOL, {"code": WRONG})]
        if i == 2:
            seen["gate_after_wrong"] = ws.gate()
            return "", [("python", {"code": "print(transition(('BBBB',)*4, 'RIGHT'))"})]
        if i == 3:
            seen["python_while_unverified"] = _last_tool_result(agent)
            return "", [(WM_TOOL, {"code": GOOD})]
        if i == 4:
            seen["gate_after_good"] = ws.gate()
            return "", [("python", {"code": "s = to_state(current_frame)\nprint(transition(s, 'RIGHT')[0])\naction(['RIGHT'])"})]
        return "", [("python", {"code": "action(['LEFT'])"})]

    agent, env, sp = _make(tmp_path, policy)
    assert _turn(agent, env, sp, 0).step_executed
    ws = agent._cg_ws
    assert ws.gate() == "NO_MODEL"                       # stub only; the action was issued without a model
    assert _turn(agent, env, sp, 1).step_executed        # wrong model -> NameError probe -> good model -> act
    assert seen["gate_after_wrong"] == "UNVERIFIED"
    assert "NameError" in seen["python_while_unverified"] or "not defined" in seen["python_while_unverified"]
    assert seen["gate_after_good"] == "VERIFIED"
    assert ws.gate() == "VERIFIED"                       # the action taken under planning still matches

    env.left_step = 2                                    # the world's rules change under the agent
    assert _turn(agent, env, sp, 2).step_executed        # LEFT now moves 2 cells, the model says 1
    assert ws.gate() == "UNVERIFIED"
    assert "Planning inside the model is DISABLED" in agent._build_user_prompt(3, valid_actions=["LEFT"])

    log = [json.loads(line) for line in ws.log_path.read_text().splitlines()]
    actions = [r for r in log if r["event"] == "action"]
    assert [a["gate_at_issue"] for a in actions] == ["NO_MODEL", "VERIFIED", "VERIFIED"]
    edits = [r for r in log if r["event"] == "verify" and r["trigger"] == "edit"]
    assert [e["verified"] for e in edits] == [False, True]
    post = [r for r in log if r["event"] == "verify" and r["trigger"] == "action"]
    assert [p["verified"] for p in post] == [False, True, False]   # stub, good model, rules changed


def test_prompt_contains_gate_regime_and_model_source(tmp_path):
    agent, env, sp = _make(tmp_path, lambda a, p: ("", [("python", {"code": "action(['RIGHT'])"})]))
    _turn(agent, env, sp, 0)
    ws = agent._cg_ws
    assert "Planning inside the model is DISABLED" in agent._build_user_prompt(1, valid_actions=["RIGHT"])
    ws.write(GOOD)
    ws.verify(history_from_state(sp), event="edit")
    p = agent._build_user_prompt(1, valid_actions=["LEFT", "RIGHT"])
    assert "== Cartograph world model: VERIFIED ==" in p and "def transition" in p
    assert "Planning is ENABLED" in p


def test_sandbox_builtin_allowlist_has_not_drifted():
    """The verifier's allowlist must stay a subset of the real Duck sandbox's."""
    from inference.agent import python_tool_sandbox as sb
    from cartograph.verifier import SAFE_BUILTINS, SAFE_MODULES
    src = sb._SANDBOX_BOOTSTRAP
    harness_b = set(re.findall(r'"(\w+)"', re.search(r"SAFE_BUILTINS = \{(.*?)\n    \}", src, re.S).group(1)))
    harness_m = set(re.findall(r'"(\w+)"', re.search(r"SAFE_MODULES = \{(.*?)\n    \}", src, re.S).group(1)))
    assert set(SAFE_BUILTINS) <= harness_b, set(SAFE_BUILTINS) - harness_b
    assert set(SAFE_MODULES) <= harness_m, set(SAFE_MODULES) - harness_m
