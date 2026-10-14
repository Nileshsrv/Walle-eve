# UPGRADE_PLAN.md — Reach parity with the reference, then beat it

Reference: https://walle-eve.vercel.app/ (landing + `/mission`). Observed from page text only; its code and live behaviour were not inspected, so some rows below are inferred. Items marked *(inferred)* should be confirmed by using the site.

Repo state at time of writing: v1 complete (`walle_eve/{env,bayes,planner,metrics,logger,sim}.py`, Flask `app.py`, Canvas dashboard with hover/pin map). See `STATE.md` and `JOURNAL.md`.

---

## 1. Goal and success criteria

Build an agent that is **measurably better**, not just feature-equal. "Better" must be proven on a shared benchmark, never on a single seed.

| Metric (over ≥200 seeds, paired, same envs for every agent) | Target |
|---|---|
| Capture rate | ≥ 99% |
| Battery deaths | 0 |
| Mean steps-to-capture | ≥ 25% lower than current v1 agent |
| Mean battery spent per capture | ≥ 20% lower than v1 |
| Mean log loss (nats) | below the "knows nothing" baseline (ln N_free ≈ 5.1) by a margin that beats the v1 agent |
| Calibration (ECE, reliability diagram) | no bin off the diagonal by > 0.1 with ≥ 30 samples |
| Robustness | success rate degrades < 10 pts when q is misspecified and sensor σ is 1.5× |

**Fairness rule:** the reference agent is not runnable here. Compare against (a) our v1 agent, (b) a *naive max-strength* baseline, (c) a *reference-style* baseline re-implemented from its public description (assumes q = 0.10 while truth is 0.12; scans when two hypotheses share the mass; A* to smoothed peak). Do not compare raw numbers with the site's seed-7 figures: its Brier is averaged per cell (0.005) while ours is summed over cells (~0.8).

---

## 2. Gap analysis

| # | Capability | Reference | Ours (v1) | Action | Phase |
|---|---|---|---|---|---|
| 1 | Entropy-over-time chart | yes | per-step number only | add chart | P1 |
| 2 | Calibration reliability diagram | yes | ECE scalar | add diagram (data already binned in `MetricsTracker`) | P1 |
| 3 | ROC curve (pooled over all cells) | yes | per-step AUC scalar | add pooled curve | P1 |
| 4 | Information gain per reading (nats) | yes | no | add `H_prior − H_post` per step | P1 |
| 5 | Detection precision/recall ("within one cell") | yes | no | add detection claim + confusion matrix | P1 |
| 6 | 90% credible-set size over time + overlay on map | yes | scalar only | add series + overlay | P1 |
| 7 | "Knows nothing" log-loss baseline shown | yes | no | show ln(N_free) | P1 |
| 8 | Telemetry: time budget, move/scan cost spent, blocked count, charges left | yes | battery, entropy, step | extend `state()` + panel | P1 |
| 9 | Posterior algebra as numeric matrices | yes | heatmaps only | add toggle: heatmap ↔ numbers | P1 |
| 10 | Keyboard shortcuts (space, →, r) | yes | no | add | P1 |
| 11 | Randomize EVE with seed | yes | seed switches whole map | add `randomize_eve` | P2 |
| 12 | Threat level (calm / standard / pursuit) *(inferred: changes EVE behaviour or noise)* | yes | no | add; define precisely below | P2 |
| 13 | Clue tokens (free pickup, ≈ ±3-cell Gaussian) | yes | no | add | P2 |
| 14 | Model mismatch (agent assumes q = 0.10, truth 0.12) | yes | agent knows true q | add mismatch **and** make the agent robust to it | P2/P3 |
| 15 | Particle filter (400 particles) cross-check + particle cloud overlay | yes | grid only | add SMC + disagreement alarm | P3 |
| 16 | Recorded replay with scrubber + step ledger | yes | live only | add replay from trace JSONL | P4 |
| 17 | JSON mission briefing export | yes | `/api/trace` raw | add `/api/briefing` | P4 |
| 18 | Landing/explainer page with formulas, numbers read from recorded run | yes | none | add `/` explainer, move dashboard to `/mission` | P4 |
| 19 | Public deployment (Vercel) | yes | local only | add deploy notes | P4 |

