#!/usr/bin/env python
"""Measure whether exact replay is informative: is each public game deterministic?

For every public game: draw SEQS random action sequences (LEN actions, clicks get random
coordinates), play each on two FRESH environments, and compare every frame cell for cell.
Also records cells changed per action. No agent, no model. Needs the arc-agi toolkit and the
one-time public game download (--env-dir cache).
"""
import argparse, json, random, traceback
import numpy as np
import arc_agi
from arcengine import GameAction

def _fr(obs):
    # A terminal step can return no frame; keep an explicit empty marker so replays still compare exactly.
    return np.array(obs.frame[-1]) if obs.frame else np.zeros((0, 0))


ap = argparse.ArgumentParser()
ap.add_argument("--env-dir", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--only", default=""); ap.add_argument("--seqs", type=int, default=3); ap.add_argument("--len", type=int, default=40)
a = ap.parse_args()
arc = arc_agi.Arcade(environments_dir=a.env_dir)
res = []
for info in arc.get_environments():
    gid = info.game_id
    if a.only and gid.split("-")[0] not in a.only.split(","):
        continue
    rng = random.Random(0)
    def play(seq):
        env = arc.make(gid); obs = env.reset(); frames = [_fr(obs)]
        for act, data in seq:
            obs = env.step(GameAction.from_id(act), data=data) if data else env.step(GameAction.from_id(act))
            frames.append(_fr(obs))
        return frames
    avail = [x for x in arc.make(gid).reset().available_actions if x != 0]
    n_same = n_total = 0; changed = []; err = None
    try:
        for _ in range(a.seqs):
            seq = []
            for _ in range(a.len):
                act = rng.choice(avail)
                seq.append((act, {"x": rng.randrange(64), "y": rng.randrange(64)} if act == 6 else None))
            f1, f2 = play(seq), play(seq)
            n_total += 1; n_same += all((x.shape == y.shape and np.array_equal(x, y)) for x, y in zip(f1, f2))
            changed += [int((f1[i] != f1[i + 1]).sum()) for i in range(len(f1) - 1) if f1[i].shape == f1[i + 1].shape]
    except Exception as e:  # report, do not hide
        err = f"{type(e).__name__}: {e} @ {traceback.extract_tb(e.__traceback__)[-1].name}:{traceback.extract_tb(e.__traceback__)[-1].lineno}"[:200]
    res.append({"game": gid, "actions": sorted(avail), "sequences": n_total, "identical_replays": n_same,
                "mean_cells_changed_per_action": round(float(np.mean(changed)), 2) if changed else None,
                "error": err})
    print(res[-1], flush=True)
ok = [r for r in res if r["sequences"] == a.seqs and r["identical_replays"] == r["sequences"] and not r["error"]]
summary = {"games": len(res), "fully_deterministic_games": len(ok),
           "sequence_replays_identical": sum(r["identical_replays"] for r in res),
           "sequence_replays_total": sum(r["sequences"] for r in res),
           "games_with_errors": [r["game"] for r in res if r["error"]], "per_game": res,
           "params": {"seqs": a.seqs, "len": a.len, "rng_seed": 0}}
json.dump(summary, open(a.out, "w"), indent=2)
print({k: v for k, v in summary.items() if k != "per_game"})
