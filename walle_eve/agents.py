"""Agent registry: every agent is (belief model, planner, optional particle cross-check).
Ablation ladder v1 -> v2a -> v2b -> v2c -> v2d -> v2 isolates each improvement."""
from __future__ import annotations
from dataclasses import dataclass
from .bayes import Belief
from .planner import Planner, NaivePlanner, PlannerV2
from .pf import ParticleFilter

QGRID = (0.04, 0.08, 0.12, 0.16, 0.24)
SPECS = {
    "naive":           dict(label="Naive loudest-signal",       q="env", learn=False, assoc="heuristic", cal=False, pf=False, planner="naive"),
    "reference_style": dict(label="Reference-style (q=0.10)",   q=[0.10], learn=False, assoc="heuristic", cal=False, pf=False, planner="v1", kw=dict(scan_rule="two_hyp")),
    "v1":              dict(label="v1 baseline",                q="env", learn=False, assoc="heuristic", cal=False, pf=False, planner="v1"),
    "v2a":             dict(label="+ learn q",                  q=QGRID, learn=True,  assoc="heuristic", cal=False, pf=False, planner="v1"),
    "v2b":             dict(label="+ exact decoy association",  q=QGRID, learn=True,  assoc="exact",     cal=False, pf=False, planner="v1"),
    "v2c":             dict(label="+ EIG scan planning",        q=QGRID, learn=True,  assoc="exact",     cal=False, pf=False, planner="v2", kw=dict(reserve2=False, value="peak")),
    "v2d":             dict(label="+ destination reserve",      q=QGRID, learn=True,  assoc="exact",     cal=False, pf=False, planner="v2", kw=dict(reserve2=True, value="peak")),
    "v2e":             dict(label="+ min-expected-distance target", q=QGRID, learn=True, assoc="exact",   cal=False, pf=False, planner="v2", kw=dict(reserve2=True, value="qmdp")),
    "v2":              dict(label="v2 adaptive (full)",         q=QGRID, learn=True,  assoc="exact",     cal=True,  pf=True,  planner="v2", kw=dict(reserve2=True, value="qmdp")),
    "v2_peak":         dict(label="v2 with peak target",        q=QGRID, learn=True,  assoc="exact",     cal=True,  pf=True,  planner="v2", kw=dict(reserve2=True, value="peak")),
    "v2_thompson":     dict(label="v2 with Thompson target",    q=QGRID, learn=True,  assoc="exact",     cal=True,  pf=True,  planner="v2", kw=dict(reserve2=True, value="thompson")),
}


@dataclass
class Agent:
    name: str
    label: str
    belief: Belief
    planner: Planner
    pf: ParticleFilter | None


def agent_list():
    return [{"id": k, "label": v["label"]} for k, v in SPECS.items()]


def build_agent(name, env, seed=0, pf=True, planner_kw=None):
    s = SPECS[name]
    qs = [env.q] if s["q"] == "env" else s["q"]
    belief = Belief(env.free_mask, env.decoys, qs=qs, learn_q=s["learn"], assoc=s["assoc"], self_cal=s["cal"])
    kw = dict(s.get("kw", {}))
    kw.update(planner_kw or {})
    cls = {"naive": NaivePlanner, "v1": Planner, "v2": PlannerV2}[s["planner"]]
    planner = cls(env.free_mask, env.pads, env.bmax, seed=seed, **kw)
    return Agent(name, s["label"], belief, planner,
                 ParticleFilter(env.free_mask, 400, seed) if (s["pf"] and pf) else None)