Where we are already ahead (keep): unlabeled shuffled detections, hover/pin inspector, scan pulse, procedural maps per seed, `STATE.md`/`JOURNAL.md` handoff discipline.

---

## 3. Phased plan

Work in order. After each phase update `STATE.md` (checklist, next step, 3-sentence handoff) and append to `JOURNAL.md`.

### P0 — Benchmark harness (do this first, so every later change is measurable)

Files: `bench.py`, `walle_eve/agents.py`, `results/` (git-ignored).

- Refactor the policy behind an `Agent` interface: `act(belief_state, obs) -> action`, with `Simulation(agent=...)`.
- Implement agents: `NaiveMaxStrength`, `ReferenceStyle` (q mismatch + two-hypothesis scan rule), `V1` (current planner), and later `V2` variants.
- `bench.py --seeds 0-199 --agents v1,naive,reference_style --threat standard --out results/run.json` runs paired seeds and writes per-episode rows plus an aggregate table in Markdown (mean, 95% bootstrap CI, paired difference).
- Acceptance: re-running with the same args gives identical numbers (all RNG seeded); table renders in `results/LEADERBOARD.md`.

### P1 — Evaluation and dashboard parity

Files: `metrics.py`, `sim.py` (`state()`), `static/app.js`, `templates/index.html`, `static/style.css`.

- `metrics.py`: add per-step `info_gain = H_prior − H_post`, `cred90_size`, detection claim (`mass in 3×3 around peak ≥ 0.5`) vs truth within 1 cell, pooled ROC points, reliability bins export, `baseline_log_loss = ln(N_free)`.
- Dashboard: add a collapsible **Evaluation** strip with four small canvas charts (entropy, calibration, ROC, credible-set size) and a 2×2 detection matrix; draw the 90% credible set as an outline on the map; heatmap/numbers toggle in the Bayesian panel.
- Telemetry: `moves`, `scans`, `blocked`, `move_cost_spent`, `scan_cost_spent`, `charges_used`.
- Keyboard: Space run/pause, → step, R reset (ignore when an input is focused).
- Acceptance: charts update live and match `metrics.summary()`; Playwright screenshot at 1440px and 390px shows no overflow.

### P2 — Environment parity and harder modes

Files: `env.py`, `sim.py`, `app.py`.

- `randomize_eve(seed)`: new EVE start, same map; endpoint `POST /api/reset {seed, eve_seed}`.
- **Threat level** (define explicitly so results are interpretable):
  - `calm`: q = 0.05, σ_θ = 0.20.
  - `standard`: q = 0.12, σ_θ = 0.25 (current).
  - `pursuit`: q = 0.20 and EVE steps *away* from WALL-E with probability 0.5 when within distance 4 (evasive, partially adversarial).
- **Clue tokens**: 1–3 tokens on free cells; stepping on one yields a free reading localising EVE to a Gaussian σ ≈ 1.5 cells around her *current* cell; consumed once.
- **Model mismatch**: `agent_q` (belief) may differ from `env.q`; default agent_q = env.q for v1, `0.10` for the reference-style baseline.
- **Stress knobs** for robustness tests: sensor σ multiplier, dropout probability (scan returns nothing), unknown-decoy mode (agent is not told decoy positions).
- Acceptance: each knob has a unit test; benchmark runs across all three threat levels.

### P3 — The better agent (v2)

Files: `bayes.py`, `planner.py`, new `walle_eve/pf.py`, `walle_eve/agents.py`.

Each item below is an **ablation switch** so its contribution can be measured in P0.

**3.1 Learn q online (robust to mismatch).** Keep K beliefs on a grid of motion rates `q ∈ {0.04, 0.08, 0.12, 0.16, 0.24}` with weights `w_k`. After each scan: `w_k ∝ w_k · Σ_c b_k(c) L(obs|c)` (predictive evidence), then normalise. Use the mixture `p = Σ_k w_k b_k`. Cost: K× a 14×14 convolution (negligible). This directly beats a reference that is wrong about q.

