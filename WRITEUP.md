# Title
Cartograph: Verified Executable World Models for ARC-AGI-3

# Subtitle
A coding agent that plans only inside a world model that exactly replays its full history, else keeps exploring.

# Project links
- Notebook: [NOTEBOOK URL]
- Code: https://github.com/Datwebguy/Cartograph

# Description

Cartograph is a coding agent for ARC-AGI-3 that keeps a persistent, agent-written executable world model and uses it for planning only when it has earned that trust.

**Idea.** The agent maintains `world_model.py` with a function `transition(state, action) -> next_state`. After every edit and every action, a verifier replays the entire recorded history of the game from the initial observation through the model. The model is verified only if every checked transition matches the observed frame cell for cell. A verified model is made available to the agent's Python tool and the agent plans inside it before acting. Otherwise the agent continues with the ordinary inspect-and-act coding loop and receives the exact failing cells, which is the evidence needed to repair the model.

**Why it works.** A verified model has no known counterexample, so plans built from it are correct on everything observed; any remaining error sits on an unobserved transition and is caught by the next replay. The gate turns silent model errors into detected ones at the first counterexample, which bounds the actions spent on bad plans.

**Setting.** Built on the open Duck coding agent, running a local open model on a single GPU with no external APIs. Level changes and resets are re-anchored on the observed frame and reported separately; a replay that checks nothing never counts as verified.

**Evidence.** Exact replay is informative: across all 25 public games, 75 of 75 replayed action sequences were frame-identical.

**Results on public games:** [GAMES ATTEMPTED], [LEVELS COMPLETED], verification success rate [X%].

The pattern is not specific to grids: any interactive domain where an agent can write a transition function and replay is deterministic can use the same gate.
