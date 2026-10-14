# 🤖 WALL-E & EVE · Bayesian Pursuit

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![NumPy](https://img.shields.io/badge/numpy-1.24+-013243.svg?style=flat-square&logo=numpy&logoColor=white)](https://numpy.org/)
[![Tests](https://img.shields.io/badge/tests-10%20passed-success.svg?style=flat-square)](tests/test_core.py)
[![Capture Rate](https://img.shields.io/badge/capture%20rate-100%25-brightgreen.svg?style=flat-square)](LEADERBOARD.md)
[![Battery Deaths](https://img.shields.io/badge/battery%20deaths-0-brightgreen.svg?style=flat-square)](LEADERBOARD.md)

> **Active Bayesian spatial inference and pursuit simulation under battery constraints, noisy sensor observations, and deceptive decoy beacons.**

---
Link of project: [https://walle-eve.netlify.app/](https://walle-eve.netlify.app/)
## 📌 Table of Contents

- [Overview](#-overview)
- [Key Results & Leaderboard](#-key-results--leaderboard)
- [How It Thinks: The 5-Stage Cycle](#-how-it-thinks-the-5-stage-cycle)
- [Agent Ablation Ladder](#-agent-ablation-ladder)
- [Web Console & Interactive Features](#-web-console--interactive-features)
- [Project Architecture](#-project-architecture)
- [Quickstart & Installation](#-quickstart--installation)
- [Benchmarking & Evaluation](#-benchmarking--evaluation)
- [REST API Reference](#-rest-api-reference)
- [Engineering Insights & Lessons Learned](#-engineering-insights--lessons-learned)

---

## 🛰️ Overview

In a procedurally generated 14×14 grid world with obstacles, solar recharge pads, and high-amplitude decoy beacons, **WALL-E** must locate and capture a moving **EVE** on a strict battery budget.

WALL-E **never receives ground-truth coordinates** for EVE. Instead, each scan returns noisy bearing ($\theta$) and exponential signal strength ($s$) observations. To make the pursuit adversarial:
- **Unlabeled Detections:** Scans return an unordered list of detections where EVE's signal is mingled with decoy beacons.
- **Dynamic Motion:** EVE drifts stochastically with drift rate $q$, or actively evades WALL-E under pursuit threat.
- **Energy Constraints:** Moving costs $1$ battery unit, scanning costs $3$ units, and battery depletion results in mission failure (death).

The **v2 Adaptive Agent** uses exact Bayesian filtering, online hypothesis estimation for target dynamics, Expected Information Gain (EIG) scan scheduling, destination-safe battery budgeting, and QMDP minimum-expected-distance path planning to systematically outperform greedy and heuristic baselines.

```
       [ EVE Drifts ] ─────────► [ Bayesian Predict ]
             │                          │
       [ Noisy Scan ]                   ▼
     (EVE + Decoys)   ─────────► [ Exact Decoy Association ]
                                        │
                                        ▼
                                 [ Likelihood Update ]
                                        │
                                        ▼
 [ Safe Action Executed ] ◄── [ EIG Scan / QMDP Target ]
```

---

## 📊 Key Results & Leaderboard

All agents are evaluated on a **paired-seed benchmark** over 200 held-out seeds (`seeds 200–399`). Every agent confronts the exact same procedurally generated maps, identical EVE movement paths, and identical sensor noise draws.

### Benchmark: `threat = standard`, `stress = none` (200 Held-Out Seeds)

| Agent | Capture Rate | Battery Deaths | Steps to Capture [95% CI] | $\Delta$ Steps vs v1 [95% CI] | Battery Spent | Log Loss (nats) | ECE | ROC-AUC |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`naive`** (loudest signal) | 2.0% | 0 | 196.8 [193.0, 199.5] | +170.2 [+165.7, +174.0] | 439.2 | 1.84 | 0.0013 | 0.986 |
| **`reference_style`** | 100.0% | 0 | 24.3 [22.2, 26.6] | -2.2 [-4.2, -0.6] | 36.2 | 2.75 | 0.0045 | 0.950 |
| **`v1` baseline** | 100.0% | 0 | 26.5 [24.2, 29.2] | baseline | 45.1 | 2.29 | 0.0034 | 0.969 |
| **`v2a`** (+ learn $q$) | 100.0% | 0 | 25.8 [23.8, 28.0] | -0.7 [-1.8, +0.1] | 43.7 | 2.29 | 0.0034 | 0.969 |
| **`v2b`** (+ exact association) | 100.0% | 0 | 25.0 [22.9, 27.3] | -1.5 [-3.3, -0.2] | 42.0 | 2.30 | 0.0037 | 0.971 |
| **`v2c`** (+ EIG scan planning) | 100.0% | 0 | 23.8 [21.6, 26.3] | -2.7 [-5.0, -0.5] | 38.1 | 2.16 | 0.0036 | 0.970 |
| **`v2d`** (+ destination reserve) | 100.0% | 0 | 24.0 [21.7, 26.5] | -2.5 [-4.9, -0.3] | 38.2 | 2.16 | 0.0036 | 0.970 |
| **`v2e`** (+ min-expected-dist) | 100.0% | 0 | 16.6 [16.0, 17.2] | **-9.9 [-12.5, -7.6]** | **22.6** | 2.39 | 0.0041 | 0.966 |
| **`v2` adaptive (full)** | **100.0%** | **0** | **16.6 [16.0, 17.2]** | **-9.9 [-12.5, -7.6]** | **22.6** | 2.39 | 0.0041 | 0.966 |

### Stress Benchmark: `threat = standard`, `stress = hard` ($\sigma \times 1.5$, 10% Dropouts)

| Agent | Capture Rate | Battery Deaths | Steps to Capture [95% CI] | $\Delta$ Steps vs v1 | Battery Spent | Log Loss | ROC-AUC |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`reference_style`** | 100.0% | 0 | 34.0 [29.7, 38.8] | +2.8 [-0.5, +6.9] | 50.4 | 3.57 | 0.900 |
| **`v1` baseline** | 100.0% | 0 | 31.2 [27.6, 35.2] | baseline | 52.9 | 3.49 | 0.914 |
| **`v2` adaptive** | **100.0%** | **0** | **19.1 [18.1, 20.0]** | **-12.2 [-16.0, -8.7]** | **28.4** | **3.15** | **0.936** |

> [!TIP]
> **Summary of Gains:** Compared to `v1`, the full `v2` agent cuts capture steps by **~37%** and reduces battery expenditure by **~50%** while maintaining **100% capture** and **zero battery deaths**. Under hard sensor stress, `v2` preserves its margin, achieving lower log loss ($3.15$ vs $3.49$) and superior ROC-AUC ($0.936$ vs $0.914$).

---

## 🧠 How It Thinks: The 5-Stage Cycle

Each mission step executes five distinct phases:

### 1. Motion & Drift
EVE transitions according to motion rate $q$ (calm: $0.05$, standard: $0.12$, pursuit: $0.20$ with adversarial evasion). The simulation evaluates EVE's move before WALL-E's action, ensuring prediction happens at observation time.

### 2. Bayesian Predict (Markov Transition)
The probability mass is smeared across adjacent traversable cells while strictly conserving total probability ($1.0$):
$$p'_t(c) = (1 - q) p_{t-1}(c) + q \sum_{n \in \text{nbrs}(c)} \frac{p_{t-1}(n)}{\text{deg}(n)}$$
In `v2`, the agent maintains an online mixture over $K=5$ candidate rates $q \in \{0.04, 0.08, 0.12, 0.16, 0.24\}$, reweighted at every scan by marginal observation likelihood.

### 3. Unlabeled Sensor Observation & Decoy Association
A scan returns $M$ detections without identity labels. Greedy agents gravitate toward high-amplitude decoys. `v2` computes the exact association weight $w_j = P(\text{detection } j \text{ is EVE} \mid \text{all detections})$ by calculating the matrix permanent of detection-to-decoy Gaussian affinities:
$$W_j = \text{perm}\left(G_{-j}\right) \implies w_j = \frac{W_j}{\sum_{k} W_k}$$
where $G_{-j}$ represents the affinity matrix with candidate row $j$ excluded.

### 4. Bayesian Update & Self-Calibration
Spatial likelihoods combine circular Gaussian angular error and exponential signal decay:
$$L(c) = \epsilon + \sum_{j} w_j \cdot \mathcal{N}\left(\theta_j; \angle(c, x), \sigma_\theta^2\right) \cdot \mathcal{N}\left(s_j; a e^{-d(c, x)/5}, \sigma_s^2\right)$$
The posterior is obtained via $p(c) \propto p'(c) \cdot L(c)$. The current cell is discounted ($\times 0.06$) since WALL-E did not capture EVE there. When observation log-likelihood drifts, a self-calibration temperature factor $\tau$ tempers the likelihood.

### 5. Decision Planning & Safety Reserves
Actions are selected under strict battery constraints:
- **EIG Active Sensing:** Calculates Monte-Carlo Expected Information Gain per unit battery cost:
  $$\text{EIG}(x) = H(p) - \mathbb{E}_{c \sim p, o \sim \text{sensor}(c, x)}\left[H(p \mid o)\right]$$
  Scans are scheduled only when $\frac{\text{EIG}(x)}{\text{pathlen}(x) + \text{cost}} \ge \tau$.
- **Destination Battery Reserve:** Before committing to a move towards target $x$, WALL-E verifies:
  $$\text{battery} - \text{pathlen}(\text{pos} \to x) - \text{SCAN\_COST} \ge \text{pathlen}(x \to \text{nearest\_pad}) + 2 \times \text{SCAN\_COST}$$
- **QMDP Minimum-Expected-Distance Target:** Rather than aiming for the modal peak (which oscillates on bimodal beliefs), `v2` targets the cell $x^*$ that minimizes expected travel distance:
  $$x^* = \arg\min_{x} \sum_{c} p(c) \cdot \text{pathlen}(x \to c)$$

---

## 🪜 Agent Ablation Ladder

The codebase features an ablation ladder in [`walle_eve/agents.py`](walle_eve/agents.py) isolating every algorithmic enhancement:

| Agent Identifier | Key Mechanism | Target Selection | Scan Decision |
|---|---|---|---|
| `naive` | Loudest signal tracking | Max signal detection | Periodic / Greedy |
| `reference_style` | Re-implementation of reference model ($q=0.10$ fixed) | Smoothed belief peak | 2-hypothesis entropy split |
| `v1` | Baseline grid Bayes + Current-cell reserve | Smoothed belief peak | Static entropy threshold |
| `v2a` | + Online Bayesian mixture learning $q$ | Smoothed belief peak | Static entropy threshold |
| `v2b` | + Exact decoy association (matrix permanents) | Smoothed belief peak | Static entropy threshold |
| `v2c` | + Monte-Carlo EIG scan planning | Smoothed belief peak | EIG per battery unit |
| `v2d` | + Destination-aware battery reserve | Smoothed belief peak | EIG per battery unit |
| `v2e` | + Minimum expected travel distance (QMDP) | Expected distance $x^*$ | EIG per battery unit |
| `v2` (full) | + Self-calibration + 400-particle SMC cross-check | Expected distance $x^*$ | EIG per battery unit |
| `v2_thompson` | v2 with Thompson sampling target selection | Sample $c \sim p$ | EIG per battery unit |

---

## 🖥️ Web Console & Interactive Features

The included Flask application delivers a sleek, responsive mission control interface:

### 1. Landing Page (`/`)
- Ambient particle canvas background with dark/gold aesthetic.
- Key empirical metrics read live from reproducible benchmark runs.
- Direct links to the Mission Console and the interactive Guide.

### 2. Mission Console (`/mission`)
- **Interactive Canvas Map:** Real-time probability heatmap, A* path overlay, decoy beacons, clue tokens, 90% credible set boundary, and particle filter cloud.
- **Cell Inspector:** Hover or click any cell to inspect coordinates, traversal cost, occupancy prior, sensor likelihood, and posterior probability.
- **Setup Rail:** Adjust seed, EVE seed, agent variant, threat levels (`calm`, `standard`, `pursuit`), and toggle hard sensor noise.
- **Power & Vitals Telemetry:** Live battery gauge with dynamic safety reserve threshold, steps count, scans performed, and entropy metrics.
- **Belief Update Inspector:** Live decomposition tab displaying **Prior**, **Likelihood**, and **Posterior** heatmaps with a numeric matrix toggle.
- **Evaluation & Scores:** Real-time canvas charts rendering:
  - Uncertainty over time ($H / H_{\max}$ and 90% credible set size)
  - Information gained per step (nats)
  - Calibration reliability curve (predicted probability vs empirical frequency)
  - Pooled ROC curve and 2×2 detection confusion matrix
- **VCR Timeline Transport:** Scrub through mission frames, play, pause, step forward/backward, adjust playback speed, or replay saved JSON runs.
- **Keyboard Shortcuts:**
  - <kbd>Space</kbd>: Run / Pause
  - <kbd>→</kbd> / <kbd>←</kbd>: Step forward / backward
  - <kbd>Home</kbd> / <kbd>End</kbd>: Jump to mission start / conclusion
  - <kbd>R</kbd>: Relaunch mission

### 3. Reasoning Guide (`/guide`)
- In-depth, formula-annotated breakdown of the five pursuit stages.
- Live data telemetry ingested directly from recorded demo runs.
- Interactive, searchable Markdown benchmark leaderboard.

---

## 📂 Project Architecture

```
walle-eve/
├── app.py                  # Flask web server, API routes, and mission state
├── bench.py                # Resumable paired benchmark runner & report generator
├── make_demo.py            # Generates static demo runs for replay & guide
├── requirements.txt        # Minimal dependencies (numpy, flask)
├── STATE.md                # Engineering state, decisions, and handoff log
├── UPGRADE_PLAN.md         # Mathematical specifications & ablation protocol
├── LEADERBOARD.md          # Published paired benchmark results
│
├── walle_eve/              # Core algorithmic package
│   ├── __init__.py         # Public exports (Simulation, GridEnv, Belief, Agent)
│   ├── env.py              # Grid world, obstacles, sensor physics, clues, decoys
│   ├── bayes.py            # Belief grid, q-mixture, permanents, likelihoods
│   ├── eig.py              # Monte-Carlo Expected Information Gain (EIG)
│   ├── pf.py               # 400-particle Sequential Monte Carlo (SMC) cross-check
│   ├── planner.py          # A*, BFS, NaivePlanner, Planner v1, PlannerV2
│   ├── agents.py           # Agent registry, configuration specs, and ladder
│   ├── metrics.py          # Log loss, calibration (ECE), ROC-AUC, credible sets
│   ├── logger.py           # Structured JSONL event tracer
│   └── sim.py              # Mission simulation harness and telemetry state
│
├── templates/              # Jinja2 HTML templates
│   ├── landing.html        # Landing page & feature showcase
│   ├── index.html          # Full-featured Mission Console
│   └── guide.html          # "How it thinks" interactive guide
│
├── static/                 # Frontend assets
│   ├── app.js              # Console logic, canvas rendering, transport scrubber
│   └── style.css           # Modern dark-gold design system
│
├── configs/                # Map configurations (seed_7_default.json)
├── data/runs/              # Pre-recorded mission runs for replay
├── results/                # Benchmark JSONL logs and leaderboard
└── tests/
    └── test_core.py        # 10 unit tests (mass conservation, A*, permanents, etc.)
```

---

## ⚡ Quickstart & Installation

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Installation
```bash
git clone https://github.com/Nileshsrv/Walle-eve.git
cd Walle-eve

# Create and activate virtual environment (optional but recommended)
python -m venv .venv
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch the Web Console
```bash
python app.py
```
Open your browser and navigate to:
- **Landing Page:** [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
- **Mission Console:** [http://127.0.0.1:5000/mission](http://127.0.0.1:5000/mission)
- **Interactive Guide:** [http://127.0.0.1:5000/guide](http://127.0.0.1:5000/guide)

### 4. Run the Test Suite
```bash
python -m pytest -q tests
```
*Expected output:* `10 passed in ~40s`

---

## 🔬 Benchmarking & Evaluation

The benchmark harness ensures reproducible, paired scientific comparisons.

### Generate Demo Runs
```bash
python make_demo.py
```

### Run a Paired Benchmark
Run 200 held-out seeds across `v1` and `v2` under standard conditions:
```bash
python bench.py run --seeds 200-399 --agents v1,v2 --threat standard --out results/standard.jsonl
```

Run stress tests with sensor degradation ($\sigma \times 1.5$ and 10% dropouts):
```bash
python bench.py run --seeds 200-299 --agents v1,v2 --threat pursuit --stress hard --out results/hard.jsonl
```

### Generate the Leaderboard
Aggregate JSONL logs into a Markdown leaderboard with bootstrap confidence intervals:
```bash
python bench.py report results/*.jsonl --out results/LEADERBOARD.md
```

---

## 🔌 REST API Reference

The Flask backend provides a clean JSON API for headless control and automation:

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/agents` | GET | List all available agent configurations and ablation specs. |
| `GET /api/state` | GET | Retrieve full metadata and frame history of the active mission. |
| `POST /api/reset` | POST | Initialize a new mission with `{seed, eve_seed, agent, threat, stress}`. |
| `POST /api/step` | POST | Advance simulation by `n` steps (default: 1). |
| `GET /api/trace` | GET | Stream raw newline-delimited JSON (NDJSON) event logs. |
| `GET /api/briefing` | GET | Download an exportable JSON mission briefing. |
| `GET /api/leaderboard` | GET | Fetch formatted Markdown leaderboard data. |
| `GET /api/runs` | GET | Enumerate saved demo run recordings. |
| `GET /api/runs/<name>` | GET | Retrieve full frame sequence for a saved run. |

---

## 💡 Engineering Insights & Lessons Learned

1. **Where the Gain Actually Came From:**
   Ablation testing proved that the single largest performance jump came from **QMDP-style target selection** (`v2e`), cutting ~7.4 steps over `v2d`. When belief mass splits into multiple modes across obstacles, targeting the modal peak causes jitter and backtracking; minimizing expected travel distance drives WALL-E toward strategic central intersections.
2. **Weak Identifiability of $q$:**
   Online estimation of EVE's motion rate $q$ from noisy bearings alone is weakly identifiable over short horizons. While the Bayesian mixture correctly orders $E[q \mid \text{calm}] < E[q \mid \text{standard}] < E[q \mid \text{pursuit}]$, it provides modest empirical pursuit gains.
3. **Decoy Permanents vs Greedy Association:**
   In environments with multiple decoys, greedy nearest-neighbor associations easily fall into local traps. Computing matrix permanents over the full permutation group $S_n$ marginalizes uncertainty accurately with negligible computational overhead ($n \le 5 \implies \le 120$ operations).
4. **Active Sensing Trade-off:**
   `v2` scans less frequently than `v1` because scans require 3 battery units and stationary turns. Consequently, `v2` reaches EVE much faster with half the battery consumption, accepting a minor trade-off in belief sharpness (log loss $2.39$ vs $2.29$) to maximize pursuit efficiency.

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
