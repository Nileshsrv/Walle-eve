"""Ground-truth scoring of the agent's posterior (the agent never sees these)."""
from __future__ import annotations
import math
import numpy as np

BIN_EDGES = [0, .005, .01, .02, .05, .1, .2, .5, 1.0001]
ROC_EDGES = np.logspace(-7, 0.0001, 71)


class MetricsTracker:
    def __init__(self, free_mask):
        self.free, self.nfree = free_mask, int(free_mask.sum())
        self.rows = []
        k = len(BIN_EDGES) - 1
        self.cal_pred, self.cal_hit, self.cal_n = np.zeros(k), np.zeros(k), np.zeros(k)
        self.pos_scores, self.neg_hist = [], np.zeros(len(ROC_EDGES) - 1)
        self.det = dict(tp=0, fp=0, fn=0, tn=0)
        self.baseline_log_loss = math.log(self.nfree)          # a filter that knew nothing

    def update(self, post, truth, info_gain=0.0):
        flat, free = post.ravel(), self.free.ravel()
        ti = int(np.ravel_multi_index(truth, post.shape))
        t = float(flat[ti])
        others = flat[free & (np.arange(flat.size) != ti)]
        auc = float((np.sum(others < t) + 0.5 * np.sum(others == t)) / max(len(others), 1))   # rank ROC-AUC per step
        order = np.argsort(flat)[::-1]
        k = int(np.searchsorted(np.cumsum(flat[order]), 0.9) + 1)
        onehot = np.zeros(flat.size); onehot[ti] = 1
        brier = float(((flat - onehot)[free] ** 2).sum())
        row = {"auc": auc, "log_loss": float(-math.log(max(t, 1e-12))), "brier": brier, "brier_cell": brier / self.nfree,
               "top1": int(order[0] == ti), "top3": int(ti in order[:3]),
               "cred90": k, "cred90_cover": int(ti in order[:k]), "info_gain": float(info_gain)}
        self.rows.append(row)
        # calibration bins (every free cell is a probability claim)
        p, isT = flat[free], (np.arange(flat.size) == ti)[free]
        b = np.clip(np.digitize(p, BIN_EDGES) - 1, 0, len(self.cal_n) - 1)
        for i in range(len(self.cal_n)):
            m = b == i
            self.cal_n[i] += m.sum(); self.cal_pred[i] += p[m].sum(); self.cal_hit[i] += isT[m].sum()
        # pooled ROC
        self.pos_scores.append(t)
        self.neg_hist += np.histogram(np.clip(others, ROC_EDGES[0], ROC_EDGES[-1]), bins=ROC_EDGES)[0]
        # detection claim: "the 3x3 around my best cell holds >= half my belief"; truth within one cell of it
        pk = np.unravel_index(int(order[0]), post.shape)
        r0, c0 = pk
        mass3 = float(post[max(0, r0 - 1):r0 + 2, max(0, c0 - 1):c0 + 2].sum())
        claim, within = mass3 >= 0.5, max(abs(pk[0] - truth[0]), abs(pk[1] - truth[1])) <= 1
        self.det["tp" if claim and within else "fp" if claim else "fn" if within else "tn"] += 1
        return row

    def roc(self):
        pos = np.array(self.pos_scores)
        nh = self.neg_hist[::-1].cumsum() / max(self.neg_hist.sum(), 1)       # FPR at descending thresholds
        thr = ROC_EDGES[::-1][1:]
        tpr = [float(np.mean(pos >= th)) for th in thr]
        pts = [[0.0, 0.0]] + [[float(f), t] for f, t in zip(nh, tpr)] + [[1.0, 1.0]]
        auc = float(sum((pts[i + 1][0] - pts[i][0]) * (pts[i + 1][1] + pts[i][1]) / 2 for i in range(len(pts) - 1)))
        return pts[::2] + [pts[-1]], auc

    def calibration(self):
        out = []
        for i in range(len(self.cal_n)):
            n = self.cal_n[i]
            out.append({"lo": BIN_EDGES[i], "hi": min(BIN_EDGES[i + 1], 1.0), "n": int(n),
                        "pred": float(self.cal_pred[i] / n) if n else None, "obs": float(self.cal_hit[i] / n) if n else None})
        return out

    def summary(self):
        if not self.rows:
            return {}
        mean = lambda k: float(np.mean([r[k] for r in self.rows]))
        n = np.maximum(self.cal_n, 1)
        ece = float(np.sum(np.abs(self.cal_pred / n - self.cal_hit / n) * self.cal_n) / max(self.cal_n.sum(), 1))
        d = self.det
        prec = d["tp"] / (d["tp"] + d["fp"]) if d["tp"] + d["fp"] else None
        rec = d["tp"] / (d["tp"] + d["fn"]) if d["tp"] + d["fn"] else None
        roc, auc_pooled = self.roc()
        return {"steps": len(self.rows), "roc_auc": mean("auc"), "roc_auc_pooled": auc_pooled, "log_loss": mean("log_loss"),
                "baseline_log_loss": self.baseline_log_loss, "brier": mean("brier"), "brier_cell": mean("brier_cell"),
                "top1": mean("top1"), "top3": mean("top3"), "cred90_size": mean("cred90"), "cred90_coverage": mean("cred90_cover"),
                "ece": ece, "mean_info_gain": mean("info_gain"), "total_info_gain": float(sum(r["info_gain"] for r in self.rows)),
                "roc": roc, "calibration": self.calibration(),
                "detection": {**d, "precision": prec, "recall": rec}, "last": self.rows[-1]}

    def scalars(self):
        s = self.summary()
        return {k: s[k] for k in ("roc_auc", "log_loss", "brier", "brier_cell", "top1", "top3", "cred90_size", "ece")} if s else {}
