import itertools, math, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from walle_eve import Simulation, make_config, GridEnv, Belief
from walle_eve.planner import astar, bfs_map
from walle_eve.eig import EIG


def test_mass_conserved_every_step():
    for seed in range(5):
        s = Simulation(seed, light=True)
        while not s.done:
            s.step()
            assert abs(s.belief.p.sum() - 1) < 1e-9 and (s.belief.p >= 0).all()


def test_astar_matches_bfs():
    rng = np.random.default_rng(0)
    for seed in range(8):
        env = GridEnv(make_config(seed))
        cells = [tuple(c) for c in np.argwhere(env.free_mask)]
        a = cells[int(rng.integers(len(cells)))]
        d = bfs_map(env.free_mask, [a])
        for _ in range(5):
            b = cells[int(rng.integers(len(cells)))]
            assert len(astar(env.free_mask, a, b)) - 1 == d[b]


def test_exact_association_matches_enumeration():
    env = GridEnv(make_config(3))
    bel = Belief(env.free_mask, env.decoys[:2], assoc="exact")      # 2 decoys -> 3 detections
    env.decoys = env.decoys[:2]
    obs = env.scan_obs()
    dets, ag = obs["detections"], env.walle
    G = [[bel._decoy_g(d, ag, pos, amp) for pos, amp in bel.decoys] for d in dets]
    tot = np.zeros(3)
    for j in range(3):
        others = [i for i in range(3) if i != j]
        for assign in itertools.permutations(others):                  # injective detection->decoy maps
            tot[j] += G[assign[0]][0] * G[assign[1]][1]
    tot = tot / tot.sum() if tot.sum() > 0 else np.full(3, 1 / 3)
    assert np.allclose(bel._weights_exact(dets, ag), tot, atol=1e-6)


def test_q_learning_orders_threat_levels():
    """q is only weakly identifiable from bearings, so assert direction and ordering, not exact recovery."""
    eq = {}
    for th in ("calm", "standard", "pursuit"):
        ws = []
        for seed in range(6):
            env = GridEnv(make_config(seed), threat=th)
            bel = Belief(env.free_mask, env.decoys, qs=(0.04, 0.08, 0.12, 0.16, 0.24), learn_q=True)
            for _ in range(80):
                env.t += 1; env._move_eve(); bel.predict()
                bel.update(bel.likelihood(env.scan_obs(), env.walle), env.walle)
            ws.append(bel.q_mean)
        eq[th] = float(np.mean(ws))
    assert eq["calm"] < eq["standard"] < eq["pursuit"]


def test_eig_nonnegative_and_positive_when_uncertain():
    env = GridEnv(make_config(4))
    bel = Belief(env.free_mask, env.decoys)
    e = EIG(env.free_mask, np.random.default_rng(0), K=32); e.prepare(bel.p)
    vals = [e.eig(tuple(c)) for c in np.argwhere(env.free_mask)[:30]]
    assert min(vals) >= 0 and max(vals) > 0.3


def test_deterministic():
    a = Simulation(11, light=True); a.run(); b = Simulation(11, light=True); b.run()
    assert a.result() == b.result()


def test_agents_never_hold_ground_truth():
    s = Simulation(5, light=True)
    for obj in (s.planner, s.belief):
        for v in vars(obj).values():
            assert v is not s.env
    assert not any(isinstance(v, tuple) and v == s.env.eve_truth and k == "eve" for k, v in vars(s.planner).items())


def test_low_battery_forces_return():
    for agent in ("v1", "v2"):
        s = Simulation(7, agent=agent, light=True)
        for _ in range(3):
            s.step()
        s.env.battery = 4
        if s.env.walle in s.env.pads:
            continue
        d = s.planner.decide(s.belief, s.env.walle, 4, {"clues": []})
        assert d.mode in ("return", "recharge")


def test_no_battery_deaths_under_stress():
    for seed in range(300, 316):
        s = Simulation(seed, agent="v2", threat="pursuit", stress={"sigma_mult": 1.5, "dropout": 0.1}, max_steps=200, light=True)
        s.run()
        assert not s.env.dead


def test_clues_and_randomised_eve():
    cfg = make_config(7)
    e1, e2 = GridEnv(cfg, eve_seed=1), GridEnv(cfg, eve_seed=2)
    assert e1.free_mask.sum() == e2.free_mask.sum()
    assert e1.eve_truth != tuple(cfg["eve"]) or e2.eve_truth != tuple(cfg["eve"])
    env = GridEnv(cfg); env.clues = {(env.walle[0], env.walle[1] + 1)} if env.is_free(env.walle[0], env.walle[1] + 1) else env.clues
    if env.clues:
        info = env.step("right")
        assert info["clue"] is not None and not env.clues
