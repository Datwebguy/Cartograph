# Build Instructions: Verified Executable World-Model Coding Agent for ARC-AGI-3

## Goal
Produce a public Kaggle notebook (linked from the paper) that implements a Duck-style coding harness + persistent executable world model + exact-replay verification. The score does not need to be high. The notebook must demonstrate the loop and be open-source compatible.

## Starting point
Clone and use the open Duck harness:
https://github.com/Tufalabs/duck-harness

Prefer the existing Kaggle notebook template if present. Do not rewrite the harness from scratch.

## Required changes
1. Give the agent a persistent `world_model.py` file in its workspace that survives across turns within a game.
2. Define a simple expected interface, for example:
   - `def transition(state, action) -> next_state`
   - optional helpers for goals or objects
3. After every model edit or environment action, run an exact-replay verifier:
   - Start from the initial observed state.
   - Replay the entire recorded history through the current world model.
   - Mark the model as verified only if every transition exactly matches the observed frames.
4. If the model is verified, instruct the agent to plan the next action inside the model.
5. If the model is not verified, fall back to the normal Duck REPL inspection-and-action loop.
6. Keep everything local, offline, and single-GPU compatible. No external APIs.

## Minimal success criteria
- Notebook runs on at least 1-3 public ARC-AGI-3 games.
- World-model file is created and updated.
- Verifier runs and can return pass/fail.
- Traces or logs show verification results and actions taken.
- Notebook is made public and its URL is recorded.

## Deliverables
- Public Kaggle notebook URL
- Short note of any public-game results (games attempted, levels completed, verification success rate)
- Code changes clearly commented

## Key references
- Duck harness: https://github.com/Tufalabs/duck-harness
- Duck write-up: https://tufalabs.ai/research/duck-harness/
- Milestone 1: https://arcprize.org/blog/arc-prize-2026-milestone-1
- Rodionov papers: https://arxiv.org/abs/2605.05138 and https://arxiv.org/abs/2607.15439
- Kepler: https://arxiv.org/abs/2610.00834
- OPINE-World: https://arxiv.org/abs/2607.01531
- Official paper track: https://arcprize.org/competitions/2026/paper
