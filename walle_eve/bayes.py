"""Bayesian belief over EVE's location.

Features beyond the textbook filter:
  * online motion-rate learning: K beliefs at different q, re-weighted by predictive evidence
  * exact decoy data association (marginalise over which detection belongs to which source)
  * clue-token likelihood, surprise-triggered likelihood tempering (self-calibration)
"""
from __future__ import annotations
import itertools, math
import numpy as np
from .env import SIGMA_THETA, SIGMA_S, DECAY, CLUE_SIGMA

VISIT_DISCOUNT = 0.06   # p(EVE here) *= 0.06 for the cell WALL-E occupies
EPS = 1e-3              # outlier floor so one bad reading cannot zero the belief
W_FLOOR = 0.01          # minimum weight any motion-rate hypothesis keeps
SURPRISE_EV = 4e-3      # predictive evidence below this = the reading was a surprise
_D4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _shift(a, dr, dc):
    """Shift the last two axes by (dr, dc), zero-filling."""
    out = np.zeros_like(a)
    n, m = a.shape[-2:]
    rs, rd = (slice(0, n - dr), slice(dr, n)) if dr >= 0 else (slice(-dr, n), slice(0, n + dr))
    cs, cd = (slice(0, m - dc), slice(dc, m)) if dc >= 0 else (slice(-dc, m), slice(0, m + dc))
    out[..., rd, cd] = a[..., rs, cs]
    return out


