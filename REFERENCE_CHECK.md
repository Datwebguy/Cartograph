# Reference and deadline check

Checked 2026-11-08 from a sandbox session. arXiv entries were looked up in arXiv's own API (title, authors, date, abstract). "Confirmed" means the cited paper exists and its abstract supports how PAPER.md describes it.

## arXiv references

| ID | Found | Matches PAPER.md? |
| --- | --- | --- |
| 2605.05138 | Rodionov, "Executable World Models for ARC-AGI-3 in the Era of Coding Agents" (2026-05-06) | **Confirmed.** Executable Python world model, verification against previous observations, planning through the model, code released at astroseger/arc-3-agents-baseline1. |
| 2607.15439 | Rodionov, "Do Coding Agents Need Executable World Models, Simplification, and Verification to Solve ARC-AGI-3?" (2026-07-16) | **Confirmed**, and it matters: it reports variant differences "smaller than anticipated", textual beating flexible-interface executable, and the textual variant also completing every public level at max effort with gpt-5.6-sol. The verification variant still ranked first throughout. PAPER.md now says so. |
| 2610.00834 | Wensen Wu, "Kepler: Auditable World Models for ARC-AGI-3" (2026-09-30) | **Confirmed.** "Retrospective transition checks and conditional prediction checks"; "100.00 RHAE on all 25 public games" under one frozen Claude Opus 5 configuration. |
| 2607.01531 | Courtis, Li, Sanner, "OPINE-World: ... Ontology-error-Prioritized Interactive Exploration ..." (2026-07-01) | **Partly.** Exists; authors fit "Courtis et al." The abstract supports ontology-error-prioritized exploration. It does **not** mention "exact-replay admission of programmatic models". Unconfirmed from the abstract; check the full text or drop the phrase. PAPER.md carries an `[UNCONFIRMED]` tag. |

## Other claims and links in PAPER.md

| Claim / link | Status |
| --- | --- |
| Duck is the Milestone 1 winner (arcprize.org/blog/arc-prize-2026-milestone-1) | **Confirmed**: "1st Place - Tufa Labs, 'The Duck'", $37.5K, "Runs Qwen 3.6 27B FP8 locally". |
| Duck is a minimal Python-REPL harness, single GPU (tufalabs.ai/research/duck-harness) | **Confirmed**: "minimal coding harness with a Python interpreter ... REPL"; Kaggle evaluation "constrained to a single GPU". |
| "Hand-crafted tools were found to hurt more than help" | **Not found** on the Tufa Labs page. Possibly in their Kaggle write-up (not reachable). Tagged `[UNCONFIRMED]`. |
| github.com/astroseger/arc-3-agents-baseline1 | **Could not check.** The session's GitHub access is limited to this repo. The paper abstract itself gives this URL, so it is probably right. Tagged. |
| "A tight, fully open combination ... has not been the dominant shipped entry on the Kaggle leaderboard" | **No evidence checked.** Tagged; soften or cite. |
| Competition rules: offline, no internet, open source, single GPU (arcprize.org/competitions/2026) | Page reachable; only the single-GPU and open-source points were seen via the Duck/Milestone pages. Re-read the rules page yourself before submitting. |

## Paper deadline and submission method

What the official pages say (read directly):

- `arcprize.org/competitions/2026`, Key Dates: "November 2, 2026 - Submissions due; **November 8, 2026 - Papers due**; December 4, 2026 - Results announced".
- `arcprize.org/competitions/2026/paper`: no deadline, no method. It says paper submissions "must be linked to a Kaggle code submission (ARC-AGI-2 or ARC-AGI-3 track)", that the code "need not achieve a high score", and that results are announced December 4, 2026. Both pages also say "ARC Prize 2026 has finished."
- The competition page links the paper track at `https://www.kaggle.com/competitions/arc-prize-2026-paper-track/overview`.

What could **not** be established:

- **Time of day and timezone** of the November 8 cutoff: not stated on any page read.
- **The submission method** (where and in what form the paper is uploaded): not stated on the ARC Prize pages. It is presumably on the Kaggle paper-track page, but Kaggle returned 404 to this session (it blocks the sandbox; the URL itself is the one the ARC page links to), so that page was not read.
- November 8, 2026 is the date this check was run. If the cutoff is end of day in some timezone it may be hours away or already past. Confirm on the Kaggle paper-track page and in your Kaggle account now.

## Update: Kaggle Writeup form (supplied by the author, 2026-11-08)

- Method: a Kaggle **Writeup** on the Paper Track page (title, subtitle, card image, description, project links, optional files, optional DOI).
- Cutoff shown on the form: **Nov 10, 2026 at 12:59 AM GMT+1** (= Nov 9, 2026 23:59 UTC). This supersedes the "November 8" date on the ARC Prize page.
- Text to paste is in `WRITEUP.md`.

## Update: unconfirmed claims removed
The Duck "hand-crafted tools" sentence, the OPINE-World "exact-replay admission" phrase and the leaderboard-novelty sentence were deleted from PAPER.md. The baseline1 code link was kept: the abstract of arXiv 2605.05138 itself gives that URL. The statement that the verification gate "reduces" wasted actions was changed to "is designed to reduce".
