#!/usr/bin/env python
"""PLUMBING SMOKE TEST - not an agent evaluation.

Plays real public ARC-AGI-3 games through the REAL Duck HarnessSolver + TAAF Benchmark +
CartographToolAgent (real prompt building, tool dispatch, sandbox, verifier, gate, logs).
The ONLY thing replaced is the LLM HTTP call: a scripted policy stands in for the model,
so this runs on CPU with no GPU, no model and no network at play time.

The scripted "world model" is a table memorising the transitions seen so far. It is
exact on history by construction, then goes stale the moment the next unseen transition
is played. So the run exercises: NO_MODEL -> UNVERIFIED (wrong model) -> VERIFIED (planning
enabled, model injected into the python tool) -> UNVERIFIED (reality outran the model) ->
VERIFIED ... on real engine data. Numbers from it say NOTHING about LLM ability.

Run with the Duck harness venv:
  PYTHONPATH=<cartograph repo>:<duck-harness>/ARC3-Inference \
    <duck-harness>/ARC3-Inference/.venv/bin/python scripts/smoke_scripted_run.py \
      --env-dir <dir> --out <dir> --games ls20,lf52,dc22
Needs network ONLY for the one-time download of the public game files (--env-dir cache).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("ONLY_RESET_LEVELS", "true")          # same flag the Duck notebook sets
os.environ.setdefault("LOCAL_ANALYZER_MODEL_ID", "scripted-no-llm")
os.environ.setdefault("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:1/v1")

import arc_agi  # noqa: E402
import taaf.benchmark  # noqa: E402
import taaf.game_api  # noqa: E402
from inference.framework.solver import HarnessSolver  # noqa: E402

from cartograph.agent import WM_TOOL, CartographToolAgent, history_from_state  # noqa: E402
from cartograph.report import summarise_dir  # noqa: E402
from cartograph.testing import scripted  # noqa: E402

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


def fetch_games(env_dir: Path, wanted: list[str]) -> list[str]:
    """One-time download of public game files via the official toolkit (anonymous key)."""
    arcade = arc_agi.Arcade(environments_dir=str(env_dir))
    ids = {e.game_id.split("-")[0]: e.game_id for e in arcade.get_environments()}
    full = []
    for w in wanted:
        gid = ids[w]
        arcade.make(gid)
        full.append(gid)
    return full


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--games", default="ls20,lf52,dc22")
    ap.add_argument("--max-actions", type=int, default=16)
    args = ap.parse_args()
    env_dir, out = Path(args.env_dir), Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    gids = fetch_games(env_dir, args.games.split(","))

    spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE, environments_dir=str(env_dir))
    games = [taaf.game_api.GameAPI(env_name=g, arcade_spec=spec) for g in gids]
    agent_cls = scripted(CartographToolAgent, lambda agent, prompt: agent._policy(agent, prompt))

    def factory(game, index):
        agent = agent_cls(model="local", workspace_root=out / "cartograph")
        agent._policy = Policy()
        return agent

    solver = HarnessSolver(label="cartograph-scripted-smoke", model="local", concurrency=1,
                           max_actions_per_game=args.max_actions, start_local_server=False,
                           kaggle_enable_vllm=False, analyzer_factory=factory)
    bm = taaf.benchmark.Benchmark(label="cartograph-smoke", games=games, solver=solver, n_passes=1, job_dir=out)
    asyncio.run(bm.run())

    summary = summarise_dir(out / "cartograph")
    (out / "smoke_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
