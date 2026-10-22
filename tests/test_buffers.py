# SPDX-License-Identifier: MIT
"""User-plane buffers at handover: PDCP / RLC FIFOs, data forwarding and losses (protocol.buffers, since 2.3.0).

The hand cases drive :class:`~handoverlab.engine.buffers.Buffers` with scripted events for one user: arrivals of
1000 bits at 0 and 40 ms, the UE leaves at 50 ms, 1000 bits arrive at 80 ms, the execution completes at 90 ms,
1000 bits arrive at 120 ms and everything is delivered in the interval from 120 ms at 1 Mbit/s.
"""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError
from handoverlab.engine.buffers import Buffers

B = np.array([1000.0])
FAST = np.array([1e6])


def _buf(**kw):
    kw.setdefault("xn_delay_s", 0.005)
    return Buffers(1, 0.04, **kw)


def _execution(b, kind, deliver=True, harq=0.0):
    b.arrive(0.0, B)
    b.arrive(0.04, B)
    b.leave(0, 0.05, 1, kind, harq)
    b.arrive(0.08, B)
    if kind == "daps":                                  # the source keeps sending during the execution
        assert b.deliver(0.08, np.array([3000.0]), FAST)[0] == pytest.approx(3000.0)
    b.join(0, 0.09, 1)
    b.arrive(0.12, B)
    if deliver:
        b.deliver(0.12, np.array([b.q[0]]), FAST)
    b.check()
    return b.metrics(1.0)


def _mean(*d):
    return 1e3 * sum(d) / len(d)


def test_baseline_forwarding_am():
    """Criterion B3a: nothing lost, the FIFO at the execution start and the arrivals during it are forwarded."""
    m = _execution(_buf(), "ho")
    assert m["pdcp_lost_kbyte_pm"] == 0.0
    assert m["pdcp_forwarded_kbyte_pm"] == pytest.approx(3000 / 8000)
    d = (0.1205, 0.0815, 0.0425, 0.0035)                # departure 0.12 + (c + 500 bit) / 1 Mbit/s - arrival
    assert m["pdcp_delay_ms"] == pytest.approx(_mean(*d))
    assert m["pdcp_delay_forwarded_ms"] == pytest.approx(_mean(*d[:3]))
    assert m["pdcp_delivered_kbyte_pm"] == pytest.approx(4000 / 8000)


def test_baseline_without_forwarding_loses_the_source_data():
    """Criterion B3b: lost = FIFO at the execution start + arrivals until the completion."""
    m = _execution(_buf(forwarding=False), "ho")
    assert m["pdcp_lost_handover_kbyte_pm"] == pytest.approx(3000 / 8000)
    assert m["pdcp_lost_kbyte_pm"] == m["pdcp_lost_handover_kbyte_pm"]
    assert m["pdcp_forwarded_kbyte_pm"] == 0.0
    assert m["pdcp_delay_ms"] == pytest.approx(0.5)     # only the 120 ms arrival: 500 bit at 1 Mbit/s


def test_late_forwarding_waits_two_xn_delays():
    """Criterion B3c: late forwarding (CHO, LTM) after HANDOVER SUCCESS: sending starts 2 x 20 ms after the
    completion at 90 ms, i.e. at 130 ms; early forwarding does not wait."""
    b = _buf(xn_delay_s=0.02)
    b.arrive(0.0, B)
    b.arrive(0.04, B)
    b.leave(0, 0.05, 1, "cond")
    b.arrive(0.08, B)
    b.join(0, 0.09, 1)
    b.arrive(0.12, B)
    assert b.start_fraction(0.12)[0] == pytest.approx(0.75)
    b.deliver(0.12, np.array([4000.0]), FAST)
    m = b.metrics(1.0)
    d = (0.1305, 0.0915, 0.0525, 0.0135)
    assert m["pdcp_delay_ms"] == pytest.approx(_mean(*d))
    assert m["pdcp_forwarded_kbyte_pm"] == pytest.approx(3000 / 8000)
    assert m["pdcp_delay_forwarded_ms"] == pytest.approx(_mean(*d[:3]))
    e = _execution(_buf(xn_delay_s=0.02, early_forwarding=True), "cond")
    assert e["pdcp_delay_ms"] == pytest.approx(_mean(0.1205, 0.0815, 0.0425, 0.0035))


