#!/usr/bin/env python
"""Build notebooks/cartograph_duck_kaggle.ipynb from Tufa Labs' Duck Kaggle notebook.

Usage: python scripts/build_notebook.py <path/to/taaf-duck-harness-kaggle-share.ipynb> [--demo]

  (default)  notebooks/cartograph_duck_kaggle.ipynb: the agent with the local Qwen model (needs the
             single large GPU the Duck setup requires).
  --demo     notebooks/cartograph_pipeline_demo.ipynb: the same harness and agent on real public games with
             the model-server setup skipped and a scripted policy in place of the LLM. No GPU needed.

The template is kept as-is except for three small, commented insertions:
  1. new cells after "Import the bundled source" that write the Cartograph package to disk
  2. the template's own "Customization hook" cell now installs CartographToolAgent through
     HarnessSolver.analyzer_factory (no harness file is edited)
  3. cell "Run the benchmark": after `bm.games` is (re)assigned, an interactive run is cut to the
     first CARTOGRAPH_N_GAMES games. This must live HERE: this cell reassigns bm.games after the hook.
and a final results cell. Everything else, including Tufa Labs' credit cell, is untouched.
"""
import copy
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = "--demo" in sys.argv
OUT = ROOT / "notebooks" / ("cartograph_pipeline_demo.ipynb" if DEMO else "cartograph_duck_kaggle.ipynb")
PKG = ["__init__.py", "verifier.py", "workspace.py", "agent.py", "report.py"] + (["testing.py", "demo.py"] if DEMO else [])
PKG_DIR = "/kaggle/working/cartograph_src/cartograph"


def md(text):
    return {"cell_type": "markdown", "id": uuid.uuid4().hex[:8], "metadata": {}, "source": text.splitlines(True)}


def code(text):
    return {"cell_type": "code", "id": uuid.uuid4().hex[:8], "metadata": {}, "execution_count": None,
            "outputs": [], "source": text.splitlines(True)}


def src(cell):
    return "".join(cell["source"])


