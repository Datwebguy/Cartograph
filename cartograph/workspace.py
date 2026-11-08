"""Per-game workspace: the persistent ``world_model.py``, its verification state,
and an append-only JSONL log of every verification and every environment action.

Harness-independent. One ``WorldModelWorkspace`` per game; the directory (and so the
file) survives across all agent turns of that game and is never overwritten by the
harness - only by the agent, through ``write()``.
"""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any, Sequence

from .verifier import HistoryItem, VerificationResult, verify_exact_replay

MODEL_FILENAME = "world_model.py"
LOG_FILENAME = "verification_log.jsonl"
DEFAULT_MAX_MODEL_CHARS = 8000   # the full file is shown to the agent every turn

# Created at game start so the file always exists; it can never verify (it raises).
STUB_SOURCE = '''\
# world_model.py - persistent across turns. Replace via the world_model_write tool.
# Contract: transition(state, action) -> next_state
#   state  : tuple of row strings, one letter per cell (same letters as current_frame.ascii)
#   action : action string as in history, e.g. "UP", "SPACE", "MOUSE(row=3, col=4)"
def transition(state, action):
    raise RuntimeError("world model not written yet")
'''

# Gate states
NO_MODEL, UNVERIFIED, VERIFIED = "NO_MODEL", "UNVERIFIED", "VERIFIED"


class WorldModelWorkspace:
    def __init__(self, root: Path, game_id: str = "", *, strict: bool = False,
                 min_checked: int = 1, timeout_s: float = 20.0,
                 max_model_chars: int = DEFAULT_MAX_MODEL_CHARS) -> None:
        self.root = Path(root)
        self.game_id = game_id
        self.strict, self.min_checked, self.timeout_s = strict, min_checked, timeout_s
        self.max_model_chars = max_model_chars
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / MODEL_FILENAME
        self.log_path = self.root / LOG_FILENAME
        if not self.path.exists():          # persistence: never clobber an existing model
            self.path.write_text(STUB_SOURCE, encoding="utf-8")
        self.last: VerificationResult | None = None

    # --- model file ---------------------------------------------------------
    def source(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def has_model(self) -> bool:
        return self.source().strip() != STUB_SOURCE.strip()

    def write(self, code: str) -> str | None:
        """Replace the model file. Returns an error string (file untouched) or None."""
        if not isinstance(code, str) or not code.strip():
            return "code must be a non-empty string"
        if len(code) > self.max_model_chars:
            return (f"world model is {len(code)} chars; the limit is {self.max_model_chars} "
                    "(the full file is shown to you every turn). Make it more compact "
                    "(e.g. store sparse diffs/rules, not whole frames).")
        try:
            tree = ast.parse(code, filename=MODEL_FILENAME)
        except SyntaxError as exc:
            return f"syntax error: {exc}"
        if not any(isinstance(n, ast.FunctionDef) and n.name == "transition" for n in tree.body):
            return "world model must define a top-level `def transition(state, action):`"
        tmp = self.path.with_suffix(".py.tmp")
        tmp.write_text(code if code.endswith("\n") else code + "\n", encoding="utf-8")
        tmp.replace(self.path)               # atomic: no half-written model
        return None

    # --- verification & gate -----------------------------------------------
    def verify(self, history: Sequence[HistoryItem], *, event: str,
               action_count: int = 0) -> VerificationResult:
        """Exact-replay the full history through the current file; log the result."""
        res = verify_exact_replay(self.source(), history, strict=self.strict,
                                  min_checked=self.min_checked, timeout_s=self.timeout_s)
        self.last = res
        self._log({"event": "verify", "trigger": event, "action_count": action_count,
                   "has_model": self.has_model(), "gate": self.gate(), **res.to_dict()})
        return res

    def gate(self) -> str:
        """VERIFIED only if the latest replay of the current file passed.
        NO_MODEL while the agent has never written one. Planning is enabled iff VERIFIED."""
        if not self.has_model():
            return NO_MODEL
        return VERIFIED if (self.last is not None and self.last.verified) else UNVERIFIED

    def planning_enabled(self) -> bool:
        return self.gate() == VERIFIED

    def log_actions(self, executed_actions: list[str], *, gate_at_issue: str,
                    action_count: int, payload: dict[str, Any]) -> None:
        self._log({"event": "action", "executed_actions": executed_actions,
                   "gate_at_issue": gate_at_issue, "action_count": action_count,
                   "level": payload.get("level"), "score": payload.get("score"),
                   "level_completed": bool(payload.get("level_completed")),
                   "game_over": bool(payload.get("game_over")),
                   "run_complete": bool(payload.get("run_complete"))})

    def log_turn(self, action_num: int) -> None:
        """One record per agent turn: which regime (gate) the turn started in."""
        self._log({"event": "turn", "action_count": action_num, "gate": self.gate()})

    def _log(self, record: dict[str, Any]) -> None:
        record = {"t": round(time.time(), 3), "game": self.game_id, **record}
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
