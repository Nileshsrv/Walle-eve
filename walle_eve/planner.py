"""Planners.
  Planner      v1: reserve rule + entropy-threshold scan + A* to smoothed peak (optional two-hypothesis rule)
  NaivePlanner baseline: trusts the loudest detection, never reasons about decoys
  PlannerV2    EIG-per-battery scan placement, destination-aware reserve, selectable value rule
"""
from __future__ import annotations
import heapq
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from .env import MOVES, SCAN_COST
from .eig import EIG

SCAN_ENTROPY_FRAC, SCAN_CONF = 0.45, 0.40
MIN_MOVES_BETWEEN_SCANS, RECHARGE_TARGET = 2, 0.9
INF = 10 ** 6


@dataclass
class Decision:
    action: str
    reason: str
    mode: str                      # recharge | return | scan | survey | clue | pursue
    path: list = field(default_factory=list)
    reserve: int = 0
    target: tuple | None = None
    options: list = field(default_factory=list)


def astar(free, start, goal):
    """4-connected A* with Manhattan heuristic. Returns list of cells incl. start, or None."""
    if start == goal:
        return [start]
    h = lambda c: abs(c[0] - goal[0]) + abs(c[1] - goal[1])
    pq, g, came, n = [(h(start), 0, start)], {start: 0}, {}, free.shape[0]
    while pq:
        _, gc, cur = heapq.heappop(pq)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]; path.append(cur)
            return path[::-1]
        if gc > g.get(cur, INF):
            continue
        for dr, dc in MOVES.values():
            nx = (cur[0] + dr, cur[1] + dc)
            if 0 <= nx[0] < n and 0 <= nx[1] < n and free[nx] and gc + 1 < g.get(nx, INF):
                g[nx] = gc + 1; came[nx] = cur
                heapq.heappush(pq, (gc + 1 + h(nx), gc + 1, nx))
    return None


def bfs_map(free, sources):
    n = free.shape[0]
    d = np.full((n, n), INF)
    dq = deque()
    for s in sources:
        d[s] = 0; dq.append(s)
    while dq:
        r, c = dq.popleft()
        for dr, dc in MOVES.values():
            a, b = r + dr, c + dc
            if 0 <= a < n and 0 <= b < n and free[a, b] and d[a, b] == INF:
                d[a, b] = d[r, c] + 1; dq.append((a, b))
    return d


def step_action(a, b):
    d = (b[0] - a[0], b[1] - a[1])
    return next(k for k, v in MOVES.items() if v == d)


