"""CartographToolAgent: Duck's ToolAgent + persistent world model + verification gate.

This is a SUBCLASS, not a patch: no file of the Duck harness is modified. It is
plugged in through the harness's existing ``HarnessSolver.analyzer_factory`` hook
(see ``make_analyzer_factory``).

What it adds, mapped to the build spec:
  1. persistent world_model.py ...... ``WorldModelWorkspace`` (file created at game
                                      start, survives all turns, edited only through
                                      the new ``world_model_write`` tool)
  2. interface ...................... ``transition(state, action) -> next_state``
  3. exact-replay verifier .......... run (a) after every ``world_model_write`` and
                                      (b) after every ``action(...)`` call, by
                                      wrapping the ``step_env`` callback
  4. gate ........................... VERIFIED  -> the model is injected into the python
                                                   tool and the prompt tells the agent to
                                                   plan inside it
                                      otherwise -> the unmodified Duck REPL loop; the
                                                   model is NOT available to python code
Everything is local; there are no network calls in anything added here.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from inference.agent.runtime_state import RUNTIME_STATE_FILENAME, load_runtime_state
from inference.agent.tool_agent import ToolAgent, _ToolDispatchResult

from .verifier import HistoryItem, SAFE_MODULES
from .workspace import NO_MODEL, UNVERIFIED, VERIFIED, WorldModelWorkspace

log = logging.getLogger(__name__)

WM_TOOL = "world_model_write"

_WM_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": WM_TOOL,
        "description": (
            "Write the persistent world model: the COMPLETE contents of world_model.py (replaces the file). "
            "It must define `def transition(state, action):` returning the next state. `state` is a tuple of row "
            "strings, one letter per cell (the same letters as `current_frame.ascii`); `action` is the action "
            "string as shown in history, e.g. 'UP', 'SPACE', 'MOUSE(row=3, col=4)'. It must be deterministic and "
            "reproduce EVERY cell exactly, including timer/HUD bars. Level changes and RESET are not predicted "
            "(the verifier re-anchors on the observed frame there). Allowed imports: "
            + ", ".join(SAFE_MODULES) + ". The model is immediately replayed against the full recorded history "
            "and the result is returned."
        ),
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Full contents of world_model.py."}},
            "required": ["code"],
        },
    },
}

SYSTEM_ADDENDUM = (
    "\n\nCartograph world-model rules (these amend the tool rules above - you have TWO tools):\n"
    f"- `python`: as described above.\n"
    f"- `{WM_TOOL}(code)`: writes the persistent file world_model.py (a `transition(state, action)` function).\n"
    "- After every edit and after every `action(...)` call, the harness replays the ENTIRE recorded history "
    "through world_model.py. The model is VERIFIED only if every checked transition matches the observed frame "
    "cell for cell.\n"
    "- Only a VERIFIED model is made available inside the `python` tool (as `transition` and `to_state`), and only "
    "then should you plan by searching inside it. If it is not verified, keep using the normal inspect-probe-act "
    "loop, and use the failure report to fix the model.\n"
)

# Defined in the python tool only while the model is verified (after the model source).
_PRELUDE_HELPERS = (
    "\ndef to_state(frame):\n"
    "    return tuple(frame.ascii.split('\\n'))\n"
)


def history_from_state(state_path: Path) -> list[HistoryItem]:
    """The harness's recorded history as verifier input: (action, rows, level)."""
    _, entries = load_runtime_state(state_path)
    return [(e.action, tuple(e.frame.ascii.split("\n")), e.frame.level) for e in entries]


def _compact(res) -> dict[str, Any]:
    out = {"verified": res.verified, "n_checked": res.n_checked, "n_anchored": res.n_anchored,
           "reason": res.reason}
    if res.first_mismatch:
        out["first_mismatch"] = res.first_mismatch
    return out