def test_daps_never_stops_and_forwards_copies():
    """Criterion B3d: no loss, the source sends during the execution, every byte of it is forwarded as a copy."""
    m = _execution(_buf(forwarding=False), "daps")      # DAPS always has its forwarding tunnel
    assert m["pdcp_lost_kbyte_pm"] == 0.0
    assert m["pdcp_forwarded_kbyte_pm"] == pytest.approx(3000 / 8000)
    assert m["pdcp_delay_ms"] == pytest.approx(_mean(0.0805, 0.0415, 0.0025, 0.0005))
    assert m["pdcp_delay_forwarded_ms"] == 0.0          # nothing was left for the target


@pytest.mark.parametrize("kind", ["ho", "cond"])
def test_harq_data_at_the_execution(kind):
    """Criterion B3e: UM loses the HARQ data at the execution start (MAC reset, RLC re-establishment), AM not."""
    um = _execution(_buf(mode="um"), kind, harq=500.0)
    am = _execution(_buf(mode="am"), kind, harq=500.0)
    assert um["pdcp_lost_handover_kbyte_pm"] == pytest.approx(500 / 8000)
    assert um["pdcp_forwarded_kbyte_pm"] == pytest.approx(2500 / 8000)
    assert am["pdcp_lost_kbyte_pm"] == 0.0 and am["pdcp_forwarded_kbyte_pm"] == pytest.approx(3000 / 8000)


def test_discard_timer():
    """Criterion B3f: with a 50 ms timer the data of 0 ms are discarded at 80 ms and those of 40 ms at 120 ms."""
    b = _buf(discard_timer_s=0.05)
    for t in (0.0, 0.04, 0.08, 0.12):
        b.arrive(t, B)
        b.discard_old(t)
        if t == 0.08:
            assert b.metrics(1.0)["pdcp_lost_discard_kbyte_pm"] == pytest.approx(1000 / 8000)
    assert b.metrics(1.0)["pdcp_lost_discard_kbyte_pm"] == pytest.approx(2000 / 8000)
    assert b.q[0] == pytest.approx(2000.0)
    b.check()


@pytest.mark.parametrize("forwarding,cell,lost,fwd", [(True, 2, 0.0, 2000.0), (False, 2, 2000.0, 0.0),
                                                       (False, 0, 0.0, 0.0)])
def test_reestablishment(forwarding, cell, lost, fwd):
    """Criterion B3g: kept with forwarding, lost without it in another cell, kept in the same cell."""
    b = _buf(forwarding=forwarding)
    b.arrive(0.0, B)
    b.arrive(0.04, B)
    b.fail(0, 0.05, False)
    b.rejoin(0, 1.05, cell)
    m = b.metrics(1.0)
    assert m["pdcp_lost_failure_kbyte_pm"] == pytest.approx(lost / 8000)
    assert m["pdcp_forwarded_kbyte_pm"] == pytest.approx(fwd / 8000)
    assert b.hold[0] == (pytest.approx(1.055) if fwd else -np.inf)
    b.check()


def test_fifo_order_at_a_constant_rate():
    """Criterion B5 (FIFO order): equal chunks served at a constant rate leave in arrival order."""
    b = Buffers(1, 0.04)
    for t in (0.0, 0.04, 0.08):
        b.arrive(t, B)
    for t in (0.12, 0.16, 0.20):
        b.deliver(t, np.array([1000.0]), np.array([2e4]))   # 20 kbit/s share: 25 kbit/s sends 1000 bit in 40 ms
    assert b.metrics(1.0)["pdcp_delay_ms"] == pytest.approx(_mean(0.12 + 0.02, 0.16 + 0.02 - 0.04,
                                                                  0.20 + 0.02 - 0.08))


SC = {"run.duration_s": 6.0, "run.warmup_s": 1.0, "mobility.users": 4, "traffic.model": "periodic"}
RULES = [{"rule": r} for r in ("a3", "cho", "daps", "ltm", "cltm")]
CAUSES = ("handover", "failure", "discard", "harq")


