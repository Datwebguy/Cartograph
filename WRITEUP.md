# Kaggle Writeup - text to paste

Form: https://www.kaggle.com/competitions/arc-prize-2026-paper-track (New Writeup). Cutoff shown on the form: **Nov 10, 2026 12:59 AM GMT+1**.

## Title (max 80)
Cartograph: Verified Executable World Models for ARC-AGI-3

## Subtitle (max 140)
A coding agent that plans only inside a world model that exactly replays its full history, else keeps exploring.

## Card image (560 x 280)
Any simple diagram: observe -> write world_model.py -> exact replay of full history -> verified? plan inside model : keep exploring.

## Project links
- Kaggle notebook: **[PASTE PUBLIC NOTEBOOK URL]**
- Code: https://github.com/Datwebguy/Cartograph
- Full paper text: PAPER.md in the repository

## Project description

Cartograph gives a coding agent for ARC-AGI-3 a persistent, agent-written executable world model and a strict rule for when it may be used.

**How it works.** The agent keeps a file, `world_model.py`, with a function `transition(state, action) -> next_state`. After every edit to the file and after every environment action, a verifier replays the entire recorded history from the initial observed state through the model. The model counts as verified only if every checked transition matches the observed frame cell for cell. Only a verified model is made available for planning: the agent then searches inside it before acting. If the model is not verified, the agent continues with the ordinary inspect-and-act coding loop, which is the situation where new observations are most useful for revising the model.

**Implementation.** It is built on the open-source Duck coding harness as a subclass of its tool agent, so the harness files are unchanged. A new tool writes the model file; the step callback triggers the replay; the model is injected into the python tool only while verified, so the gate is enforced by the tool and not only by the prompt. Model code runs in a resource-limited child process with the same import allowlist as the harness. Everything is local and offline with no external APIs, and it targets a single GPU.

**Design choice.** Level changes and RESET are re-anchored on the observed frame instead of being predicted, and are reported separately from the checked transitions. A replay that checks nothing never counts as verified.

**Measured so far.**
- Replay is informative: across all 25 public games, 75 of 75 replayed action sequences were frame-identical (3 random 40-action sequences per game).
- 16 of 16 tests pass, covering the verifier and the gate in the real agent loop.
- A scripted end-to-end run on three real public games exercised model write, replay, gate open and gate close with full logging.

**Agent results on public games:** [INSERT AFTER THE KAGGLE RUN: games attempted, levels completed, verification success rate, from the notebook's final cell.]

The verification gate is a reusable pattern for any interactive setting where an agent can write a transition function and the environment is deterministic enough for exact replay to be informative.
