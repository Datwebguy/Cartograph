"""Exact-replay verifier for an agent-written world model.

Contract of ``world_model.py`` (written by the agent):

    def transition(state, action) -> next_state

  * ``state``  : tuple of row strings, one letter per cell. These are exactly the
                 characters of ``Frame.ascii`` in the Duck harness, i.e. what the
                 agent already sees (the raw numeric grid is hidden from it).
  * ``action`` : the action string as recorded in the Duck history, e.g. ``"UP"``,
                 ``"SPACE"``, ``"MOUSE(row=3, col=4)"``.
  * returns    : the next state in the same representation (tuple/list of str).

Verification rule (what "verified" means):

    Start from the initial observed state (history[0]). Replay the ENTIRE recorded
    history through ``transition``. The model is verified only if, for every
    replayed transition, the predicted next state equals the observed next frame
    cell for cell, AND at least ``min_checked`` transitions were actually checked.

Design decision (documented deviation, see ``anchor`` below): two kinds of recorded
transitions are *discontinuities of the environment*, not dynamics a per-level
transition function can be expected to predict: a level change (the next level's
layout is new information) and ``RESET`` (restores a level start that the model has
no state to know). Unless ``strict=True``, the replay re-anchors on the observed
frame at those steps instead of checking them. They are counted separately
(``n_anchored``) and reported, never silently counted as passes. ``strict=True``
checks every transition, anchors included.

The model code is untrusted LLM output, so it runs in a child process
(``python -I -S``) with resource limits, a wall-clock timeout, a restricted builtins
table and an import allowlist. The allowlist deliberately equals the Duck python
tool's, so a model that verifies here also runs inside the Duck sandbox (this is
what makes it usable for planning). This is a consistency measure, not a hardened
security boundary - the same is true of the harness sandbox it mirrors.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

# One recorded step: (action string, rows of letters, level number).
# history[0] is the initial observation (its action is ignored).
HistoryItem = tuple[str, tuple[str, ...], int]

# MUST stay a subset of the Duck sandbox's SAFE_MODULES / SAFE_BUILTINS
# (inference/agent/python_tool_sandbox.py). tests/test_agent_gating.py checks this
# against the real harness whenever the harness is importable.
SAFE_MODULES = (
    "bisect", "collections", "copy", "fractions", "functools", "heapq", "itertools",
    "json", "math", "operator", "random", "re", "statistics", "string",
)
SAFE_BUILTINS = (
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable", "chr",
    "complex", "dict", "dir", "divmod", "enumerate", "Exception", "filter", "float",
    "format", "frozenset", "getattr", "hasattr", "hash", "hex", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next", "oct", "ord", "pow",
    "print", "range", "repr", "reversed", "round", "set", "slice", "sorted", "str", "sum",
    "tuple", "TypeError", "type", "ValueError", "RuntimeError", "zip",
)

MAX_DIFF_SAMPLES = 5


@dataclass
class VerificationResult:
    verified: bool
    n_transitions: int = 0      # transitions present in the history (len(history) - 1)
    n_checked: int = 0          # transitions predicted by the model and compared
    n_anchored: int = 0         # level-change / RESET steps re-anchored (not checked)
    strict: bool = False
    first_mismatch: dict[str, Any] | None = None   # {index, action, kind, n_diff, diffs}
    error: str | None = None    # load/runtime/timeout/format problem, if any
    reason: str = ""            # one-line human summary
    model_sha256: str = ""
    elapsed_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- child process --------------------------------------------------------------
# Reads one JSON line {source, history, strict, timeout_s}; writes one JSON line.
_CHILD = textwrap.dedent(
    r"""
    import builtins, io, json, sys

    try:
        import resource
    except ImportError:
        resource = None

    REAL_STDOUT = sys.stdout
    req = json.loads(sys.stdin.readline())
    if resource is not None:
        cpu = max(1, int(req["timeout_s"])) + 1
        for lim, val in ((resource.RLIMIT_CPU, cpu), (resource.RLIMIT_FSIZE, 1_000_000),
                         (resource.RLIMIT_NOFILE, 32), (resource.RLIMIT_AS, 2 * 1024 ** 3)):
            try:
                resource.setrlimit(lim, (val, val))
            except (OSError, ValueError):
                pass

    SAFE_MODULES = set(req["safe_modules"])

    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if str(name or "").split(".", 1)[0] not in SAFE_MODULES:
            raise ImportError("Module '%s' is not allowed in the world-model sandbox." % name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    safe = {n: getattr(builtins, n) for n in req["safe_builtins"]}
    safe["__import__"] = _safe_import
    ns = {"__builtins__": safe, "__name__": "world_model"}

    def emit(**kw):
        REAL_STDOUT.write(json.dumps(kw) + "\n")
        REAL_STDOUT.flush()

    def short(e):
        return ("%s: %s" % (type(e).__name__, e))[:300]

    sys.stdout = io.StringIO()   # a model that print()s must not corrupt the protocol
    try:
        exec(compile(req["source"], "world_model.py", "exec"), ns)
    except Exception as e:
        emit(error="load failed: " + short(e)); raise SystemExit
    fn = ns.get("transition")
    if not callable(fn):
        emit(error="world_model.py must define transition(state, action)"); raise SystemExit

    hist, strict = req["history"], req["strict"]
    state = tuple(hist[0][1])
    checked = anchored = 0
    for i in range(1, len(hist)):
        action, obs_rows, level = hist[i][0], tuple(hist[i][1]), hist[i][2]
        if (not strict) and (level != hist[i - 1][2] or action.strip().upper() == "RESET"):
            state = obs_rows; anchored += 1
            continue
        try:
            out = fn(state, action)
        except Exception as e:
            emit(checked=checked, anchored=anchored, error="transition raised at step %d (%s): %s" % (i, action, short(e)),
                 mismatch={"index": i, "action": action, "kind": "exception"}); raise SystemExit
        if not (isinstance(out, (list, tuple)) and all(type(r) is str for r in out)):
            emit(checked=checked, anchored=anchored,
                 mismatch={"index": i, "action": action, "kind": "bad_return_type",
                           "got_type": type(out).__name__}); raise SystemExit
        out = tuple(out)
        checked += 1
        if out != obs_rows:
            m = {"index": i, "action": action}
            if len(out) != len(obs_rows) or any(len(a) != len(b) for a, b in zip(out, obs_rows)):
                m.update(kind="shape", expected="%dx%d" % (len(obs_rows), len(obs_rows[0]) if obs_rows else 0),
                         got="%dx%d" % (len(out), len(out[0]) if out else 0))
            else:
                diffs = [(r, c, obs_rows[r][c], out[r][c]) for r in range(len(out))
                         for c in range(len(out[r])) if out[r][c] != obs_rows[r][c]]
                m.update(kind="cells", n_diff=len(diffs), diffs=diffs[:req["max_diffs"]])
            emit(checked=checked, anchored=anchored, mismatch=m); raise SystemExit
        state = obs_rows   # equal to out; use the observed object
    emit(checked=checked, anchored=anchored, mismatch=None)
    """
)


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


def verify_exact_replay(
    source: str,
    history: Sequence[HistoryItem],
    *,
    strict: bool = False,
    min_checked: int = 1,
    timeout_s: float = 20.0,
) -> VerificationResult:
    """Replay ``history`` through the model in ``source``; see module docstring."""
    t0 = time.monotonic()
    sha = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    base = dict(
        n_transitions=max(0, len(history) - 1), strict=strict, model_sha256=sha,
    )

    def done(verified: bool, **kw: Any) -> VerificationResult:
        return VerificationResult(verified=verified, elapsed_s=round(time.monotonic() - t0, 4),
                                  **{**base, **kw})

    if not history:
        return done(False, error="empty history", reason="no history to replay")

    req = {
        "source": source,
        "history": [[a, list(rows), int(level)] for a, rows, level in history],
        "strict": strict,
        "timeout_s": timeout_s,
        "max_diffs": MAX_DIFF_SAMPLES,
        "safe_modules": list(SAFE_MODULES),
        "safe_builtins": list(SAFE_BUILTINS),
    }
    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", _CHILD],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", start_new_session=True,
            env={"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/tmp"},
        )
    except OSError as exc:
        return done(False, error=f"verifier process could not start: {exc}", reason="verifier error")
    try:
        stdout, _ = proc.communicate(json.dumps(req), timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        proc.communicate()
        return done(False, error=f"replay timed out after {timeout_s}s", reason="timeout")

    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    try:
        msg = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        return done(False, error="verifier child produced no result (crash, limit hit, or exit)",
                    reason="verifier error")

    checked, anchored = int(msg.get("checked", 0)), int(msg.get("anchored", 0))
    common = dict(n_checked=checked, n_anchored=anchored)
    if msg.get("error"):
        return done(False, error=msg["error"], first_mismatch=msg.get("mismatch"),
                    reason=msg["error"], **common)
    mismatch = msg.get("mismatch")
    if mismatch:
        what = mismatch.get("kind")
        n = mismatch.get("n_diff")
        return done(False, first_mismatch=mismatch, reason=(
            f"mismatch at step {mismatch['index']} ({mismatch['action']}): {what}"
            + (f", {n} cell(s) differ" if n is not None else "")), **common)
    if checked < min_checked:
        return done(False, reason=(f"vacuous: only {checked} transition(s) checked "
                                   f"(need >= {min_checked}); {anchored} anchored"), **common)
    return done(True, reason=f"all {checked} checked transition(s) match exactly "
                             f"({anchored} level-change/RESET anchors)", **common)
