"""Summarise per-game ``verification_log.jsonl`` files into the numbers reported in the paper.

Definitions (all computed from the logs, nothing estimated):
  actions_executed          environment actions issued (sum over `action` events)
  levels_completed          max `score` (levels_completed) seen in the action events
  model_edits / _verified   world_model_write calls / those whose replay verified
  post_action_checks        replays run after an action, ONLY where a model had been written
                            (checks against the unwritten stub are counted in `checks_without_model`)
  post_action_verified      of those, the replays that verified
  verification_rate         post_action_verified / post_action_checks (None if no checks)
  actions_by_gate_at_issue  gate state (NO_MODEL / UNVERIFIED / VERIFIED) when each action batch
                            was issued; VERIFIED means planning inside the model was enabled
  turns_by_gate             same, per agent turn
  first_verified_at_action  action count at the first successful replay (None if never)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GATES = ("NO_MODEL", "UNVERIFIED", "VERIFIED")


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarise_game(log: list[dict[str, Any]]) -> dict[str, Any]:
    acts = [r for r in log if r["event"] == "action"]
    verifies = [r for r in log if r["event"] == "verify"]
    edits = [r for r in verifies if r["trigger"] == "edit"]
    post_all = [r for r in verifies if r["trigger"] == "action"]
    post = [r for r in post_all if r["has_model"]]
    turns = [r for r in log if r["event"] == "turn"]
    first_ok = next((r["action_count"] for r in verifies if r["verified"]), None)
    return {
        "actions_executed": sum(len(a["executed_actions"]) for a in acts),
        "levels_completed": max([a.get("score") or 0 for a in acts] or [0]),
        "model_edits": len(edits),
        "model_edits_verified": sum(bool(e["verified"]) for e in edits),
        "post_action_checks": len(post),
        "post_action_verified": sum(bool(p["verified"]) for p in post),
        "checks_without_model": len(post_all) - len(post),
        "verification_rate": (sum(bool(p["verified"]) for p in post) / len(post)) if post else None,
        "actions_by_gate_at_issue": {g: sum(a["gate_at_issue"] == g for a in acts) for g in GATES},
        "turns_by_gate": {g: sum(t["gate"] == g for t in turns) for g in GATES},
        "first_verified_at_action": first_ok,
    }


def summarise_dir(root: Path) -> dict[str, Any]:
    """``root`` holds one sub-directory per game run, each with a verification_log.jsonl."""
    per_game = {d.name: summarise_game(_load(d / "verification_log.jsonl"))
                for d in sorted(Path(root).iterdir()) if (d / "verification_log.jsonl").exists()}
    post = sum(g["post_action_checks"] for g in per_game.values())
    ok = sum(g["post_action_verified"] for g in per_game.values())
    return {
        "games_attempted": len(per_game),
        "levels_completed_total": sum(g["levels_completed"] for g in per_game.values()),
        "actions_executed_total": sum(g["actions_executed"] for g in per_game.values()),
        "post_action_checks_total": post,
        "post_action_verified_total": ok,
        "verification_rate_overall": (ok / post) if post else None,
        "per_game": per_game,
    }
