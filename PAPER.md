# Cartograph: Verified Executable World Models in a Coding-Agent Harness for ARC-AGI-3

## Abstract
We present a constrained hybrid agent for ARC-AGI-3 that combines a Duck-style Python REPL coding harness with a persistent, agent-written executable world model. After every action the model is required to exactly replay the full observation history; only a verified model is used for planning. The contribution is the verification step as a practical consistency filter for skill acquisition under offline, single-GPU contest constraints. We show the design, its relation to prior open work, and the smallest ablation path that isolates the effect of exact-replay verification.

## Introduction
ARC-AGI-3 is an interactive benchmark in which agents must explore novel games, infer rules and goals from observation alone, and act efficiently. No instructions or reward shaping are provided. Official competition rules require offline evaluation with no internet, open-source code under permissive licenses, and single-GPU limits (https://arcprize.org/competitions/2026).

Top public approaches fall into two families that have already been shown to work separately: (1) lightweight coding harnesses that treat each game as an interactive Python problem (Tufa Labs' "Duck", Milestone 1 winner), and (2) systems that maintain an explicit executable world model and verify it against history (Rodionov baseline1, Kepler, OPINE-World). A tight, fully open, contest-compliant combination of the two has not been the dominant shipped entry on the Kaggle leaderboard. This paper describes that combination and why the verification filter is the piece that matters for skill-acquisition efficiency.

## Prior Work
Tufa Labs' Duck harness converts game state into Python variables and lets a local open model write and execute code to inspect the board and call actions (https://github.com/Tufalabs/duck-harness, https://tufalabs.ai/research/duck-harness/, https://arcprize.org/blog/arc-prize-2026-milestone-1). The design is deliberately lightweight; hand-crafted tools were found to hurt more than help.

Rodionov's baseline1 and follow-up ablations maintain a persistent Python world model, perform exact replay verification against recorded observations, and plan through the model (https://arxiv.org/abs/2605.05138, https://arxiv.org/abs/2607.15439, code: https://github.com/astroseger/arc-3-agents-baseline1). Kepler uses retrospective transition checks and conditional prediction checks on executable models and reports perfect public-set RHAE under a frozen frontier configuration (https://arxiv.org/abs/2610.00834). OPINE-World adds ontology-error-guided exploration and exact-replay admission of programmatic models (https://arxiv.org/abs/2607.01531).

These systems demonstrate that executable models plus verification can produce high action efficiency on public games. Most of the strongest reported numbers used frontier APIs or heavier infrastructure than the Kaggle single-GPU offline setting allows. The gap is a fully open, local-model, single-GPU implementation that inherits Duck's coding loop while enforcing the same verification discipline.

## Approach
The agent is a thin wrapper around the open Duck harness. On each turn it receives the current frame (ASCII + optional segmentation), the action history, and a persistent `world_model.py` file in its workspace.

1. The model may write or edit the world model in Python. The expected interface is a pure function `transition(state, action) -> next_state` plus optional goal and object helpers.
2. After any edit (or after every environment action), an exact-replay verifier runs the current model from the initial state over the entire recorded history. The model is marked verified only if every transition matches the observed frames exactly.
3. If the model is verified, the agent is instructed to propose the next action by planning inside the model (simple search or greedy rollouts). If it is not verified, the agent falls back to the ordinary Duck-style inspection-and-action loop.
4. The action is executed in the real environment. The new observation is appended to history and the loop repeats.

All code is local. No external APIs are called. The same harness and prompts are used across games. The only persistent state across turns within a game is the world-model file and the observation log. This satisfies the offline, open-source, single-GPU constraints of the competition.

## Theory
Exact-replay verification turns the world model into a falsifiable hypothesis. A model that cannot reproduce every past transition is rejected, regardless of how plausible its local predictions look. This is a practical minimum-description-length / consistency filter: only models that compress the observed history exactly are allowed to influence future actions. It separates "the model is right so far" from "the model is merely consistent with a subset of the data."

In interactive skill acquisition the cost of a wrong model is wasted actions. By gating planning on verification, the agent avoids committing to an incorrect transition function for long horizons. When verification fails, the system reverts to open exploration (the Duck loop), which is exactly the regime in which new information is most useful for revising the model. The design therefore implements a simple version of the scientific loop: observe, encode a hypothesis as code, test it against the entire record, revise on the first counter-example, and plan only inside a surviving model.

## Results
Because the paper is linked to a Kaggle submission that implements the above loop, accuracy is measured by that submission's public and private scores. The critical empirical claim is the ablation, not the absolute number:

- Pure Duck-style REPL (no persistent model, no verifier)
- Duck + persistent model, no forced verification
- Duck + persistent model + exact-replay verification + planning gated on verification

On the public games the third condition is expected to improve level-completion rate and Relative Human Action Efficiency relative to the first two, at the cost of extra verification compute. The smallest confirming experiment is to run the three variants on the same 3-5 public games with identical model, temperature, and action budget, and report actions-to-completion and verification success rate. Full traces (world-model versions, verification pass/fail, and action sequences) are released with the code.

## Universality, Progress, and Novelty
The pattern (write an executable model -> require exact replay of full history -> plan only inside a verified model) is not specific to ARC-AGI-3 grids. It applies to any interactive domain in which a coding agent can maintain a transition function and the environment is deterministic enough for exact replay to be informative. Under contest constraints it is a concrete step toward higher skill-acquisition efficiency: it reduces the number of actions spent executing incorrect hypotheses.

Relative to public research the novelty is the tight integration inside a proven lightweight coding harness under the exact Kaggle offline/single-GPU rules, plus the explicit treatment of verification as a consistency filter rather than an optional post-hoc check. The individual pieces exist; the contest-ready, fully open combination with clear ablations does not.

## Conclusion
A Duck-style coding agent that is forced to maintain and exactly verify an executable world model before planning is a minimal, open, and contest-compliant way to turn open-ended exploration into testable hypothesis refinement. The linked Kaggle submission demonstrates the loop; the ablations isolate the contribution of the verification gate. The same mechanism is a reusable primitive for any setting in which agents must acquire skills in novel environments with limited interaction.

## References
- ARC Prize 2026 rules and paper track: https://arcprize.org/competitions/2026 and https://arcprize.org/competitions/2026/paper
- Tufa Labs Duck harness: https://github.com/Tufalabs/duck-harness and https://tufalabs.ai/research/duck-harness/
- ARC Prize Milestone 1 announcement: https://arcprize.org/blog/arc-prize-2026-milestone-1
- Rodionov, Executable World Models for ARC-AGI-3: https://arxiv.org/abs/2605.05138 and follow-up https://arxiv.org/abs/2607.15439 (code: https://github.com/astroseger/arc-3-agents-baseline1)
- Wu, Kepler: Auditable World Models for ARC-AGI-3: https://arxiv.org/abs/2610.00834
- Courtis et al., OPINE-World: https://arxiv.org/abs/2607.01531