class Planner:
    """v1 planner (also the base class)."""
    def __init__(self, free_mask, pads, battery_max=100, scan_rule="entropy", seed=0):
        self.free, self.pads, self.bmax, self.scan_rule = free_mask, list(pads), battery_max, scan_rule
        self.returning = False
        self.moves_since_scan = MIN_MOVES_BETWEEN_SCANS

    def nearest_pad_path(self, pos):
        best = None
        for p in self.pads:
            path = astar(self.free, pos, p)
            if path and (best is None or len(path) < len(best)):
                best = path
        return best or [pos]

    # ---- shared battery logic ----
    def _power(self, pos, battery, pad_path, reserve):
        pad_len, on_pad = len(pad_path) - 1, pos in self.pads
        if on_pad and (self.returning or battery <= reserve) and battery < self.bmax * RECHARGE_TARGET:
            self.returning = True
            return Decision("recharge", f"On pad, battery {battery}/{self.bmax}: charging to {int(self.bmax * RECHARGE_TARGET)}.",
                            "recharge", reserve=reserve)
        if on_pad and self.returning:
            self.returning = False
        if battery <= reserve and not on_pad:
            self.returning = True
            return Decision(step_action(pad_path[0], pad_path[1]),
                            f"Battery {battery} <= reserve {reserve} (pad {pad_len} + 2x scan {SCAN_COST}). Forced return.",
                            "return", pad_path, reserve, pad_path[-1])
        if self.returning and not on_pad:
            return Decision(step_action(pad_path[0], pad_path[1]), f"Returning to pad ({pad_len} steps), battery {battery}.",
                            "return", pad_path, reserve, pad_path[-1])
        return None

    # ---- hooks ----
    def _need_scan(self, belief, pos, ctx):
        H, Hmax, sm = belief.entropy(), belief.max_entropy, belief.smoothed()
        conf = float(sm.max())
        if self.scan_rule == "two_hyp":
            pk = np.unravel_index(np.argmax(sm), sm.shape)
            mask = (np.abs(belief.rr - pk[0]) > 3) | (np.abs(belief.cc - pk[1]) > 3)
            second = float((sm * mask).max())
            if second >= 0.5 * conf or H > 0.7 * Hmax:
                return True, f"Two competing hypotheses (peak {conf:.2f}, rival {second:.2f}); scanning to separate them."
            return False, ""
        if H > SCAN_ENTROPY_FRAC * Hmax or conf < SCAN_CONF:
            return True, f"H={H:.2f}/{Hmax:.2f} nats, best 3x3 mass {conf:.2f} < {SCAN_CONF}: diffuse belief, scanning."
        return False, ""

    def _target(self, belief, pos, ctx):
        sm = belief.smoothed()
        tgt = tuple(int(i) for i in np.unravel_index(np.argmax(sm), sm.shape))
        return tgt, f"posterior peak {tgt} (mass {float(sm.max()):.2f})"

    def decide(self, belief, pos, battery, ctx=None) -> Decision:
        ctx = ctx or {}
        pad_path = self.nearest_pad_path(pos)
        pad_len = len(pad_path) - 1
        reserve = pad_len + 2 * SCAN_COST                        # Reserve = Path(pad) + 2 * Cost(scan)
        d = self._power(pos, battery, pad_path, reserve)
        if d:
            return d
        afford = battery - SCAN_COST > pad_len + 2 * SCAN_COST
        need, why = self._need_scan(belief, pos, ctx)
        if afford and self.moves_since_scan >= MIN_MOVES_BETWEEN_SCANS and need:
            self.moves_since_scan = 0
            return Decision("scan", why, "scan", reserve=reserve)
        tgt, tw = self._target(belief, pos, ctx)
        path = astar(self.free, pos, tgt)
        if path and len(path) > 1:
            self.moves_since_scan += 1
            return Decision(step_action(path[0], path[1]), f"Pursuing {tw}, {len(path) - 1} steps via A*.", "pursue", path, reserve, tgt)
        if afford:
            self.moves_since_scan = 0
            return Decision("scan", f"At {tw} but EVE unseen: re-scan to refine.", "scan", reserve=reserve)
        return Decision("recharge", "At peak with low battery; waiting.", "recharge", reserve=reserve)


class NaivePlanner(Planner):
    """Baseline: head for wherever the loudest detection points; rescan every few moves."""
    def _need_scan(self, belief, pos, ctx):
        return (ctx.get("last_scan") is None or self.moves_since_scan >= 4), "Naive: refresh the loudest reading."

    def _target(self, belief, pos, ctx):
        scan, sp = ctx.get("last_scan"), ctx.get("last_scan_pos") or pos
        if not scan or not scan["detections"]:
            return pos, "no reading"
        top = max(scan["detections"], key=lambda d: d["strength"])
        dist = -5.0 * np.log(max(top["strength"], 1e-3))
        r = int(round(np.clip(sp[0] + dist * np.sin(top["theta"]), 0, self.free.shape[0] - 1)))
        c = int(round(np.clip(sp[1] + dist * np.cos(top["theta"]), 0, self.free.shape[1] - 1)))
        cells = np.argwhere(self.free)
        j = int(np.argmin(((cells - [r, c]) ** 2).sum(1)))
        t = (int(cells[j][0]), int(cells[j][1]))
        return t, f"loudest signal -> {t}"