def test_option_off_changes_nothing():
    """Criterion B1 (the golden fingerprints check it for every card)."""
    sc = hl.builtin_scenario("smoke").with_overrides(SC)
    a = hl.simulate(sc, [{"rule": "a3"}], seeds=[2])[0]
    b = hl.simulate(sc.with_overrides({"protocol.buffers": None}), [{"rule": "a3"}], seeds=[2])[0]
    assert a.fingerprint == b.fingerprint and a.metrics == b.metrics
    assert "buffers" not in sc.to_dict()["protocol"]
    assert all(v == 0.0 for k, v in a.metrics.items() if k.startswith("pdcp_"))


@pytest.mark.parametrize("extra", [{"protocol.buffers": "am"},
                                   {"protocol.buffers": "um", "traffic.model": "ftp3",
                                    "protocol.discard_timer_s": 0.3},
                                   {"protocol.buffers": "am", "protocol.forwarding": False},
                                   {"protocol.buffers": "um", "protocol.scheduler": "rr"}])
def test_conservation_for_every_procedure(extra):
    """Criterion B2: arrived = delivered + lost + queued (checked at the end of every run with the option) and the
    causes add up; debug mode (invariant checks) gives the same metrics."""
    sc = hl.builtin_scenario("smoke").with_overrides(dict(SC, **extra))
    res = hl.simulate(sc, RULES, seeds=[3])
    for r in res:
        m = r.metrics
        assert m["pdcp_lost_kbyte_pm"] == pytest.approx(sum(m["pdcp_lost_%s_kbyte_pm" % c] for c in CAUSES))
        assert m["pdcp_delivered_kbyte_pm"] > 0
    if "protocol.scheduler" not in extra and "traffic.model" not in extra:
        dbg = hl.simulate(sc, RULES[:1], seeds=[3], debug=True)[0]
        assert dbg.fingerprint == res[0].fingerprint and dbg.metrics == res[0].metrics


def test_um_loses_harq_blocks_am_does_not():
    """Criterion B4: with one HARQ transmission every TB error is final: UM loses data, AM re-sends them."""
    sc = hl.builtin_scenario("smoke").with_overrides(dict(SC, **{"protocol.scheduler": "rr",
                                                                 "protocol.harq_max_tx": 1}))
    um = hl.simulate(sc.with_overrides({"protocol.buffers": "um"}), RULES[:1], seeds=[3])[0].metrics
    am = hl.simulate(sc.with_overrides({"protocol.buffers": "am"}), RULES[:1], seeds=[3])[0].metrics
    assert um["pdcp_lost_harq_kbyte_pm"] > 0 and am["pdcp_lost_harq_kbyte_pm"] == 0.0
    assert am["pdcp_lost_kbyte_pm"] <= um["pdcp_lost_kbyte_pm"]


def test_light_load_without_handover_has_a_short_delay():
    """Criterion B5: no handover, light load: the mean PDCP delay is below one measurement interval (40 ms)."""
    parked = [{"share": 1.0, "v_min": 0.1, "v_max": 0.1}]            # 0.6 m in the run
    sc = hl.builtin_scenario("smoke").with_overrides(dict(SC, **{"protocol.buffers": "am", "mobility.groups": parked}))
    m = hl.simulate(sc, [{"rule": "a3"}], seeds=[3])[0].metrics
    assert m["handovers_pm"] == 0.0 and m["failures_pm"] == 0.0
    assert 0.0 < m["pdcp_delay_ms"] < 40.0


def test_buffer_options_are_checked():
    sc = hl.builtin_scenario("smoke")
    with pytest.raises(ConfigError, match="protocol.buffers"):
        sc.with_overrides({"protocol.buffers": "tm"})
    with pytest.raises(ConfigError, match="protocol.discard_timer_s"):
        sc.with_overrides({"protocol.buffers": "am", "protocol.discard_timer_s": 0.07})
    with pytest.raises(ConfigError, match="full_buffer"):
        sc.with_overrides({"protocol.buffers": "am", "traffic.model": "full_buffer"})
    with pytest.raises(ConfigError, match="protocol.buffers"):
        hl.builtin_scenario("urban-grid-28ghz-beams").with_overrides({"protocol.buffers": "am"})
    assert sc.with_overrides({"protocol.buffers": "um", "protocol.discard_timer_s": 0.075}).protocol.buffers == "um"
