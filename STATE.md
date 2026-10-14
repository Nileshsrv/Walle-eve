# STATE.md — WALL-E & EVE Bayesian Pursuit (v2)

## Run
`pip install -r requirements.txt && python app.py` → http://127.0.0.1:5000  (console `/`, guide `/guide`)
Tests: `python -m pytest -q tests` (10 pass). Demo recordings: `python make_demo.py`.
Benchmark: `python bench.py run --seeds 200-399 --agents v1,v2 --threat standard --out results/standard.jsonl`
then `python bench.py report results/*.jsonl --out results/LEADERBOARD.md` (resumable; ~0.4 s/episode for v2 on 1 CPU).

## Architecture & decisions
- Stack: Python 3.10+, numpy, Flask; vanilla JS + Canvas. In-memory single mission (`G` in app.py).
- walle_eve/: env (threats, clues, determinism keyed on (seed,step)), bayes (K-q mixture belief, exact decoy association, clue + tempering),
  eig (Monte-Carlo EIG, common random numbers), pf (400-particle cross-check), planner (Planner v1, NaivePlanner, PlannerV2),
  agents (registry/ablation ladder), metrics, logger, sim.
- Agent ladder (agents.py): naive, reference_style, v1, v2a(+learn q), v2b(+exact assoc), v2c(+EIG), v2d(+dest. reserve), v2e(+min-expected-distance target), v2(+self-cal, PF), v2_peak, v2_thompson.
- v2 defaults (tuned on seeds 100–129, evaluated on held-out 200–399): value="qmdp", eig_tau=0.4, radius 7, K=32 samples.
- UI: docked console (rail / map / tabbed dock / timeline-transport). Live and replay share one frame list; timeline scrubs frames.

## Measured (see results/LEADERBOARD.md)
standard, 200 held-out seeds: v1 26.5 steps, 45.1 battery | v2 16.6 steps (paired Δ −9.9, CI −12.5..−7.6), 22.6 battery, 100% capture, 0 deaths.
pursuit: 30.4 → 17.6. hard sensors (σ×1.5 + 10% dropout): 31.2 → 19.1; v2 log loss 3.15 vs v1 3.49.
naive loudest-signal: 2% capture. reference_style (our re-implementation): 24.3 steps.
Caveats: v2 log loss slightly WORSE than v1 on standard (2.39 vs 2.29: scans less). Gain is dominated by the min-expected-distance target; learning q is weakly identifiable (+tiny gain);
PF alarm and surprise tempering never fired in benchmarks (diagnostics only, v2 == v2e).

## Checklist
- [x] P0 benchmark harness  [x] P1 charts/metrics/telemetry/keys/matrices  [x] P2 threat levels, clues, randomize EVE, hard sensors
- [x] P3 learn q, exact association, EIG scans, destination reserve, qmdp/Thompson targets, PF check, self-cal, explainable reasons
- [x] P4 replay+scrubber, save/open recording, briefing JSON, /guide page; tests
- [ ] Not done: unknown-decoy mode, Student-t outliers, multi-step lookahead rollouts, YAML configs, Vercel/serverless deploy (state is in-memory), hold-out calibration bin criterion, multi-seed ablation of threat=calm

## Next steps
1) Recover belief quality (log loss) without losing speed: e.g. scan when EVE is close even if EIG/unit < tau. 2) Evasive-EVE model in the motion update. 3) Port sim to JS for static deployment.

## Handoff prompt
Repo is a Bayesian pursuit sim with a paired-seed benchmark and a docked Flask+Canvas console; v2 cuts steps-to-capture ~37% and battery ~50% vs v1 on 200 held-out seeds with 100% capture. Most of the gain comes from targeting the cell with minimum expected travel distance, not from learning q or the PF check. Resume from "Next steps"; keep results reproducible via bench.py and append to JOURNAL.md.
