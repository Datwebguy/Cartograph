# Cartograph

Verified executable world models for ARC-AGI-3.

A coding agent keeps a persistent `world_model.py` (`transition(state, action) -> next_state`). After every edit and every action, a verifier replays the full recorded history through it. The model is verified only if every checked transition matches the observed frame exactly. A verified model is made available for planning; otherwise the agent continues with the ordinary inspect-and-act loop. Local, offline, single GPU, no external APIs.

- `PAPER.md` the paper
- `cartograph/` verifier, persistent workspace, agent, reporting
- `notebooks/` Kaggle notebook
- `tests/` test suite (run against the Duck harness environment)
- `scripts/` notebook builder and measurement scripts
- `results/` measurement outputs