class Belief:
    def __init__(self, free_mask, decoys, qs=(0.12,), learn_q=False, assoc="exact", self_cal=False):
        self.free, self.decoys = free_mask, decoys
        self.qs = np.array(qs, float)
        self.K = len(self.qs)
        self.learn_q = learn_q and self.K > 1
        self.assoc, self.self_cal = assoc, self_cal
        n = self.n = free_mask.shape[0]
        self.rr, self.cc = np.mgrid[0:n, 0:n]
        deg = sum(_shift(free_mask.astype(float), dr, dc) for dr, dc in _D4) * free_mask
        self.iso = free_mask & (deg == 0)            # cells with no free neighbours keep their mass
        self.deg = np.maximum(deg, 1.0)
        self.nfree = int(free_mask.sum())
        self.B = np.repeat((free_mask / self.nfree)[None], self.K, 0)   # one belief per motion rate
        self.w = np.ones(self.K) / self.K
        self.perms = list(itertools.permutations(range(len(decoys))))
        self.evidence, self.surprised, self.temper_next, self.pred_scores = 1.0, False, False, []

    @property
    def p(self):
        return np.tensordot(self.w, self.B, axes=1)

    @property
    def q_mean(self):
        return float(self.w @ self.qs)

    # ---- Predict:  p_t = (1-q) p + q * sum_{nbrs} p(nbr)/deg(nbr)   (mass-conserving, per q) ----
    def predict(self):
        flow = self.B / self.deg
        inflow = sum(_shift(flow, dr, dc) for dr, dc in _D4) * self.free
        q = self.qs[:, None, None]
        self.B = self._norm((1 - q) * self.B + q * inflow + q * self.B * self.iso)
        return self.p

    # ---- Likelihood ----
    def _geo(self, agent):
        dr, dc = self.rr - agent[0], self.cc - agent[1]
        dist = np.hypot(dr, dc)
        return np.arctan2(dr, dc), np.exp(-dist / DECAY), dist == 0

    def _F(self, det, geo):
        theta_c, s_c, here = geo
        dth = np.angle(np.exp(1j * (det["theta"] - theta_c)))
        ang = np.where(here, 1.0, np.exp(-0.5 * (dth / SIGMA_THETA) ** 2))
        return ang * np.exp(-0.5 * ((det["strength"] - s_c) / SIGMA_S) ** 2)

    def _decoy_g(self, det, agent, pos, amp):
        d = math.hypot(pos[0] - agent[0], pos[1] - agent[1])
        dth = (det["theta"] - math.atan2(pos[0] - agent[0], pos[1] - agent[1]) + math.pi) % (2 * math.pi) - math.pi
        return math.exp(-0.5 * (dth / (1.5 * SIGMA_THETA)) ** 2) * \
            math.exp(-0.5 * ((det["strength"] - amp * math.exp(-d / DECAY)) / (1.5 * SIGMA_S)) ** 2)

    def _weights_heuristic(self, dets, agent):
        return np.array([1 - max([self._decoy_g(d, agent, pos, amp) for pos, amp in self.decoys] or [0.0])
                         for d in dets])

    def _weights_exact(self, dets, agent):
        """w_j = P(detection j is EVE | all detections), marginalising over decoy assignments:
        W_j = permanent of G with row j removed, G[i,k] = fit of detection i to known decoy k."""
        n, m = len(dets), len(self.decoys)
        if n != m + 1:
            return self._weights_heuristic(dets, agent)
        G = np.array([[max(self._decoy_g(d, agent, pos, amp), 1e-12) for pos, amp in self.decoys]
                      for d in dets]).reshape(n, m)
        W = np.zeros(n)
        for j in range(n):
            rows = [i for i in range(n) if i != j]
            W[j] = sum(np.prod([G[rows[a], pm[a]] for a in range(m)]) if m else 1.0 for pm in self.perms) if m else 1.0
        s = W.sum()
        return W / s if s > 1e-300 else np.full(n, 1.0 / n)

    def likelihood(self, obs, agent):
        """L(obs | EVE in cell) = eps + sum_j w_j * N(bearing_j) * N(strength_j).  None if no detections."""
        dets = obs["detections"]
        if not dets:
            return None
        geo = self._geo(agent)
        w = self._weights_exact(dets, agent) if self.assoc == "exact" else self._weights_heuristic(dets, agent)
        L = np.full(self.p.shape, EPS)
        for wj, det in zip(w, dets):
            L += wj * self._F(det, geo)
        return L * self.free

    def clue_likelihood(self, clue):
        d2 = (self.rr - clue["pos"][0]) ** 2 + (self.cc - clue["pos"][1]) ** 2
        return (EPS + np.exp(-0.5 * d2 / CLUE_SIGMA ** 2)) * self.free

    # ---- Update: weight motion rates, multiply, discount current cell, renormalise ----
    def update(self, L, agent):
        pri = self.B
        self.surprised = False
        if L is not None:
            ev = (pri * L).sum((1, 2))
            self.evidence = mix = float(self.w @ ev)
            self.pred_scores.append(-math.log(max(mix, 1e-12)))
            Lp = L
            if self.self_cal and (mix < SURPRISE_EV or self.temper_next):
                Lp, self.surprised, self.temper_next = L ** 0.5, True, False      # temper: don't over-commit
                ev = (pri * Lp).sum((1, 2))
            if self.learn_q:
                w = self.w * np.maximum(ev, 1e-12)
                w = np.maximum(w / w.sum(), W_FLOOR)
                self.w = w / w.sum()
            post = pri * Lp
        else:
            post = pri.copy()
        post[:, agent[0], agent[1]] *= VISIT_DISCOUNT
        self.B = self._norm(post)
        return self.p

    def _norm(self, a):
        a = a * self.free
        s = a.sum((-2, -1), keepdims=True)
        return np.where(s > 0, a / np.where(s > 0, s, 1.0), self.free / self.nfree)

    # ---- summaries ----
    @staticmethod
    def entropy_of(p):
        q = p[p > 0]
        return float(-(q * np.log(q)).sum())

    def entropy(self):
        return self.entropy_of(self.p)

    @property
    def max_entropy(self):
        return math.log(self.nfree)

    def smoothed(self):
        """3x3 neighbourhood mass on free cells."""
        p = self.p
        s = p.copy()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr or dc:
                    s += _shift(p, dr, dc)
        return s * self.free

    def credible_cells(self, mass=0.9):
        flat = self.p.ravel()
        order = np.argsort(flat)[::-1]
        k = int(np.searchsorted(np.cumsum(flat[order]), mass) + 1)
        return [[int(i // self.n), int(i % self.n)] for i in order[:k]]
