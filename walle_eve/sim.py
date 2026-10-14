"""Simulation orchestrator: env + agent (belief, planner, particle check) + metrics + trace."""
from __future__ import annotations
import os
import numpy as np
from .env import GridEnv, load_config, make_config
from .agents import build_agent
from .metrics import MetricsTracker
from .logger import TraceLogger
from .bayes import Belief

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs")
r4 = lambda a: np.round(a, 4).tolist()
KL_ALARM, KL_STREAK = 0.6, 3


class Simulation:
    def __init__(self, seed=7, cfg=None, agent="v2", threat="standard", eve_seed=None, stress=None,
                 max_steps=300, trace_path=None, console=False, light=False, planner_kw=None):
        if cfg is None:
            f = os.path.join(CONFIG_DIR, f"seed_{seed}_default.json")
            cfg = load_config(f) if os.path.exists(f) else make_config(seed)
        self.cfg, self.seed, self.light, self.max_steps = cfg, cfg.get("seed", seed), light, max_steps
        self.stress = stress or {}
        self.threat, self.eve_seed = threat, eve_seed
        self.env = GridEnv(cfg, threat=threat, eve_seed=eve_seed, sigma_mult=self.stress.get("sigma_mult", 1.0),
                           dropout=self.stress.get("dropout", 0.0))
        self.agent = build_agent(agent, self.env, seed=self.seed, pf=not light, planner_kw=planner_kw)
        self.belief, self.planner, self.pf = self.agent.belief, self.agent.planner, self.agent.pf
        self.metrics = MetricsTracker(self.env.free_mask)
        self.logger = TraceLogger(trace_path, console)
        self.frames, self.path, self.last = [], [self.env.walle], None
        self.last_scan = self.last_scan_pos = None
        self.kl, self.kl_streak, self.warnings = 0.0, 0, 0
        # Free opening reading: updates the uniform prior (cost 0).
        obs = self.env.scan_obs()
        L = self.belief.likelihood(obs, self.env.walle)
        self.last_scan, self.last_scan_pos = obs, self.env.walle
        if self.pf:
            self.pf.update(L, self.env.walle)
        H0 = self.belief.entropy()
        post = self.belief.update(L, self.env.walle)
        self.prior_view, self.lik_view, self.post_view = np.full_like(post, 1 / self.belief.nfree) * self.env.free_mask, \
            (L / max(L.max(), 1e-12)) if L is not None else np.ones_like(post), post
        self._record(0, "init-scan", obs, "Opening reading (free): the uniform prior is updated by the first bearing and strength.",
                     "scan", None, H0 - self.belief.entropy())

    @property
    def done(self):
        return self.env.captured or self.env.dead or self.env.t >= self.max_steps

    def step(self):
        if self.done:
            return self.last
        e = self.env
        ctx = {"last_scan": self.last_scan, "last_scan_pos": self.last_scan_pos, "clues": sorted(e.clues)}
        dec = self.planner.decide(self.belief, e.walle, e.battery, ctx)
        info = e.step(dec.action)
        self.path.append(e.walle)
        self.prior_view = self.belief.predict()
        if self.pf:
            self.pf.predict(self.belief.q_mean)
        obs, L = info["obs"], None
        if obs and obs["detections"]:
            L = self.belief.likelihood(obs, e.walle)
            self.last_scan, self.last_scan_pos = obs, e.walle
        if info["clue"]:
            Lc = self.belief.clue_likelihood(info["clue"])
            L = Lc if L is None else L * Lc
        H_prior = self.belief.entropy_of(self.prior_view)
        self.post_view = self.belief.update(L, e.walle)
        self.lik_view = (L / max(L.max(), 1e-12)) if L is not None else np.ones_like(self.post_view)
        note = ""
        if self.pf:
            self.pf.update(L, e.walle)
            self.kl = self.pf.kl_from(self.post_view)
            self.kl_streak = self.kl_streak + 1 if self.kl > KL_ALARM else 0
            if self.kl_streak >= KL_STREAK:
                self.warnings += 1; self.kl_streak = 0; self.belief.temper_next = self.belief.self_cal
                note += f" ⚠ grid and particle filters disagree (KL {self.kl:.2f}); tempering next reading."
        if self.belief.surprised:
            note += " ⚠ surprising reading: likelihood tempered."
        text = dec.reason + (" Bumped wall." if info["bumped"] else "") + (" Clue picked up." if info["clue"] else "") + note
        if info["captured"]:
            text += " ★ EVE captured!"
        elif info["dead"]:
            text += " ✖ Battery depleted."
        return self._record(e.t, dec.action, obs, text, dec.mode, dec, H_prior - self.belief.entropy())

    def _record(self, step, action, obs, text, mode, dec, info_gain):
        e = self.env
        row = self.metrics.update(self.belief.p, e.eve_truth, info_gain)       # ground truth used for scoring only
        if self.light:
            self.last = {"step": step, "mode": mode, "plan": [], "reserve": 0}
            return self.last
        H = round(self.belief.entropy(), 4)
        self.last = self.logger.log(
            step=step, action=action, mode=mode, battery=e.battery, observation=obs, belief_entropy=H,
            posterior_matrix=r4(self.belief.p), reasoning_text=text, metrics=row, walle=list(e.walle),
            plan=[list(c) for c in (dec.path if dec else [])], reserve=(dec.reserve if dec else 0))
        self.frames.append({
            "step": step, "action": action, "mode": mode, "battery": e.battery, "entropy": H,
            "info_gain": round(info_gain, 4), "reason": text, "walle": list(e.walle), "eve": list(e.eve_truth),
            "belief": r4(self.belief.p), "prior": r4(self.prior_view), "lik": r4(self.lik_view),
            "pf": self.pf.counts().tolist() if self.pf else None, "kl": round(self.kl, 3),
            "cred90": self.belief.credible_cells(), "plan": [list(c) for c in (dec.path if dec else [])],
            "reserve": dec.reserve if dec else 0, "clues": [list(c) for c in sorted(e.clues)],
            "q": [round(float(w), 3) for w in self.belief.w], "options": dec.options if dec else [],
            "captured": e.captured, "dead": e.dead,
            "spend": {"moves": e.moves, "scans": e.scans, "blocked": e.blocked, "move_cost": e.move_spent,
                      "scan_cost": e.scan_spent, "idle_cost": e.idle_spent, "charges": e.charges, "clues": e.clues_taken},
            "m": self.metrics.scalars()})
        return self.last

    def run(self, n=None):
        for _ in range(n or self.max_steps):
            if self.done:
                break
            self.step()
        return self.last

    # ---- views ----
    def meta(self):
        e = self.env
        return {"seed": self.seed, "agent": self.agent.name, "agent_label": self.agent.label, "threat": self.threat,
                "eve_seed": self.eve_seed, "stress": self.stress, "size": e.n, "battery_max": e.bmax, "nfree": self.belief.nfree,
                "max_steps": self.max_steps, "qs": [float(q) for q in self.belief.qs], "true_q": e.q,
                "obstacles": [list(o) for o in e.obstacles], "pads": [list(p) for p in e.pads],
                "decoys": [{"pos": list(p), "amp": a} for p, a in e.decoys]}

    def summary(self):
        e = self.env
        return {"done": self.done, "captured": e.captured, "dead": e.dead, "step": e.t, "metrics": self.metrics.summary(),
                "warnings": self.warnings, "mean_pred_score": float(np.mean(self.belief.pred_scores)) if self.belief.pred_scores else None}

    def result(self):
        e, m = self.env, self.metrics.summary()
        return {"seed": self.seed, "captured": e.captured, "dead": e.dead, "steps": e.t, "spent": e.spent, "scans": e.scans,
                "moves": e.moves, "blocked": e.blocked, "log_loss": m["log_loss"], "ece": m["ece"], "auc": m["roc_auc"],
                "brier": m["brier"], "info_gain": m["total_info_gain"], "warnings": self.warnings}

    def briefing(self):
        return {"meta": self.meta(), "summary": {k: v for k, v in self.summary().items() if k != "metrics"},
                "metrics": {k: v for k, v in self.metrics.summary().items() if k not in ("roc", "calibration", "last")},
                "q_posterior": dict(zip(map(str, self.belief.qs), map(float, self.belief.w))),
                "ledger": [{k: f[k] for k in ("step", "action", "mode", "battery", "entropy", "info_gain", "reason")} for f in self.frames]}
