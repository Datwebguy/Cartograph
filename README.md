# Cartograph

Verified executable world models in a Duck-style coding-agent harness for ARC-AGI-3 (ARC Prize 2026 paper track).

The agent keeps a persistent `world_model.py`, exact-replays the full observation history after every edit/action, and only plans inside the model when it is verified; otherwise it falls back to the normal Duck REPL loop.

## Files
- `PAPER.md` - paper draft (source of truth for the submission)
- `BUILD_INSTRUCTIONS.md` - spec for the harness changes and the public Kaggle notebook

## Status
- [ ] Clone Tufalabs/duck-harness and get a baseline run working
- [ ] Persistent `world_model.py` + exact-replay verifier + gating
- [ ] Public Kaggle notebook on 1-3 public games (URL: TBD)
- [ ] Fill real results into PAPER.md (Results is currently a plan, not measured data)
- [ ] Verify the arXiv references and ARC Prize submission deadline/method

## Notes
- Eligibility: the paper must link a real Kaggle code submission (ARC-AGI-2 or ARC-AGI-3 track) that demonstrates the approach. A high score is not required.
- The Results section of the paper states *expected* outcomes. Replace with measured numbers before submitting.
- The ARC Prize paper page lists no deadline; it says results are announced 2026-12-04. Confirm the cutoff in your Kaggle/ARC account.
