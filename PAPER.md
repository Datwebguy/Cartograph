# Cartograph: Verified Executable World Models in a Coding-Agent Harness for ARC-AGI-3

## Abstract
We present a constrained hybrid agent for ARC-AGI-3 that combines a Duck-style Python REPL coding harness with a persistent, agent-written executable world model. After every action the model is required to exactly replay the full observation history; only a verified model is used for planning. The contribution is the verification step as a practical consistency filter for skill acquisition under offline, single-GPU contest constraints. We show the design, its relation to prior open work, and the smallest ablation path that isolates the effect of exact-replay verification.

## Introduction
ARC-AGI-3 is an interactive benchmark in which agents must explore novel games, infer rules and goals from observation alone, and act efficiently. No instructions or reward shaping are provided. Official competition rules require offline evaluation with no internet, open-source code under permissive licenses, and single-GPU limits (https://arcprize.org/competitions/2026).

Top public approaches fall into two families that have already been shown to work separately: (1) lightweight coding harnesses that treat each game as an interactive Python problem (Tufa Labs' "Duck", Milestone 1 winner), and (2) systems that maintain an explicit executable world model and verify it against history (Rodionov baseline1, Kepler, OPINE-World). This paper describes that combination and why the verification filter is the piece that matters for skill-acquisition efficiency.

## Prior Work
Tufa Labs' Duck harness converts game state into Python variables and lets a local open model write and execute code to inspect the board and call actions (https://github.com/Tufalabs/duck-harness, https://tufalabs.ai/research/duck-harness/, https://arcprize.org/blog/arc-prize-2026-milestone-1). The design is deliberately lightweight: a minimal Python REPL harness.

Rodionov's baseline1 and follow-up ablations maintain a persistent Python world model, perform exact replay verification against recorded observations, and plan through the model (https://arxiv.org/abs/2605.05138, https://arxiv.org/abs/2607.15439, code: https://github.com/astroseger/arc-3-agents-baseline1). Kepler uses retrospective transition checks and conditional prediction checks on executable models and reports perfect public-set RHAE under a frozen frontier configuration (https://arxiv.org/abs/2610.00834). OPINE-World adds ontology-error-prioritized interactive exploration over programmatic world models (https://arxiv.org/abs/2607.01531).

The follow-up (https://arxiv.org/abs/2607.15439) separates executable models, simplification and exact-replay verification into variants; whether the verification gate helps in the open, local-model setting is the question the planned ablation below addresses.

## Approach
The agent is a thin wrapper around the open Duck harness. On each turn it receives the current frame (ASCII + optional segmentation), the action history, and a persistent `world_model.py` file in its workspace.

1. The model may write or edit the world model in Python. The expected interface is a pure function `transition(state, action) -> next_state` plus optional goal and object helpers.
2. After any edit (or after every environment action), an exact-replay verifier runs the current model from the initial state over the entire recorded history. The model is marked verified only if every transition matches the observed frames exactly.
3. If the model is verified, the agent is instructed to propose the next action by planning inside the model (simple search or greedy rollouts). If it is not verified, the agent falls back to the ordinary Duck-style inspection-and-action loop.
4. The action is executed in the real environment. The new observation is appended to history and the loop repeats.

All code is local. No external APIs are called. The same harness and prompts are used across games. State persisting across turns within a game is the world-model file, the observation log, and Duck's own existing carry-over (its textual world-model notes and message history), which we leave unchanged. This is designed to satisfy the offline, open-source, single-GPU constraints of the competition (see Results).

**Implementation (no harness file is modified).** Cartograph is a subclass of Duck's `ToolAgent`, installed through the existing `HarnessSolver.analyzer_factory` hook, pinned to duck-harness commit `7652836`. It adds one tool, `world_model_write(code)`, which replaces `world_model.py` and replays it immediately; and it wraps the environment-step callback so that the full-history replay also runs after every `action(...)` call (a batch of actions inside one call is verified once, at the end). The gate is mechanical, not only a prompt instruction: the model source is injected into the `python` tool (as `transition` and `to_state`) only while verified, so unverified planning raises `NameError`. State is the tuple of letter-coded rows that Duck already shows the agent; actions are the recorded action strings.

**Verifier semantics and the one deliberate deviation.** A model is verified only if every checked transition matches the observed frame cell for cell and at least one transition was checked (a replay that checks nothing is not a pass). Two kinds of recorded step are environment discontinuities that a per-level transition function cannot be expected to predict: a level change (new layout) and `RESET`. By default the replay re-anchors on the observed frame at those steps, counts them separately (`n_anchored`), and does not count them as passes; `strict=True` checks them too. Model code runs in a child process with CPU/memory/time limits and the same import and builtin allowlist as Duck's python tool; this is a consistency measure, not a hardened security boundary, as in the harness it mirrors.

## Theory
Exact-replay verification turns the world model into a falsifiable hypothesis. A model that cannot reproduce every past transition is rejected, regardless of how plausible its local predictions look. This is a practical minimum-description-length / consistency filter: only models that compress the observed history exactly are allowed to influence future actions. It separates "the model is right so far" from "the model is merely consistent with a subset of the data."

In interactive skill acquisition the cost of a wrong model is wasted actions. By gating planning on verification, the agent avoids committing to an incorrect transition function for long horizons. When verification fails, the system reverts to open exploration (the Duck loop), which is exactly the regime in which new information is most useful for revising the model. The design therefore implements a simple version of the scientific loop: observe, encode a hypothesis as code, test it against the entire record, revise on the first counter-example, and plan only inside a surviving model.

## Results

Section A reports the agent run on public games from the linked Kaggle notebook and is filled from its output. Sections B and C report what has been measured without the LLM and the planned ablation.

### A. Public-game agent run (the Kaggle submission)

| Quantity | Value |
| --- | --- |
| Games attempted | _pending notebook run_ |
| Levels completed | _pending notebook run_ |
| Verification success rate (post-action replays that verified, among checks with a model written) | _pending notebook run_ |
| Kaggle notebook URL | _TBD_ |

To fill this in, run `notebooks/cartograph_duck_kaggle.ipynb` on Kaggle and copy the output of its last cell (`cartograph_results.json`, defined in `cartograph/report.py`).

### B. Measured without the LLM

All numbers below come from files in `results/` and the test suite in `tests/`; duck-harness commit `7652836`.

1. **Exact replay is meaningful on the public games.** For each of the 25 public games, 3 random action sequences of 40 actions (clicks at random coordinates, fixed seed 0) were played on two fresh environments and compared frame by frame: **25 of 25 games, 75 of 75 sequence replays identical** (`results/replay_determinism.json`). Mean cells changed per action ranges from 1.12 (tn36) to 112.33 (cn04) across games. Scope: random play, 40 actions per sequence.
2. **Verifier and gate unit tests: 16 of 16 pass** (`tests/`): correct model verifies; wrong, raising, malformed, shape-mismatched, looping and import-violating models fail; a replay that checks nothing fails; level-change and `RESET` steps are anchored not counted (and checked under `strict`); the planning gate opens only on a verified model, the python tool raises `NameError` for `transition` while unverified, and the gate closes when the environment's rules change; the verifier's builtin/import allowlist is a subset of Duck's.
3. **Scripted plumbing smoke test (not an agent result).** The real `HarnessSolver`, TAAF `Benchmark` and `CartographToolAgent` played 3 real public games (ls20, lf52, dc22; 16 actions each, 48 total) with only the LLM call replaced by a fixed script (`scripts/smoke_scripted_run.py`; logs in `results/smoke_scripted/`). The scripted "model" memorises transitions seen so far, so it is exact on history and stale one action later. Observed per game (identical across the three, as scripted): the deliberately wrong identity model was rejected (3 of 3); 13 of 14 model writes verified; 13 of 16 actions were issued while the gate was open (planning enabled) and 3 with no model; every one of the 13 post-action replays that followed a written model failed (0 of 13 per game, 0 of 39 overall), because the action had just produced a transition the table did not contain. This run validates the pipeline end to end on real engine data (write, replay, gate open, gate close, logging); the script does not try to win, so level counts are not an agent result.

### C. Planned ablation

On the same 3-5 public games, with identical model, temperature and action budget: (1) pure Duck REPL; (2) Duck + persistent model, no forced verification; (3) Duck + persistent model + exact-replay verification + gated planning. Report levels completed, actions to completion, and verification success rate. The size of any difference is determined by this experiment.

## Universality, Progress, and Novelty
The pattern (write an executable model -> require exact replay of full history -> plan only inside a verified model) is not specific to ARC-AGI-3 grids. It applies to any interactive domain in which a coding agent can maintain a transition function and the environment is deterministic enough for exact replay to be informative. Under contest constraints it is a concrete step toward higher skill-acquisition efficiency: it is designed to reduce the number of actions spent executing incorrect hypotheses.

Relative to public research the novelty is the tight integration inside a proven lightweight coding harness under the exact Kaggle offline/single-GPU rules, plus the explicit treatment of verification as a consistency filter rather than an optional post-hoc check. The individual pieces exist; the contest-ready, fully open combination with clear ablations does not.

## Conclusion
A Duck-style coding agent that is forced to maintain and exactly verify an executable world model before planning is a minimal, open, and contest-compliant way to turn open-ended exploration into testable hypothesis refinement. The linked Kaggle submission demonstrates the loop; the planned ablation isolates the contribution of the verification gate. The same mechanism is a reusable primitive for any setting in which agents must acquire skills in novel environments with limited interaction.

## References
- ARC Prize 2026 rules and paper track: https://arcprize.org/competitions/2026 and https://arcprize.org/competitions/2026/paper
- Tufa Labs Duck harness: https://github.com/Tufalabs/duck-harness and https://tufalabs.ai/research/duck-harness/
- ARC Prize Milestone 1 announcement: https://arcprize.org/blog/arc-prize-2026-milestone-1
- Rodionov, Executable World Models for ARC-AGI-3: https://arxiv.org/abs/2605.05138 and follow-up https://arxiv.org/abs/2607.15439 (code: https://github.com/astroseger/arc-3-agents-baseline1)
- Wu, Kepler: Auditable World Models for ARC-AGI-3: https://arxiv.org/abs/2610.00834
- Courtis et al., OPINE-World: https://arxiv.org/abs/2607.01531
