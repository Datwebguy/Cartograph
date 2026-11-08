# Kaggle notebook

`cartograph_duck_kaggle.ipynb` is **generated** from Tufa Labs' public Duck notebook
(`taaf-duck-harness-kaggle-share.ipynb` in https://github.com/Tufalabs/duck-harness) by
`scripts/build_notebook.py`. Their credit cell and all setup cells are kept; our changes are:

1. cells 4b: write the `cartograph/` package (readable `%%writefile` cells, no extra dataset needed);
2. the template's "Customization hook": install `CartographToolAgent` via `HarnessSolver.analyzer_factory`;
3. "Run the benchmark": after the template reassigns `bm.games`, an interactive run is cut to the first
   `CARTOGRAPH_N_GAMES = 3` games (a real competition rerun is not restricted);
4. a final cell that summarises `verification_log.jsonl` files into `cartograph_results.json` and prints the table.

## Not tested

This notebook has **not been run**: it needs Kaggle (competition wheelhouse and environment files, an H100,
vLLM, the Qwen3.6-27B-FP8 dataset). It was only built and syntax-checked. The agent code it embeds is covered by
`tests/`, and was exercised on real games with a scripted stand-in for the LLM (`scripts/smoke_scripted_run.py`).

## Before you publish

- The template attaches datasets owned by others (`jeroencottaar/taaf-kaggle-source-share`,
  `driessmit1/arc3-vllm-h100-wheelhouse-v3`, `driessmit1/vrfai-qwen3-6-27b-fp8-hf-snapshot`). They must stay
  attached and be accessible to the people who open your public notebook.
- The Duck repository has no LICENSE file (its `pyproject.toml` only has an MIT classifier). Check with Tufa Labs
  before republishing their notebook text.
- Kaggle "Save & Run (Commit)" with the GPU accelerator and internet **off**. Then copy the last cell's output
  into PAPER.md section A, and record the notebook URL there and in README.md.
- Duck advertises `ACTION7` on some games but cannot issue it; the first three offline games may include one.

## Implementation notes
- The world-model file is capped at 8000 characters because the whole file is shown to the agent every turn within a 32k-token context.
- Exact match includes timer/HUD bars, so a model must reproduce them to verify.
