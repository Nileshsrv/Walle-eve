"""Grid world: obstacles, pads, decoys, clue tokens, moving EVE, noisy bearing/strength sensor.

Determinism: EVE's motion draws and the sensor noise are keyed on (seed, step) so that different
agents facing the same seed see the same EVE trajectory (non-evasive modes) and the same noise
at the same step. This is what makes paired benchmarking meaningful.
"""
from __future__ import annotations
import json, math, random
from collections import deque
import numpy as np

MOVES = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
MOVE_COST, SCAN_COST, RECHARGE_GAIN = 1, 3, 20
SIGMA_THETA, SIGMA_S, DECAY = 0.25, 0.04, 5.0   # nominal bearing noise (rad), strength noise, exp(-d/5)
CLUE_SIGMA = 1.5                                 # clue token localises EVE to ~1.5 cells

THREATS = {
    "calm":     {"q": 0.05, "sigma_theta": 0.20, "evade": 0.0},
    "standard": {"q": 0.12, "sigma_theta": 0.25, "evade": 0.0},
    # pursuit: faster, and when she moves within 4 cells of WALL-E she steps away half the time
    "pursuit":  {"q": 0.20, "sigma_theta": 0.25, "evade": 0.5},
}


def signal(d: float, amp: float = 1.0) -> float:
    return amp * math.exp(-d / DECAY)


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _reachable(size, obstacles, start):
    seen, dq = {start}, deque([start])
    while dq:
        r, c = dq.popleft()
        for dr, dc in MOVES.values():
            n = (r + dr, c + dc)
            if 0 <= n[0] < size and 0 <= n[1] < size and n not in obstacles and n not in seen:
                seen.add(n); dq.append(n)
    return seen


