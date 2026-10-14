"""Flask server: one in-memory mission, JSON API, dashboard (/) and guide (/guide)."""
import glob, json, os
from flask import Flask, jsonify, render_template, request, Response
from walle_eve import Simulation, agent_list

app = Flask(__name__)
RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "runs")
STRESS = {"none": {}, "hard": {"sigma_mult": 1.5, "dropout": 0.10}}
G = {"sim": None, "sent": 0}


def new_sim(body):
    stress = body.get("stress", "none")
    G["sim"] = Simulation(int(body.get("seed", 7)), agent=body.get("agent", "v2"), threat=body.get("threat", "standard"),
                          eve_seed=(int(body["eve_seed"]) if body.get("eve_seed") not in (None, "") else None),
                          stress=STRESS.get(stress, {}))
    G["body"] = body
    G["sent"] = 0


def payload(all_frames=False):
    s = G["sim"]
    frames = s.frames if all_frames else s.frames[G["sent"]:]
    G["sent"] = len(s.frames)
    return jsonify({"meta": s.meta(), "frames": frames, "summary": s.summary(), "start": len(s.frames) - len(frames)})


@app.get("/")
def landing():
    return render_template("landing.html")


@app.get("/mission")
def mission():
    return render_template("index.html")


@app.get("/guide")
def guide():
    return render_template("guide.html")


@app.get("/api/agents")
def agents():
    return jsonify(agent_list())


@app.get("/api/state")
def state():
    if G["sim"] is None:
        new_sim({})
    return payload(all_frames=True)


@app.post("/api/reset")
def reset():
    new_sim(request.get_json(silent=True) or {})
    return payload(all_frames=True)


@app.post("/api/step")
def step():
    if G["sim"] is None:
        new_sim({})
    n = max(1, min(int((request.get_json(silent=True) or {}).get("n", 1)), 400))
    for _ in range(n):
        G["sim"].step()
    return payload()


@app.get("/api/trace")
def trace():
    return Response("\n".join(json.dumps(r) for r in G["sim"].logger.records), mimetype="application/x-ndjson")


@app.get("/api/briefing")
def briefing():
    b = json.dumps(G["sim"].briefing(), indent=1)
    return Response(b, mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename=briefing_seed{G['sim'].seed}_{G['sim'].agent.name}.json"})


@app.get("/api/leaderboard")
def leaderboard():
    p = os.path.join(os.path.dirname(RUNS), "..", "results", "LEADERBOARD.md")
    return Response(open(p).read() if os.path.exists(p) else "", mimetype="text/markdown")


@app.get("/api/runs")
def runs():
    return jsonify(sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(RUNS, "*.json"))))


@app.get("/api/runs/<name>")
def run(name):
    path = os.path.join(RUNS, os.path.basename(name) + ".json")
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    return Response(open(path).read(), mimetype="application/json")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
