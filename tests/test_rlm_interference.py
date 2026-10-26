# SPDX-License-Identifier: MIT
"""The optional dynamic interference on link monitoring (protocol.rlm_interference: dynamic): defaults untouched,
the full-load and zero-activity limits, the background burst process, single = batch, seeds and validation."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError, ProtocolConfig
from handoverlab.engine import core
from handoverlab.engine.procedures import CONNECTED
from handoverlab.seeds import streams
from handoverlab.traffic import CellBursts

BASE = {"mobility.users": 12, "run.duration_s": 15.0, "run.warmup_s": 2.0, "mobility.profile": "veh30"}
DYN = {"protocol.rlm_interference": "dynamic"}
CSI = dict(DYN, **{"protocol.rlm_rs_type": "csi-rs"})
FULL = {"traffic.normal_load": [1.0, 1.0], "traffic.hotspot_load": [1.0, 1.0]}
IDLE = {"traffic.normal_load": [0.0, 0.0], "traffic.hotspot_load": [0.0, 0.0], "traffic.rate_scale": 0.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 2.0, "ttt_s": 0.08},
         {"rule": "a3", "name": "A3b", "off_db": 4.0, "ttt_s": 0.32}]


def _sc(*ovs):
    d = dict(BASE)
    for o in ovs:
        d.update(o)
    return hl.builtin_scenario("smoke").with_overrides(d)


def _run(sc, seed=3, batch=True, rules=RULES):
    return hl.run_world(hl.build_world(sc, seed), rules, batch=batch)


def _key(res):
    return [(r.fingerprint, r.metrics["failures_pm"], r.metrics["handovers_pm"]) for r in res]


# ------------------------------------------------------------------ defaults and keys
def test_defaults_untouched():
    P = ProtocolConfig()
    assert (P.rlm_interference, P.rlm_rs_type, P.rlm_ssb_overlap, P.rlm_bg_se) == ("static", "ssb", 1.0, 2.0)
    sc = _sc()
    d = sc.to_dict()
    assert not any(k.startswith("rlm_") and k not in ("rlm_holdoff_s", "rlm_eval") for k in d["protocol"])
    explicit = _sc({"protocol.rlm_interference": "static", "protocol.rlm_rs_type": "ssb",
                    "protocol.rlm_ssb_overlap": 1.0, "protocol.rlm_bg_se": 2.0})
    assert explicit.to_dict() == d                                  # same job IDs
    assert "rlm_interference" in _sc(DYN).to_dict()["protocol"]
    # sub-keys without the option change nothing
    assert _key(_run(_sc({"protocol.rlm_rs_type": "csi-rs", "protocol.rlm_bg_se": 5.0}))) == _key(_run(sc))


@pytest.mark.parametrize("ov,msg", [
    ({"protocol.rlm_interference": "on"}, "rlm_interference"),
    ({"protocol.rlm_rs_type": "dmrs"}, "rlm_rs_type"),
    ({"protocol.rlm_ssb_overlap": 1.5}, "rlm_ssb_overlap"),
    ({"protocol.rlm_bg_se": 0.0}, "rlm_bg_se"),
    (dict(DYN, **{"protocol.lm_load": 0.3}), "rlm_interference"),
    (dict(DYN, **{"protocol.lm_load_per_ue": 0.1}), "rlm_interference"),
    (dict(DYN, **{"protocol.rlm_eval": "ts38133"}), "rlm_interference"),
    (dict(DYN, **{"traffic.ftp_file_bytes": 0}), "ftp_file_bytes")])
def test_validation(ov, msg):
    with pytest.raises(ConfigError, match=msg):
        _sc(ov)


# ------------------------------------------------------------------ weights and limits
def test_weights():
    b = np.array([0.0, 1.0, 0.5, 0.0])
    u = np.array([0.0, 0.3, 0.2, 0.4])
    a = b + (1 - b) * u                                             # transmitted share
    out = np.empty(4)
    core.rlm_weights(ProtocolConfig(rlm_rs_type="csi-rs"), 0.3, b, u, out)
    assert out == pytest.approx(0.3 * a)
    core.rlm_weights(ProtocolConfig(rlm_rs_type="ssb", rlm_ssb_overlap=1.0), 0.3, b, u, out)
    assert (out == 1.0).all()                                       # neighbour SSBs: always on, no isolation
    core.rlm_weights(ProtocolConfig(rlm_rs_type="ssb", rlm_ssb_overlap=0.25), 0.3, b, u, out)
    assert out == pytest.approx(0.25 + 0.75 * 0.3 * a)
    core.rlm_weights(ProtocolConfig(rlm_rs_type="ssb", rlm_ssb_overlap=0.0), 0.3, b, u, out)
    assert out == pytest.approx(0.3 * a)                            # SSBs that never meet: as CSI-RS


@pytest.mark.parametrize("dyn,iso", [(CSI, 0.3), (DYN, 1.0)])
def test_full_load_reduces_to_the_static_model(dyn, iso):
    """Every cell always transmitting: CSI-RS gives isolation x 1, SSB (with isolation 1) gives 1, the weights
    of the static model at full load."""
    iso_ov = {"radio.isolation": iso}
    st = _run(_sc(FULL, iso_ov))
    dy = _run(_sc(FULL, iso_ov, dyn))
    assert [r.metrics["failures_pm"] for r in dy] == pytest.approx([r.metrics["failures_pm"] for r in st])
    assert [r.metrics["handovers_pm"] for r in dy] == pytest.approx([r.metrics["handovers_pm"] for r in st])
    assert sum(r.metrics["failures_pm"] for r in st) > 0             # the limit is not trivial


def _record(sc, seed=3):
    """Link-monitoring SINR, SNR and SINR with every neighbour transmitting, at every step of one rule."""
    w = hl.build_world(sc, seed)
    from handoverlab.channel.source import RadioSource
    from handoverlab.simulate import _instantiate
    e = core.Engine(w, _instantiate(RULES[0]))
    rec = []
    orig = e.proc.step

    def step(t):
        ln = e.lm_ln
        ls = ln[e.ar, e.serv]
        con = e.state == CONNECTED
        rec.append((np.array(e.sl_now)[con], (ls / e.noise)[con], (ls / (ln.sum(1) - ls + e.noise))[con],
                    np.array(e.b_now)))
        return orig(t)
    e.proc.step = step
    for ch in RadioSource(w, 500).chunks():
        e.advance(ch)
    return e, rec


def test_zero_activity_gives_the_snr_or_the_ssb_interference():
    e, rec = _record(_sc(IDLE, CSI))
    assert not e.u_occ.any() and not e.bursts.full.any()
    for sl, snr, _, b in rec[:200]:
        assert not b.any()
        assert np.array_equal(sl, snr)                              # CSI-RS, no activity: the SNR
    _, rec = _record(_sc(IDLE, DYN, {"radio.isolation": 1.0}))
    for sl, _, sinr1, _ in rec[:200]:
        assert sl == pytest.approx(sinr1, rel=1e-9)                 # SSB: neighbour SSBs only


# ------------------------------------------------------------------ the burst process
def test_bursts_follow_the_queue():
    """M/D/1: busy share = load, mean busy period d / (1 - load); the correlation time grows with d."""
    dt = 0.01

    def series(load, d, n=100000, seed=1):
        cb = CellBursts(load, d * 1e6, 1e6, dt, np.random.default_rng(seed))
        return np.array([cb.step() for _ in range(n)])

    x = series([0.0, 0.3, 0.6, 1.0, 1.7], 0.2)
    assert (x[:, 0] == 0).all() and (x[:, 3] == 1).all() and (x[:, 4] == 1).all()
    for j, rho in ((1, 0.3), (2, 0.6)):
        assert x[:, j].mean() == pytest.approx(rho, abs=0.03)
        on = x[:, j] > 0
        starts = np.count_nonzero(on[1:] & ~on[:-1])
        busy = np.count_nonzero(on) * dt / starts                   # mean busy period [s]
        assert busy == pytest.approx(0.2 / (1 - rho), rel=0.12)

    def corr(s, lag):
        s = s - s.mean()
        return float((s[:-lag] * s[lag:]).mean() / s.var())
    short, long_ = series([0.3], 0.05)[:, 0], series([0.3], 0.5)[:, 0]
    assert corr(long_, 20) > 0.5 > corr(short, 20)                  # 200 ms apart: correlated only for long files
    assert abs(corr(short, 100)) < 0.05


def test_engine_bursts_use_their_own_stream():
    sc = _sc(DYN)
    e, rec = _record(sc, seed=5)
    w = hl.build_world(sc, 5)
    cb = CellBursts(w.bg_load, 8.0 * sc.traffic.ftp_file_bytes, sc.radio.bandwidth_mhz * 1e6 * 2.0,
                    sc.protocol.step_s, streams(5, "rlm", 1)[0])
    ref = np.array([cb.step() for _ in range(len(rec))])
    assert np.array_equal(np.array([r[3] for r in rec]), ref)
    assert ref.mean(0) == pytest.approx(w.bg_load, abs=0.15)
    # the radio samples, trajectories and background loads do not move
    w0 = hl.build_world(_sc(), 5)
    assert np.array_equal(w0.x, w.x) and np.array_equal(w0.bg_load, w.bg_load)


# ------------------------------------------------------------------ engines and seeds
@pytest.mark.parametrize("dyn", [DYN, CSI, dict(DYN, **{"protocol.rlm_ssb_overlap": 0.5})])
def test_single_and_batch_agree(dyn):
    sc = _sc(dyn)
    assert _key(_run(sc, batch=True)) == _key(_run(sc, batch=False))


def test_seeds_reproducible_and_dynamic_differs():
    sc = _sc(CSI)
    a, b = _run(sc, 7), _run(sc, 7)
    assert _key(a) == _key(b)
    assert _key(_run(sc, 8)) != _key(a)
    assert _key(_run(_sc(DYN), 7)) != _key(_run(_sc(), 7))          # the SSB model changes the result


def test_numba_kernel_not_used():
    e = core.Engine(hl.build_world(_sc(DYN), 3), __import__("handoverlab.simulate", fromlist=["x"])._instantiate(
        RULES[0]))
    assert e.dyn and e.lm
    e.world.scenario.run.backend = "numba"                          # the check runs before numba is imported
    try:
        assert core.rlm_kernel(e) is None
    finally:
        e.world.scenario.run.backend = "numpy"


def test_ns3_like_counter_with_dynamic_interference():
    sc = _sc(DYN, {"protocol.ns3_oos_rx": 200.0, "protocol.cmd_during_t310": "lost",
                   "protocol.rlm_holdoff_s": 0.0, "protocol.exec_can_fail": False})
    assert _key(_run(sc, batch=True)) == _key(_run(sc, batch=False))