def main(template_path):
    nb = json.load(open(template_path))
    cells = copy.deepcopy(nb["cells"])
    for c in cells:                                   # drop the template's recorded outputs
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    nb["metadata"].pop("papermill", None)

    idx = {c["source"][0].strip(): i for i, c in enumerate(cells) if c["source"]}
    i_setup = next(i for i, c in enumerate(cells) if src(c).startswith("## 4. Import the bundled source"))
    i_hook = next(i for i, c in enumerate(cells) if src(c).startswith("# Make one-off changes to `bm`"))
    i_run = next(i for i, c in enumerate(cells) if "bm.n_passes = 1" in src(c))

    # (3) game restriction, inside the template's run cell (after it reassigns bm.games)
    run_src = src(cells[i_run])
    needle = "bm.n_passes = 1\nbm.game_weights = None\n"
    assert run_src.count(needle) == 1, "template changed: cannot place the game restriction"
    cells[i_run]["source"] = run_src.replace(needle, needle + (
        "\n# --- Cartograph: an interactive (non-submission) run plays only the first CARTOGRAPH_N_GAMES\n"
        "# public games (1-3 per the build spec). A real competition rerun is NOT restricted.\n"
        "CARTOGRAPH_N_GAMES = 3\n"
        "if not TRUE_SUBMISSION:\n"
        "    bm.games = bm.games[:CARTOGRAPH_N_GAMES]\n"
        "    print('cartograph: playing games', [getattr(g, 'env_name', g) for g in bm.games])\n"
        "# --- end Cartograph\n")).splitlines(True)

    # (2) the template's customization hook
    if DEMO:
        hook = (
            "\n# --- Cartograph pipeline demonstration (no GPU, no model server).\n"
            "# The real Duck solver and CartographToolAgent play real public games; only the model's decisions\n"
            "# are scripted. This shows write / replay / gate open / gate close / logging on real engine data.\n"
            "import os\n"
            "os.environ.setdefault('LOCAL_ANALYZER_MODEL_ID', 'scripted-no-llm')\n"
            "os.environ.setdefault('LOCAL_ANALYZER_BASE_URL', 'http://127.0.0.1:1/v1')\n"
            "from cartograph.demo import make_demo_factory\n\n"
            "_s = bm.solver\n"
            "_s.max_actions_per_game = 16\n"
            "bm.solver.analyzer_factory = make_demo_factory(model='local', workspace_root=str(WORKING_DIR / 'cartograph'))\n"
            "print('cartograph demo: analyzer_factory installed; world models ->', WORKING_DIR / 'cartograph')\n")
    else:
        hook = (
            "\n# --- Cartograph: verified executable world model + verification gate.\n"
            "# HarnessSolver already exposes `analyzer_factory`; we only supply a ToolAgent subclass.\n"
            "# It is not pickled with the benchmark, so it is installed here, after the bundle loaded.\n"
            "from cartograph.agent import make_analyzer_factory\n\n"
            "_s = bm.solver\n"
            "bm.solver.analyzer_factory = make_analyzer_factory(\n"
            "    model=_s.model, timeout=_s.analyzer_timeout, save_request_logs=_s.save_request_logs,\n"
            "    workspace_root=str(WORKING_DIR / 'cartograph'),   # world_model.py + verification_log.jsonl per game\n"
            ")\n"
            "print('cartograph: analyzer_factory installed; world models ->', WORKING_DIR / 'cartograph')\n")
    cells[i_hook]["source"] = (src(cells[i_hook]) + hook).splitlines(True)

    if DEMO:   # skip the vLLM/model setup commands: the demo needs no model server
        setup_src = src(cells[i_setup + 1])
        loop = setup_src[setup_src.index("env = _command_env()\nfor command in"):setup_src.index("# Honour any PYTHONPATH")]
        assert "setup_commands.json" in loop, "template changed: cannot skip setup commands"
        cells[i_setup + 1]["source"] = setup_src.replace(
            loop, "env = _command_env()\nprint('cartograph demo: model-server setup commands skipped (no LLM is used)')\n\n").splitlines(True)

    # (1) package cells
    new = [
        md("## 4b. Cartograph: write the package\n\n"
           "Cartograph adds a persistent `world_model.py`, an exact-replay verifier and a verification gate to the "
           "Duck harness without editing the harness: `CartographToolAgent` subclasses Duck's `ToolAgent`. "
           "Everything is local and offline (no external API). The cells below write the package to disk so "
           "this notebook is self-contained; source is in the Cartograph repository.\n"),
        code(f"import sys\nfrom pathlib import Path\nPath('{PKG_DIR}').mkdir(parents=True, exist_ok=True)\n"
             f"sys.path.insert(0, str(Path('{PKG_DIR}').parent))\n"),
    ]
    for name in PKG:
        text = (ROOT / "cartograph" / name).read_text()
        new.append(code(f"%%writefile {PKG_DIR}/{name}\n{text}"))
    if DEMO:
        new[0] = md("## 4b. Cartograph: write the package (pipeline demonstration)\n\n"
                    "This notebook demonstrates the Cartograph loop end to end on real public ARC-AGI-3 games, "
                    "without a GPU. The real Duck solver and `CartographToolAgent` run; a fixed script replaces the "
                    "language model's decisions. The results table at the end therefore describes the pipeline "
                    "(model written, replayed, gate opened and closed, everything logged), not a language model's "
                    "play. The language-model version is `cartograph_duck_kaggle.ipynb`.\n")
    cells[i_setup + 2:i_setup + 2] = new     # right after the template's setup code cell

    # final results cell
    cells += [
        md("## 9. Cartograph results\n\nSummarises the per-game `verification_log.jsonl` files: games attempted, "
           "levels completed, verification success rate, and the gate state each action was issued under.\n"),
        code("import json\nfrom cartograph.report import summarise_dir\n\n"
             "summary = summarise_dir(WORKING_DIR / 'cartograph')\n"
             "summary['game_runs'] = [{'game_id': r.game_id, 'state': r.state, 'final_score': r.final_score}\n"
             "                        for r in bm.game_runs]\n"
             "(WORKING_DIR / 'cartograph_results.json').write_text(json.dumps(summary, indent=2))\n"
             "print(json.dumps({k: v for k, v in summary.items() if k != 'per_game'}, indent=2))\n"
             "for game, s in summary['per_game'].items():\n    print(game, json.dumps(s))\n"),
    ]
    nb["cells"] = cells
    OUT.parent.mkdir(exist_ok=True)
    json.dump(nb, open(OUT, "w"), indent=1)
    print("wrote", OUT, f"({len(cells)} cells)")


if __name__ == "__main__":
    main(sys.argv[1])
