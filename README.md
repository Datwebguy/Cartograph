# Cartograph

Verified executable world models in a Duck-style coding-agent harness for ARC-AGI-3 (ARC Prize 2026 paper track).

The agent keeps a persistent `world_model.py`, exact-replays the full observation history after every edit/action, and only plans inside the model when it is verified; otherwise it falls back to the normal Duck REPL loop.

## Files
- `PAPER.md` - paper draft (source of truth for the submission)
- `BUILD_INSTRUCTIONS.md` - spec for the harness changes and the public Kaggle notebook

## Status
- [x] Clone Tufalabs/duck-harness (read-only) and get a baseline run working - plumbing only: the harness, TAAF and the real games run on CPU with a scripted stand-in for the LLM. The Qwen3.6-27B model was **not** run (no GPU in the drafting session).
- [x] Persistent `world_model.py` + exact-replay verifier + gating (`cartograph/`, 16 tests passing)
- [x] Kaggle notebook built (`notebooks/`) - **not run**, needs Kaggle; you run and publish it (URL: TBD)
- [x] Real results recorded in PAPER.md section B (determinism, tests, scripted smoke test); section A (the agent run) is empty until the notebook is run
- [x] arXiv references and deadline checked - see `REFERENCE_CHECK.md` (unconfirmed claims removed from the paper; deadline per the Kaggle Writeup form: Nov 10, 2026 12:59 AM GMT+1)

## Layout
- `cartograph/` verifier, workspace, `CartographToolAgent` (subclass of Duck's `ToolAgent`; no harness file is edited), report
- `tests/` run with the Duck venv: `PYTHONPATH=.:<duck-harness>/ARC3-Inference <that venv>/bin/python -m pytest tests`
- `scripts/` `smoke_scripted_run.py`, `replay_determinism.py`, `build_notebook.py`
- `results/` raw logs behind the numbers in PAPER.md

## Notes
- Eligibility: the paper must link a real Kaggle code submission (ARC-AGI-2 or ARC-AGI-3 track) that demonstrates the approach. A high score is not required.
- The Results section of the paper states *expected* outcomes. Replace with measured numbers before submitting.
- The ARC competition page lists "November 8, 2026 - Papers due" (the paper page lists none); time, timezone and submission method are not stated. See `REFERENCE_CHECK.md`.