**3.2 Exact decoy data association.** Replace the heuristic decoy-match `m_j` with marginalisation over assignments. For `n = 1 + #decoys` unlabeled detections `d_1..d_n`:
`L(c) = (1/n!) Σ_{π∈S_n} f_E(d_{π(0)} | c) · Π_{k=1..n-1} f_{D_k}(d_{π(k)})`.
n ≤ 5 so ≤ 120 terms per cell; vectorise over cells. Add a Student-t outlier mixture to each `f` for robustness. Optional unknown-decoy mode: treat decoy positions as latent and learn them from repeated detections.

**3.3 Information-per-battery scan planning (replaces the entropy threshold).**
`EIG(x) = H(p) − E_{c~p, o~sensor(c,x)} [H(p | o)]`, estimated with K = 64 Monte-Carlo samples.
Score every candidate scan position `x` (restrict to cells within reach of the battery budget) by
`EIG(x) / (pathlen(pos→x) + SCAN_COST)`
and pick the best option including "scan here". This naturally triangulates: bearing readings from different positions beat repeated readings from one spot.

**3.4 Reserve v2 (fixes a known v1 limit).** The v1 reserve uses the path to the nearest pad from the *current* cell. Require instead, before committing to any leg to target `x`:
`battery − pathlen(pos→x) − scan_cost ≥ pathlen(x→nearest_pad) + 2·SCAN_COST`.
Keep the hard "return now" rule as a safety net. Acceptance: zero battery deaths on 1000 stress episodes with 1.5× σ and dropouts.

**3.5 Capture-oriented value.** Alternatives to "go to smoothed peak", benchmarked head to head:
- *Thompson*: sample `c ~ p`, A* to it (exploration for free).
- *QMDP-style*: choose the target minimising `Σ_c p(c) · pathlen(x→c)` (expected distance), which prefers central positions when the belief is bimodal.
- *Short-horizon lookahead*: depth-3 rollout over {move, scan} maximising P(capture within horizon) − λ·battery.

**3.6 Particle filter cross-check.** 400-particle SMC over the same motion and sensor model (`pf.py`). Track `KL(grid ‖ particles)`; if it exceeds a threshold for 3 steps, log a "model disagreement" warning and temper the likelihood (power 0.5) for one step. Show the particle cloud as a map overlay.

**3.7 Self-calibration without ground truth.** Track the prequential score of the agent's own *observation predictions* (mean `−log Σ_c p(c) L(obs|c)`), which needs no truth. Use it to (a) drive 3.1, and (b) set a likelihood temperature `τ` when the score drifts. Validate against the ground-truth reliability diagram, which the agent never sees.

**3.8 Explainable reasons.** Each decision's `reasoning_text` includes the numbers that decided it: top-3 EIG/cost options, reserve slack, current `w_k` over q.

Acceptance for P3: meets the Section 1 table on `standard`, and the ablation matrix (Section 5) shows each switch's effect with confidence intervals. Keep a switch only if it helps or is neutral and cheap.

### P4 — Replay, briefing, explainer, deployment

- `/api/briefing`: JSON with seed, config, outcome, per-step ledger, summary metrics, and the agent's reasons.
- Replay: load a stored trace, scrub a slider, show posterior + ledger row; numbers on the explainer page come from the stored trace file, not typed by hand.
- `/` explainer page: five-step update with formulas (prior, predict, likelihood with decoy association, multiply/discount/renormalise, spend/reserve), then link to `/mission`.
- Deployment: the app uses in-memory state, so for serverless hosting either keep the mission client-side (port the sim to JS) or host on a persistent Flask platform; note the choice in `JOURNAL.md`.

---

## 4. Ablation matrix (P3 protocol)

Run each row on seeds 0–199 across `calm / standard / pursuit`, plus a stress setting (q misspecified, σ × 1.5, 10% dropouts).

