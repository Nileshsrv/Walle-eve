"""Record demo runs (used by the replay picker and the /guide page numbers)."""
import json, os
from walle_eve import Simulation
os.makedirs("data/runs", exist_ok=True)
for name, kw in {"seed7_v2_standard": dict(agent="v2"), "seed7_v1_standard": dict(agent="v1"),
                 "seed3_v2_pursuit": dict(seed=3, agent="v2", threat="pursuit")}.items():
    kw.setdefault("seed", 7)
    s = Simulation(**kw); s.run()
    json.dump({"meta": s.meta(), "frames": s.frames, "summary": s.summary()}, open(f"data/runs/{name}.json", "w"), separators=(",", ":"))
    print(name, "steps", s.env.t, "captured", s.env.captured, "spent", s.env.spent)