class CartographToolAgent(ToolAgent):
    def __init__(self, *args: Any, workspace_root: str | Path | None = None, strict: bool = False,
                 min_checked: int = 1, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cg_root = Path(workspace_root) if workspace_root else None
        self._cg_strict, self._cg_min_checked = strict, min_checked
        self._cg_ws: WorldModelWorkspace | None = None
        self._cg_state_path: Path | None = None
        self._system_prompt += SYSTEM_ADDENDUM

    # --- workspace ----------------------------------------------------------
    def _workspace(self, state_path: Path) -> WorldModelWorkspace:
        if self._cg_ws is None:
            stem = state_path.name.removesuffix(f"_{RUNTIME_STATE_FILENAME}")
            root = (self._cg_root or state_path.parent / "cartograph") / stem
            self._cg_ws = WorldModelWorkspace(root, game_id=stem, strict=self._cg_strict,
                                              min_checked=self._cg_min_checked)
        return self._cg_ws

    # --- turn entry: wrap step_env so every action triggers verification ----
    def analyze(self, state_path: Path, action_num: int, *args: Any, **kwargs: Any):
        self._cg_state_path = state_path
        if state_path.exists():
            ws = self._workspace(state_path)
            history = history_from_state(state_path)
            if ws.last is None:        # first turn (or resumed game): establish the gate
                ws.verify(history, event="init", action_count=max(0, len(history) - 1))
            ws.log_turn(action_num)
            step_env = kwargs.get("step_env")
            if step_env is not None:
                kwargs["step_env"] = self._wrap_step_env(state_path, ws, step_env)
        return super().analyze(state_path, action_num, *args, **kwargs)

    def _wrap_step_env(self, state_path: Path, ws: WorldModelWorkspace,
                       step_env: Callable[[dict[str, Any]], dict[str, Any]]):
        def wrapped(arguments: dict[str, Any]) -> dict[str, Any]:
            gate_at_issue = ws.gate()                      # state when the agent issued the action
            payload = step_env(arguments)
            try:
                if isinstance(payload, dict) and payload.get("executed"):
                    history = history_from_state(state_path)   # already includes the new frame(s)
                    n = max(0, len(history) - 1)
                    ws.log_actions(list(payload.get("executed_actions") or []),
                                   gate_at_issue=gate_at_issue, action_count=n, payload=payload)
                    ws.verify(history, event="action", action_count=n)
            except Exception:                              # bookkeeping must never break the game
                log.exception("cartograph: post-action verification failed to run")
            return payload
        return wrapped

    # --- tools --------------------------------------------------------------
    def _tools(self, state_path: Path) -> list[dict[str, Any]]:
        return [*super()._tools(state_path), _WM_TOOL_SPEC]

    def _dispatch_tool(self, state_path: Path, name: str, arguments: dict[str, Any]) -> _ToolDispatchResult:
        if name != WM_TOOL:
            return super()._dispatch_tool(state_path, name, arguments)
        ws = self._workspace(state_path)
        err = ws.write(arguments.get("code"))
        if err:
            return _ToolDispatchResult(json.dumps({"tool": WM_TOOL, "written": False, "error": err}, indent=2))
        history = history_from_state(state_path)
        res = ws.verify(history, event="edit", action_count=max(0, len(history) - 1))
        return _ToolDispatchResult(json.dumps(
            {"tool": WM_TOOL, "written": True, "gate": ws.gate(),
             "planning_enabled": ws.planning_enabled(), **_compact(res)}, indent=2))

    def _run_python_tool(self, state_path: Path, arguments: dict[str, Any]) -> _ToolDispatchResult:
        # GATE (mechanical, not just a prompt): the model is only defined inside the python
        # tool while it is verified. Unverified => `transition` is a NameError there.
        ws = self._workspace(state_path)
        if ws.planning_enabled():
            arguments = {**arguments, "code": self._prelude(ws) + str(arguments.get("code", ""))}
        return super()._run_python_tool(state_path, arguments)

    @staticmethod
    def _prelude(ws: WorldModelWorkspace) -> str:
        return ws.source().rstrip("\n") + "\n" + _PRELUDE_HELPERS + "\n"

    # --- prompt: tell the agent which regime it is in -----------------------
    def _build_user_prompt(self, *args: Any, **kwargs: Any) -> str:
        prompt = super()._build_user_prompt(*args, **kwargs)
        ws = self._cg_ws
        if ws is None:
            return prompt
        gate, last = ws.gate(), ws.last
        lines = ["", f"== Cartograph world model: {gate} =="]
        if gate == VERIFIED:
            offset = self._prelude(ws).count("\n")
            lines += [
                f"world_model.py exactly reproduces all {last.n_checked} checked transitions of this game "
                f"({last.n_anchored} level-change/RESET steps re-anchored on the observed frame).",
                "Planning is ENABLED: in the `python` tool `transition(state, action)` and `to_state(frame)` are "
                "predefined (state = tuple of row strings). Plan the next action(s) by searching inside the model "
                "(BFS/DFS/greedy rollouts, e.g. `s = to_state(current_frame)`), then execute them with `action(...)`.",
                f"Line numbers in python-tool errors are offset by {offset} while the model is injected.",
                "If reality ever diverges from the model it is marked UNVERIFIED automatically and planning is disabled.",
            ]
        else:
            lines += [
                "Planning inside the model is DISABLED (`transition` is not available in the python tool). "
                "Use the normal loop: inspect, probe, act.",
                f"When you understand the dynamics, write/refine the model with `{WM_TOOL}`; it is re-verified "
                "against the full history immediately and after every action.",
            ]
            if gate == UNVERIFIED and last is not None:
                lines.append(f"Last verification failed: {last.reason}")
                if last.first_mismatch and last.first_mismatch.get("diffs"):
                    lines.append("First differing cells (row, col, observed, predicted): "
                                 + json.dumps(last.first_mismatch["diffs"]))
        if gate != NO_MODEL:
            lines += ["Current world_model.py:", "```python", ws.source().rstrip("\n"), "```"]
        return prompt + "\n".join(lines)


def make_analyzer_factory(**agent_kwargs: Any) -> Callable[[Any, int], Any]:
    """For ``HarnessSolver(analyzer_factory=...)``: one CartographToolAgent per game.

    ``agent_kwargs`` are forwarded to ``ToolAgent`` (model, timeout, base_url, api_key,
    provider, ...) plus Cartograph's own ``workspace_root``/``strict``/``min_checked``.
    """
    def factory(game: Any, index: int) -> CartographToolAgent:
        return CartographToolAgent(**agent_kwargs)
    return factory
