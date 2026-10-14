"""Monte-Carlo expected information gain (nats) of a scan taken from cell x.
Uses common random numbers across candidate cells so comparisons are low-variance.
Decoys are ignored here (they are explained away by the likelihood), so this is a mild
over-estimate of the info available from a decoy-cluttered scan; documented in JOURNAL.md."""
from __future__ import annotations
import numpy as np
from .env import SIGMA_THETA, SIGMA_S, DECAY
from .bayes import EPS, VISIT_DISCOUNT


class EIG:
    def __init__(self, free, rng, K=48):
        self.free, self.n, self.rng, self.K = free, free.shape[0], rng, K
        self.rr, self.cc = np.mgrid[0:self.n, 0:self.n]
        self.cache = {}

    def _geo(self, x):
        g = self.cache.get(x)
        if g is None:
            dr, dc = self.rr - x[0], self.cc - x[1]
            d = np.hypot(dr, dc)
            g = self.cache[x] = (np.arctan2(dr, dc), np.exp(-d / DECAY), d == 0)
        return g

    def prepare(self, p):
        flat = p.ravel() / p.sum()
        idx = self.rng.choice(flat.size, self.K, p=flat)
        self.sr, self.sc = idx // self.n, idx % self.n
        self.nt, self.ns = self.rng.normal(0, SIGMA_THETA, self.K), self.rng.normal(0, SIGMA_S, self.K)
        self.p = p
        self.H = float(-(p[p > 0] * np.log(p[p > 0])).sum())

    def eig(self, x):
        T, S, here = self._geo(x)
        dr, dc = self.sr - x[0], self.sc - x[1]
        d = np.hypot(dr, dc)
        th, s = np.arctan2(dr, dc) + self.nt, np.exp(-d / DECAY) + self.ns
        dth = np.where(here[None], 0.0, np.angle(np.exp(1j * (th[:, None, None] - T[None]))))
        F = np.exp(-0.5 * (dth / SIGMA_THETA) ** 2) * np.exp(-0.5 * ((s[:, None, None] - S[None]) / SIGMA_S) ** 2)
        post = self.p[None] * (EPS + F) * self.free
        post[:, x[0], x[1]] *= VISIT_DISCOUNT
        post /= post.sum((1, 2), keepdims=True)
        Hp = -(post * np.log(np.maximum(post, 1e-300))).sum((1, 2)).mean()
        return max(0.0, self.H - float(Hp))
