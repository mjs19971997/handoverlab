# SPDX-License-Identifier: MIT
"""Compiled slot scheduler (run.backend: numba, since 2.4.0): bit-identical to the NumPy loop on the same build."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.engine import _kernels
from handoverlab.engine.scheduler import SlotScheduler


class _World:
    def __init__(self, seed=3):
        self.seed = seed
        self.scenario = hl.builtin_scenario("ns3-urban-3.5ghz")


STATE = ("h_bits", "h_data", "h_sinr", "h_tx", "h_due", "h_mcs", "h_ncb", "avg", "lost_bits", "sinr_rep")


def _play(kind, max_tx, kernel, n_int=25, U=12, M=3):
    """``n_int`` intervals of random inputs (SINR, free shares, demands, connections, cells, first slots and MAC
    resets); returns everything the scheduler gives back or keeps."""
    s = SlotScheduler(_World(), M, U, kind, 0.01, harq_max_tx=max_tx, harq_rtt_slots=4)
    if kernel is not None:
        s.use_kernel(kernel)
    rng = np.random.default_rng(7)
    serv = rng.integers(0, M, U)
    out = []
    for i in range(n_int):
        sinr = 10.0 ** (rng.uniform(-8.0, 28.0, U) / 10.0)
        demand = rng.choice([0.0, 3e3, 4e4, 1e9], U)
        con = rng.random(U) < 0.85
        free = rng.choice([0.0, 0.3, 0.71, 1.0], M)
        if i % 4 == 1:
            serv[rng.integers(0, U)] = rng.integers(0, M)
        first = rng.integers(0, s.n_slots + 2, U) if i % 3 == 0 else None
        got, used = s.serve(sinr, demand, con, serv.copy(), free, first)
        out.append((got, used, s.inflight()))
        if i % 5 == 2:
            out.append(s.flush(int(rng.integers(0, U))))
    return out, {k: getattr(s, k).copy() for k in STATE}, s.stats


def _assert_same(a, b):
    (oa, sa, ta), (ob, sb, tb) = a, b
    assert ta == tb and ta["retx"] > 0 and ta["tb_lost"] > 0
    for x, y in zip(oa, ob):
        if isinstance(x, tuple):
            assert all(np.array_equal(p, q) for p, q in zip(x, y))
        else:
            assert x == y
    for k in STATE:
        assert np.array_equal(sa[k], sb[k], equal_nan=True), k


@pytest.mark.parametrize("kind,max_tx", [("rr", 4), ("pf", 4), ("rr", 2), ("pf", 1)])
def test_kernel_logic_equals_numpy_loop(kind, max_tx):
    """Criterion E1 a) and c): the loop run as plain Python (no compiler), compared with ==."""
    if max_tx == 1:
        ref = _play(kind, max_tx, None)
        assert ref[2]["retx"] == 0
        out = _play(kind, max_tx, _kernels._sched_slots)
        assert out[2] == ref[2] and all(np.array_equal(out[1][k], ref[1][k], equal_nan=True) for k in STATE)
        return
    _assert_same(_play(kind, max_tx, _kernels._sched_slots), _play(kind, max_tx, None))


@pytest.mark.parametrize("kind,max_tx", [("rr", 4), ("pf", 4), ("rr", 1)])
def test_compiled_kernel_equals_numpy_loop(kind, max_tx):
    """Criterion E1 a) with Numba."""
    pytest.importorskip("numba")
    a, b = _play(kind, max_tx, _kernels.sched_slots), _play(kind, max_tx, None)
    if max_tx == 1:
        assert a[2] == b[2] and all(np.array_equal(a[1][k], b[1][k], equal_nan=True) for k in STATE)
    else:
        _assert_same(a, b)


SC = {"run.duration_s": 1.2, "run.warmup_s": 0.4, "mobility.users": 6, "traffic.model": "full_buffer"}
RUNS = {
    "rr": {"protocol.scheduler": "rr"},
    "pf-fading": {"protocol.scheduler": "pf", "radio.fast_fading": "tdl-c"},
    "rr-um-2tx": {"protocol.scheduler": "rr", "protocol.buffers": "um", "traffic.model": "periodic",
                  "protocol.harq_max_tx": 2},
    "pf-am": {"protocol.scheduler": "pf", "protocol.buffers": "am", "traffic.model": "periodic"},
}


def _same_runs(name, ov):
    sc = hl.builtin_scenario("smoke").with_overrides({**SC, **ov})
    ref = hl.simulate(sc, [{"rule": "a3"}], seeds=[2])[0]                          # NumPy, same build
    res = hl.simulate(sc.with_overrides({"run.backend": "numba"}), [{"rule": "a3"}], seeds=[2])[0]
    assert res.fingerprint == ref.fingerprint and res.metrics == ref.metrics, name


@pytest.mark.parametrize("name", list(RUNS))
def test_numba_scheduler_runs_equal_numpy(name):
    """Criterion E1 b): fingerprint and every metric equal (==) with both backends."""
    pytest.importorskip("numba")
    _same_runs(name, RUNS[name])


def test_scheduler_kernel_logic_in_a_run_without_numba(monkeypatch):
    """Criterion E1 c): a whole run through the engine with the plain-Python loop."""
    monkeypatch.setattr(_kernels, "sched_slots", _kernels._sched_slots)
    monkeypatch.setattr(_kernels, "rlm_step", _kernels._rlm_step)
    monkeypatch.setattr(_kernels, "available", lambda: True)
    _same_runs("rr-um-2tx", {**RUNS["rr-um-2tx"], "run.duration_s": 1.0})


def test_debug_mode_uses_the_numpy_loop(monkeypatch):
    monkeypatch.setattr(_kernels, "sched_slots", _kernels._sched_slots)
    monkeypatch.setattr(_kernels, "available", lambda: True)
    sc = hl.builtin_scenario("smoke").with_overrides({**SC, **RUNS["rr"], "run.backend": "numba"})
    from handoverlab.engine.core import Engine
    from handoverlab.rules import make_rule
    from handoverlab.world import build_world
    w = build_world(sc, 2)
    assert Engine(w, make_rule({"rule": "a3"}), debug=True).sched.kernel is None
    assert Engine(w, make_rule({"rule": "a3"}), debug=False).sched.kernel is _kernels._sched_slots


def test_vectorised_mcs_lookup_equals_select():
    """The MCS look-up of the compiled path (all MCS in one array operation) gives select()'s values."""
    for loss in (1.0, -0.5, 2.5):
        a, b = SlotScheduler(_World(), 1, 1, "rr", 0.01), SlotScheduler(_World(), 1, 1, "rr", 0.01)
        a.loss = b.loss = loss
        for n in (1, 2, 5, 17, 51, 133, 273):
            for x in np.arange(-150, 351, 8) / 10.0:
                assert a.select(x, n) == b.select_all(x, n), (loss, n, x)
