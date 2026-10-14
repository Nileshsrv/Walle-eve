# JOURNAL.md
## Session 1
- Created scaffold + STATE.md.
- Bug: `mkdir -p a/{b,c}` under /bin/sh created a literal dir; first batch of files failed to write. Fixed with explicit mkdir and rewrote files.
- Design: scan returns unlabeled detections (EVE + decoys) so decoys genuinely confuse max-strength search; the Bayesian agent knows decoy *positions* (beacons are infrastructure) and discounts detections matching a decoy signature (m_j) instead of trusting the loudest one.
- Design: EVE moves BEFORE the agent action each tick so predict→update ordering is consistent with the observation time.
- Design: initial free scan implements "prior updated by initial bearing/strength".
- Formulas: see STATE.md. Metrics ROC-AUC computed per step as P(score(true cell) > score(other free cell)) with ties 0.5.
- Results: seeds 0–29 → 30/30 captures, mean 26.6 steps, max 71, min battery 6; modes: pursue 479, scan 300, return 25, recharge 23.
- Known limits: reserve uses A* path length from current cell only (no lookahead for moves toward target); posterior ECE is coarse (one true cell per step).

## Session 2 — left map panel
- Added map interactivity in static/app.js (cellAt/describe/updateInfo/mapEvents/animatePulse) + legend/inspector in index.html/style.css.
- Bug fixed: tooltip overflowed the right edge of the canvas; now clamped/flipped within the map bounds.
- QA: headless Chromium (Playwright) screenshot; only console error is the Google Fonts fetch (sandbox has no network; fallback fonts apply).
- Note: background servers die between tool calls in this sandbox; start server and run the screenshot in one command.

## Session 3
- Compared against walle-eve.vercel.app (page text only). Wrote UPGRADE_PLAN.md: gap table, phased roadmap, v2 agent design, ablation protocol.

## Session 4 — implementing UPGRADE_PLAN
- env: determinism keyed on (seed, step) so agents share EVE paths/noise (paired benchmark). Threat levels, clues, dropout, sigma_mult, eve_seed.
- bayes: K=5 belief mixture over q (evidence-weighted, weight floor 0.01); exact decoy association via permanents: w_j ∝ perm(G without row j), L=eps+Σ w_j F_j.
- eig: K=32 MC samples with common random numbers, decoys ignored (over-estimates info in cluttered scans); candidates = even-parity cells within BFS radius 7 + current cell.
- Tuning (seeds 100–129): value rule dominated. peak 26.7 | thompson 18.2 | qmdp 17.5 steps at tau .09; qmdp tau .5 → 15.5 steps. Chose tau .4. Evaluated on 200–399 (not tuned on).
- Bug: _all_pairs recomputed BFS per pair (8 s/episode) → compute one BFS row per source.
- Finding: q is weakly identifiable (E[q]=.095/.118/.143 for true .05/.12/.20) → test asserts ordering only.
- Finding: PF alarm never fired; surprise tempering never changed results (v2 ≡ v2e).
- Sandbox: background processes die when a tool call ends; run benchmarks in foreground chunks (resumable JSONL).
- UI: docked console (not card grid); mobile layout reorders map first; fixed top-bar overflow.
- Results: results/LEADERBOARD.md (standard 11 agents × 200 seeds; pursuit & hard 4 agents × 100 seeds).
