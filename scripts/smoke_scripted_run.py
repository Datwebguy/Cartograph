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

from cartograph.demo import make_demo_factory  # noqa: E402
from cartograph.report import summarise_dir  # noqa: E402

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
    factory = make_demo_factory(model="local", workspace_root=out / "cartograph")

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