| Variant | q-learning | exact assoc. | EIG scans | reserve v2 | value rule |
|---|---|---|---|---|---|
| v1 | – | – | – | – | smoothed peak |
| +A | ✓ | – | – | – | smoothed peak |
| +B | ✓ | ✓ | – | – | smoothed peak |
| +C | ✓ | ✓ | ✓ | – | smoothed peak |
| +D | ✓ | ✓ | ✓ | ✓ | smoothed peak |
| +E | ✓ | ✓ | ✓ | ✓ | Thompson / QMDP / lookahead (3 rows) |
| reference-style | – | – | – | – | smoothed peak, q mismatch |
| naive | – | – | – | – | loudest signal |

Report: capture rate, steps-to-capture, battery per capture, deaths, log loss, ECE, with 95% bootstrap CIs and paired differences against v1.

---

## 5. Target file tree additions

```
walle-eve/
├── bench.py                    # P0 paired benchmark
├── results/                    # LEADERBOARD.md, run JSON (git-ignored)
├── tests/                      # pytest: mass conservation, A* optimality, reserve rule, assoc. vs brute force
├── walle_eve/
│   ├── agents.py               # Naive, ReferenceStyle, V1, V2 (ablation switches)
│   ├── pf.py                   # particle filter
│   └── eig.py                  # Monte-Carlo expected information gain
├── templates/{explainer,mission}.html
└── static/charts.js            # entropy / calibration / ROC / credible-set charts
```

---

## 6. Tests to write alongside

- `sum(p) == 1` after every predict/update for every map in 50 seeds.
- A* returns optimal length vs BFS on random maps.
- Reserve rule: a scripted low-battery state always produces a return move; zero deaths in 1000 stress episodes.
- Exact association matches brute-force enumeration for n = 3.
- q-learning: with true q = 0.20 and prior weights on 0.12, `w` shifts toward 0.16–0.24 within ~25 scans.
- EIG is ≥ 0 and is larger for a scan position near a bimodal belief's midpoint than for a far corner.
- Determinism: same seed and args give identical benchmark output.

---

## 7. Risks and cautions

- **Overfitting to seed 7.** Always report across ≥ 200 seeds.
- **Compute.** EIG with K = 64 over many candidate positions can be slow; restrict candidates to a battery-feasible radius and cache likelihood grids. Target < 50 ms/step.
- **Evasive EVE (pursuit mode)** makes a stationary-motion belief wrong by design; q-learning and the particle cross-check are the mitigations. Consider an evasion term in the motion model only if ablations justify it.
- **Don't leak truth.** Metrics read `env.eve_truth`; the agent must not. Add a test that agents receive no reference to the env's private fields.
- **Reference unknowns.** Threat-level semantics and clue σ are guesses from page text; verify by using the live site and adjust Section P2 accordingly.

---

## 8. Handoff prompt (paste to the next model)

> You are continuing the WALL-E & EVE project in this repo. Read `STATE.md`, `JOURNAL.md`, then this file. Execute phases in order P0 → P4: build the paired benchmark harness first, then dashboard/evaluation parity, environment modes, and the v2 agent with ablation switches (online q-learning, exact decoy association, EIG-per-battery scan planning, reserve v2, capture-oriented value, particle cross-check, self-calibration). After each phase update `STATE.md` and append to `JOURNAL.md`. Prove every improvement with paired-seed benchmark results (≥ 200 seeds, 95% bootstrap CIs); never claim superiority from a single run.

---

## Implementation status (appended after build)

Done: P0 (bench.py, agents ladder), P1 (all rows 1–10 incl. charts, detection matrix, numeric matrices, keys, telemetry), P2 (11 randomize EVE, 12 threat levels, 13 clues, 14 mismatch + stress knobs), P3 (3.1–3.8 except lookahead rollouts and unknown-decoy/Student-t), P4 (replay, briefing, guide page; deployment NOT done).
Targets vs result (standard, 200 held-out seeds): capture ≥99% ✔ (100%) · deaths 0 ✔ · steps −25% ✔ (−37%) · battery −20% ✔ (−50%) · log loss better than v1 ✘ (2.39 vs 2.29) · ECE not worse ✘ (0.0041 vs 0.0034, both small) · robustness ✔ (100% capture under pursuit and hard sensors).
