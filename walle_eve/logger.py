"""Structured per-step trace: JSONL on disk, formatted lines on console."""
from __future__ import annotations
import json


class TraceLogger:
    def __init__(self, path: str | None = None, console: bool = False):
        self.records, self.path, self.console = [], path, console
        if path:
            open(path, "w").close()

    def log(self, **rec):
        self.records.append(rec)
        if self.path:
            with open(self.path, "a") as f:
                f.write(json.dumps({k: v for k, v in rec.items()}) + "\n")
        if self.console:
            print(self.format(rec))
        return rec

    @staticmethod
    def format(r):
        return (f"[{r['step']:03d}] {r['action']:<8} bat={r['battery']:>3} H={r['belief_entropy']:.3f} "
                f"obs={'scan' if r.get('observation') else '-'} | {r['reasoning_text']}")
