#!/usr/bin/env python3
"""Paired benchmark. Every agent faces the same maps, EVE trajectories and sensor noise per seed.

  python bench.py run --seeds 200-399 --agents v1,v2 --threat standard --out results/standard.jsonl
  python bench.py run --seeds 200-299 --agents v1,v2 --threat pursuit --stress hard --out results/hard.jsonl
  python bench.py report results/*.jsonl --out results/LEADERBOARD.md
"""
import argparse, glob, json, os, sys, time
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from walle_eve import Simulation, SPECS

STRESS = {"none": {}, "hard": {"sigma_mult": 1.5, "dropout": 0.10}}
MAX_STEPS = 200


def seeds_arg(s):
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def episode(job):
    agent, seed, threat, stress = job
    sim = Simulation(seed, agent=agent, threat=threat, stress=STRESS[stress], max_steps=MAX_STEPS, light=True)
    sim.run()
    return {"agent": agent, "threat": threat, "stress": stress, **sim.result()}


def cmd_run(a):
    jobs = [(ag, s, a.threat, a.stress) for ag in a.agents.split(",") for s in seeds_arg(a.seeds)]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    done = set()
    if os.path.exists(a.out):                                  # resumable
        for line in open(a.out):
            r = json.loads(line); done.add((r["agent"], r["seed"], r["threat"], r["stress"]))
    jobs = [j for j in jobs if j not in done]
    t0 = time.time()
    with open(a.out, "a") as f:
        if a.workers > 1:
            from multiprocessing import Pool
            it = Pool(a.workers).imap_unordered(episode, jobs, chunksize=4)
        else:
            it = map(episode, jobs)
        for i, r in enumerate(it, 1):
            f.write(json.dumps(r) + "\n"); f.flush()
            if i % 50 == 0:
                print(f"{i}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    print("done", len(jobs), "episodes", f"{time.time() - t0:.0f}s")


def boot(x, f=np.mean, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    bs = [f(x[rng.integers(0, len(x), len(x))]) for _ in range(n)]
    return float(f(x)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def cmd_report(a):
    rows = [json.loads(l) for p in a.files for fp in glob.glob(p) for l in open(fp)]
    groups = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        groups[(r["threat"], r["stress"])][r["agent"]][r["seed"]] = r
    out = ["# Benchmark leaderboard", "", f"Steps for uncaptured episodes are censored at {MAX_STEPS}. Intervals are 95% bootstrap CIs over seeds. "
           "Paired Δ is per-seed (same map, same EVE path, same noise) against the baseline agent.", ""]
    for (threat, stress), ags in sorted(groups.items()):
        base = a.baseline if a.baseline in ags else next(iter(ags))
        out += [f"## threat = {threat}, stress = {stress}", "",
                "| agent | n | capture | deaths | steps [95% CI] | Δ steps vs " + base + " [95% CI] | battery spent | log loss | ECE | AUC |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        order = [k for k in SPECS if k in ags]
        for ag in order:
            eps = ags[ag]
            seeds = sorted(eps)
            steps = [eps[s]["steps"] if eps[s]["captured"] else MAX_STEPS for s in seeds]
            m, lo, hi = boot(steps)
            d = ""
            if ag != base:
                common = [s for s in seeds if s in ags[base]]
                diff = [(eps[s]["steps"] if eps[s]["captured"] else MAX_STEPS) -
                        (ags[base][s]["steps"] if ags[base][s]["captured"] else MAX_STEPS) for s in common]
                dm, dlo, dhi = boot(diff)
                d = f"{dm:+.1f} [{dlo:+.1f}, {dhi:+.1f}]"
            g = lambda k: float(np.mean([eps[s][k] for s in seeds]))
            out.append(f"| {ag} | {len(seeds)} | {100 * np.mean([eps[s]['captured'] for s in seeds]):.1f}% | "
                       f"{sum(eps[s]['dead'] for s in seeds)} | {m:.1f} [{lo:.1f}, {hi:.1f}] | {d} | "
                       f"{g('spent'):.1f} | {g('log_loss'):.2f} | {g('ece'):.4f} | {g('auc'):.3f} |")
        out.append("")
    open(a.out, "w").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run"); r.add_argument("--seeds", default="200-399"); r.add_argument("--agents", default="v1,v2")
    r.add_argument("--threat", default="standard"); r.add_argument("--stress", default="none", choices=STRESS)
    r.add_argument("--out", default="results/run.jsonl"); r.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p = sp.add_parser("report"); p.add_argument("files", nargs="+"); p.add_argument("--out", default="results/LEADERBOARD.md")
    p.add_argument("--baseline", default="v1")
    args = ap.parse_args()
    cmd_run(args) if args.cmd == "run" else cmd_report(args)
