"""400-particle sequential Monte Carlo over the same motion/sensor model: an independent
numerical cross-check on the grid filter (flags disagreement via KL)."""
from __future__ import annotations
import numpy as np
from .env import MOVES
from .bayes import VISIT_DISCOUNT


class ParticleFilter:
    def __init__(self, free, n_particles=400, seed=0):
        self.free, self.n, self.N = free, free.shape[0], n_particles
        self.rng = np.random.default_rng(seed)
        n = self.n
        self.table = np.full((n * n, 4), -1)
        self.deg = np.zeros(n * n, int)
        for r in range(n):
            for c in range(n):
                if free[r, c]:
                    nb = [(r + dr) * n + c + dc for dr, dc in MOVES.values()
                          if 0 <= r + dr < n and 0 <= c + dc < n and free[r + dr, c + dc]]
                    self.table[r * n + c, :len(nb)] = nb
                    self.deg[r * n + c] = len(nb)
        cells = np.flatnonzero(free.ravel())
        self.idx = self.rng.choice(cells, self.N)
        self.w = np.ones(self.N) / self.N

    def predict(self, q):
        move = (self.rng.random(self.N) < q) & (self.deg[self.idx] > 0)
        pick = (self.rng.random(self.N) * np.maximum(self.deg[self.idx], 1)).astype(int)
        self.idx = np.where(move, self.table[self.idx, pick], self.idx)

    def update(self, L, agent):
        if L is not None:
            self.w = self.w * np.maximum(L.ravel()[self.idx], 1e-12)
        self.w = np.where(self.idx == agent[0] * self.n + agent[1], self.w * VISIT_DISCOUNT, self.w)
        s = self.w.sum()
        self.w = self.w / s if s > 0 else np.ones(self.N) / self.N
        if 1.0 / np.sum(self.w ** 2) < self.N / 2:               # systematic resampling
            pos = (self.rng.random() + np.arange(self.N)) / self.N
            self.idx = self.idx[np.minimum(np.searchsorted(np.cumsum(self.w), pos), self.N - 1)]
            self.w = np.ones(self.N) / self.N

    def hist(self):
        return np.bincount(self.idx, weights=self.w, minlength=self.n ** 2).reshape(self.n, self.n)

    def counts(self):
        return np.bincount(self.idx, minlength=self.n ** 2).reshape(self.n, self.n)

    def kl_from(self, grid_p):
        g, f = grid_p + 1e-9, self.hist() + 1e-4
        g, f = g / g.sum(), f / f.sum()
        return float((g * np.log(g / f)).sum())
