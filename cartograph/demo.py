"""Scripted stand-in for the LLM, used to demonstrate the full Cartograph loop without a GPU.

Plays real games through the real Duck harness and CartographToolAgent; only the model's
decisions are scripted. The scripted "world model" is a table of the transitions seen so far:
exact on history, stale one action later. It exercises every gate transition (no model ->
rejected wrong model -> verified -> planning enabled -> stale -> unverified ...) on real engine
data. It is a pipeline demonstration, NOT an agent result.
"""
from __future__ import annotations

from typing import Any, Callable

from .agent import WM_TOOL, CartographToolAgent, history_from_state
from .testing import scripted

SIZE_CAP = 7400   # stay under the 8000-char world-model limit


def _h(state):      # MUST equal the _h embedded in the generated model source below
    x = 7
    for row in state:
        for ch in row:
            x = (x * 131 + ord(ch)) % 1000000007
    return x


def table_model(history) -> str:
    """Diff-table 'model' of the transitions the verifier will check (anchors skipped)."""
    entries = []
    for i in range(1, len(history)):
        action, rows, level = history[i]
        prev_rows, prev_level = history[i - 1][1], history[i - 1][2]
        if level != prev_level or action.strip().upper() == "RESET":
            continue
        d = "".join(f"{r:02d}{c:02d}{rows[r][c]}" for r in range(len(rows)) for c in range(len(rows[r]))
                    if rows[r][c] != prev_rows[r][c])
        entries.append(((action, _h(prev_rows)), d))
    table, size = {}, 0
    for k, v in entries:
        size += len(repr(k)) + len(v) + 8
        if size > SIZE_CAP:
            break
        table[k] = v
    return (
        "def _h(state):\n    x = 7\n    for row in state:\n        for ch in row:\n"
        "            x = (x * 131 + ord(ch)) % 1000000007\n    return x\n"
        f"T = {table!r}\n"
        "def transition(state, action):\n    d = T[(action, _h(state))]\n"
        "    rows = [list(r) for r in state]\n    for i in range(0, len(d), 5):\n"
        "        rows[int(d[i:i+2])][int(d[i+2:i+4])] = d[i+4]\n"
        "    return tuple(''.join(r) for r in rows)\n"
    )


IDENTITY = "def transition(state, action):\n    return state\n"
CLICKS = [(32, 32), (10, 10), (50, 50), (20, 44), (44, 20)]


class Policy:
    """Per-game scripted stand-in for the LLM. One executed action per turn."""
    EXPLORE = 3

    # The Duck harness can only issue these model-facing names. It may still *advertise* others
    # (e.g. ACTION7 on lf52) but then answers `executed: false`; a real LLM just avoids them.
    ISSUABLE = {"UP", "DOWN", "LEFT", "RIGHT", "SPACE", "MOUSE"}

    def __init__(self):
        self.stage, self.cycle, self.calls = 0, 0, 0

    def _act(self, agent, n):
        names = [a for a in agent._current_valid_actions if a in self.ISSUABLE] or ["UP"]
        a = names[n % len(names)]
        if a == "MOUSE":
            r, c = CLICKS[n % len(CLICKS)]
            return f"action([{{'action': 'MOUSE', 'row': {r}, 'col': {c}}}])"
        return f"action(['{a}'])"

    def __call__(self, agent, prompt):
        self.calls += 1
        if self.calls > 300:                      # fail fast instead of spinning if no action executes
            raise RuntimeError("scripted policy runaway: no progress")
        hist = history_from_state(agent._cg_state_path)
        n = len(hist) - 1
        if n < self.EXPLORE:                                   # plain Duck loop, no model yet
            return "", [("python", {"code": self._act(agent, n)})]
        if self.stage == 0:
            self.stage = 1
            if self.cycle == 0:                                # first model is deliberately wrong
                return "", [(WM_TOOL, {"code": IDENTITY})]
        if self.stage == 1:
            self.stage = 2
            return "", [(WM_TOOL, {"code": table_model(hist)})]
        if self.stage == 2:                                    # plan inside the model if (and only if) allowed
            self.stage = 3
            return "", [("python", {"code": (
                "try:\n    s = to_state(current_frame)\n    print('planning-enabled', len(s))\n"
                "except NameError:\n    print('planning-disabled')")})]
        self.stage, self.cycle = 0, self.cycle + 1
        return "", [("python", {"code": self._act(agent, n)})]


def make_demo_factory(**agent_kwargs: Any) -> Callable[[Any, int], Any]:
    """analyzer_factory for HarnessSolver: one scripted-policy CartographToolAgent per game."""
    agent_cls = scripted(CartographToolAgent, lambda agent, prompt: agent._policy(agent, prompt))

    def factory(game: Any, index: int) -> Any:
        agent = agent_cls(**agent_kwargs)
        agent._policy = Policy()
        return agent
    return factory