def make_config(seed: int, size: int = 14) -> dict:
    """Procedurally generate a connected map for a seed."""
    rng = random.Random(seed)
    cells = [(r, c) for r in range(size) for c in range(size)]
    obstacles = set(rng.sample(cells, int(size * size * 0.13)))
    free = [c for c in cells if c not in obstacles]
    pads = rng.sample(free, 3)
    start = pads[0]
    obstacles -= set(pads)
    reach = _reachable(size, obstacles, start)
    obstacles |= {c for c in cells if c not in reach}          # fill unreachable pockets
    pads = [p for p in pads if p in reach]
    free = sorted(reach - set(pads))
    decoys = rng.sample(free, 3)
    far = [c for c in free if abs(c[0] - start[0]) + abs(c[1] - start[1]) > size // 2 and c not in decoys]
    eve = rng.choice(far or free)
    clue_pool = [c for c in free if c not in decoys and c != eve]
    clues = rng.sample(clue_pool, 2)
    return {"seed": seed, "size": size, "q": 0.12, "battery_max": 100,
            "obstacles": sorted(map(list, obstacles)), "pads": [list(p) for p in pads],
            "decoys": [{"pos": list(d), "amp": round(rng.uniform(1.8, 2.6), 2)} for d in decoys],
            "clues": [list(c) for c in clues],
            "walle": list(start), "eve": list(eve)}


class GridEnv:
    def __init__(self, cfg: dict, threat: str = "standard", sigma_mult: float = 1.0,
                 dropout: float = 0.0, eve_seed: int | None = None):
        self.cfg, self.threat = cfg, threat
        th = THREATS[threat]
        self.n = cfg["size"]
        self.q, self.evade = th["q"], th["evade"]
        self.sig_theta, self.sig_s = th["sigma_theta"] * sigma_mult, SIGMA_S * sigma_mult
        self.dropout = dropout
        self.bmax = cfg.get("battery_max", 100)
        self.seed = cfg.get("seed", 0)
        self.eve_rng = random.Random((eve_seed if eve_seed is not None else self.seed) * 31 + 5)
        self.obstacles = {tuple(o) for o in cfg["obstacles"]}
        self.pads = [tuple(p) for p in cfg["pads"]]
        self.decoys = [(tuple(d["pos"]), d["amp"]) for d in cfg["decoys"]]
        self.clues = {tuple(c) for c in cfg.get("clues", [])}
        self.free_mask = np.ones((self.n, self.n), bool)
        for r, c in self.obstacles:
            self.free_mask[r, c] = False
        self.walle = tuple(cfg["walle"])
        self._eve = tuple(cfg["eve"])        # ground truth: NEVER exposed to the agent
        if eve_seed is not None:             # randomised EVE start, same map
            rr = random.Random(eve_seed)
            dec = {d for d, _ in self.decoys}
            cand = [(r, c) for r in range(self.n) for c in range(self.n)
                    if self.free_mask[r, c] and (r, c) not in dec and (r, c) not in self.pads
                    and abs(r - self.walle[0]) + abs(c - self.walle[1]) > self.n // 2]
            if cand:
                self._eve = rr.choice(cand)
        self.battery = self.bmax
        self.t = 0
        self.captured = self.dead = False
        self.moves = self.scans = self.blocked = self.charges = self.clues_taken = 0
        self.move_spent = self.scan_spent = self.idle_spent = 0

    # ---- geometry ----
    def is_free(self, r, c):
        return 0 <= r < self.n and 0 <= c < self.n and bool(self.free_mask[r, c])

    def neighbors(self, r, c):
        return [(r + dr, c + dc) for dr, dc in MOVES.values() if self.is_free(r + dr, c + dc)]

    @property
    def eve_truth(self):  # metrics / UI only
        return self._eve

    @property
    def spent(self):
        return self.move_spent + self.scan_spent + self.idle_spent

    # ---- sensors ----
    def scan_obs(self):
        """Unlabeled detections: one for EVE (amp 1) and one per decoy (amp>1), shuffled.
        Noise is keyed on (seed, t) so every agent sees the same noise at the same step."""
        if self.dropout and random.Random(self.seed * 17 + self.t).random() < self.dropout:
            return {"type": "scan", "detections": []}
        nz = np.random.default_rng([self.seed, self.t, 17])
        dets = []
        for pos, amp in [(self._eve, 1.0)] + self.decoys:
            dr, dc = pos[0] - self.walle[0], pos[1] - self.walle[1]
            d = math.hypot(dr, dc)
            theta = math.atan2(dr, dc) + nz.normal(0, self.sig_theta)
            s = max(0.0, signal(d, amp) + nz.normal(0, self.sig_s))
            dets.append({"theta": (theta + math.pi) % (2 * math.pi) - math.pi, "strength": float(s)})
        random.Random(self.seed * 13 + self.t).shuffle(dets)
        return {"type": "scan", "detections": dets}

    def clue_obs(self):
        nz = np.random.default_rng([self.seed, self.t, 23])
        return {"type": "clue", "pos": [float(self._eve[0] + nz.normal(0, CLUE_SIGMA)),
                                        float(self._eve[1] + nz.normal(0, CLUE_SIGMA))]}

    # ---- dynamics ----
    def _move_eve(self):
        u, v, w = self.eve_rng.random(), self.eve_rng.random(), self.eve_rng.random()  # fixed draws/step
        if u >= self.q:
            return
        nb = self.neighbors(*self._eve)
        if not nb:
            return
        dist = math.hypot(self._eve[0] - self.walle[0], self._eve[1] - self.walle[1])
        if self.evade and dist <= 4 and w < self.evade:
            best = max(math.hypot(a - self.walle[0], b - self.walle[1]) for a, b in nb)
            nb = [x for x in nb if math.hypot(x[0] - self.walle[0], x[1] - self.walle[1]) >= best - 1e-9]
        self._eve = nb[min(int(v * len(nb)), len(nb) - 1)]

    def step(self, action: str) -> dict:
        """EVE moves first (time advances), then the agent's action resolves."""
        self._move_eve()
        info = {"action": action, "bumped": False, "obs": None, "clue": None, "cost": 0}
        if action in MOVES:
            dr, dc = MOVES[action]
            nr, nc = self.walle[0] + dr, self.walle[1] + dc
            if self.is_free(nr, nc):
                self.walle = (nr, nc)
            else:
                info["bumped"] = True; self.blocked += 1       # bumping still bills 1 unit
            info["cost"] = MOVE_COST; self.moves += 1; self.move_spent += MOVE_COST
        elif action == "scan":
            info["cost"] = SCAN_COST; self.scans += 1; self.scan_spent += SCAN_COST
            info["obs"] = self.scan_obs()
        elif action == "recharge":
            if self.walle in self.pads:
                self.battery = min(self.bmax, self.battery + RECHARGE_GAIN); self.charges += 1
            else:
                info["cost"] = 1; self.idle_spent += 1          # wasted rest off-pad
        if self.walle in self.clues:                            # free clue pickup
            self.clues.discard(self.walle); self.clues_taken += 1
            info["clue"] = self.clue_obs()
        self.battery -= info["cost"]
        self.t += 1
        self.captured = self.walle == self._eve
        self.dead = self.battery <= 0 and not self.captured
        info.update(captured=self.captured, dead=self.dead)
        return info