class PlannerV2(Planner):
    def __init__(self, free_mask, pads, battery_max=100, use_eig=True, reserve2=True, value="peak",
                 eig_tau=0.4, radius=7, seed=0):
        super().__init__(free_mask, pads, battery_max)
        self.use_eig, self.reserve2, self.value, self.eig_tau, self.radius = use_eig, reserve2, value, eig_tau, radius
        self.rng = np.random.default_rng(seed)
        self.eig = EIG(free_mask, self.rng, K=32)
        self.pad_d = bfs_map(free_mask, self.pads)
        self.goal = None
        self.commit, self.commit_left = None, 0
        self._D = None

    def _all_pairs(self):
        if self._D is None:
            self.cells = [tuple(map(int, c)) for c in np.argwhere(self.free)]
            rows = []
            for c in self.cells:
                dm = bfs_map(self.free, [c])
                rows.append([dm[x] for x in self.cells])
            self._D = np.array(rows, float)
        return self._D

    def _value_target(self, belief, pos, d_pos):
        p = belief.p
        if self.value == "thompson":
            if self.commit and self.commit != pos and self.commit_left > 0:
                self.commit_left -= 1
                return self.commit, f"Thompson target {self.commit} (committed)"
            flat = p.ravel() / p.sum()
            i = int(self.rng.choice(flat.size, p=flat))
            self.commit, self.commit_left = (i // p.shape[1], i % p.shape[1]), 5
            return self.commit, f"Thompson sample {self.commit}"
        if self.value == "qmdp":
            D = self._all_pairs()
            pv = np.array([p[c] for c in self.cells])
            e = D @ pv
            j = int(np.argmin(e))
            return self.cells[j], f"min expected distance {e[j]:.1f} at {self.cells[j]}"
        return self._target(belief, pos, {})

    def decide(self, belief, pos, battery, ctx=None) -> Decision:
        ctx = ctx or {}
        d_pos = bfs_map(self.free, [pos])
        pad_path = self.nearest_pad_path(pos)
        pad_len = len(pad_path) - 1
        reserve = pad_len + 2 * SCAN_COST
        dec = self._power(pos, battery, pad_path, reserve)
        if dec:
            return dec
        H, p = belief.entropy(), belief.p
        cands = []
        if self.use_eig:
            self.eig.prepare(p)
            cells = [(int(r), int(c)) for r, c in np.argwhere(self.free & (d_pos <= self.radius))
                     if (r + c) % 2 == 0 or (r, c) == pos]
            for x in cells:
                d = int(d_pos[x])
                ok = (battery - d - SCAN_COST >= self.pad_d[x] + 2 * SCAN_COST) if self.reserve2 \
                    else (battery - SCAN_COST > pad_len + 2 * SCAN_COST)
                if ok:
                    e = self.eig.eig(x)
                    cands.append((e / (d + SCAN_COST), "scan", x, e, d))
            for cl in ctx.get("clues", []):
                cl = tuple(cl); d = int(d_pos[cl])
                if d < INF and battery - d >= self.pad_d[cl] + 2 * SCAN_COST:
                    g = max(0.0, H - 3.65)                         # entropy of a 1.5-cell Gaussian ~ 3.65 nats
                    cands.append((g / (d + 0.5), "clue", cl, g, d))
        cands.sort(key=lambda t: -t[0])
        opts = [f"{k}@{x}:{s:.2f}n/u" for s, k, x, _, _ in cands[:3]]
        best = cands[0] if cands else None
        if best and self.goal:                                     # hysteresis: avoid flip-flopping goals
            for c in cands:
                if (c[1], c[2]) == self.goal and c[0] >= 0.7 * best[0]:
                    best = c; break
        if best and best[0] >= self.eig_tau:
            s, kind, x, e, d = best
            self.goal = (kind, x)
            if kind == "scan" and x == pos:
                self.goal = None
                return Decision("scan", f"Best scan here: EIG {e:.2f} nats per {d + SCAN_COST} units = {s:.2f}/unit "
                                f"(H={H:.2f}, q^={belief.q_mean:.2f}).", "scan", reserve=reserve, options=opts)
            path = astar(self.free, pos, x)
            if path and len(path) > 1:
                what = f"scan spot {x} (EIG {e:.2f}, {s:.2f}/unit)" if kind == "scan" else f"clue token {x} (free reading)"
                return Decision(step_action(path[0], path[1]), f"Heading to {what}, {d} steps.",
                                "survey" if kind == "scan" else "clue", path, reserve, x, opts)
        self.goal = None
        tgt, tw = self._value_target(belief, pos, d_pos)
        path = astar(self.free, pos, tgt)
        if self.reserve2 and d_pos[tgt] < INF and battery - d_pos[tgt] < self.pad_d[tgt] + 2 * SCAN_COST and pos not in self.pads:
            self.returning = True
            return Decision(step_action(pad_path[0], pad_path[1]),
                            f"Target {tgt} is {int(d_pos[tgt])} away but home from there is {int(self.pad_d[tgt])}; battery {battery} can't cover both. Recharging first.",
                            "return", pad_path, reserve, pad_path[-1], opts)
        if path and len(path) > 1:
            return Decision(step_action(path[0], path[1]), f"Pursuing {tw}, {len(path) - 1} steps via A*.", "pursue", path, reserve, tgt, opts)
        if battery - SCAN_COST > pad_len + 2 * SCAN_COST:
            return Decision("scan", f"At {tw} but EVE unseen: probing.", "scan", reserve=reserve, options=opts)
        return Decision("recharge", "At target with low battery; waiting.", "recharge", reserve=reserve, options=opts)
