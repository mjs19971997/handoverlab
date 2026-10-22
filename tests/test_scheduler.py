# SPDX-License-Identifier: MIT
"""Slot scheduler, MCS, TBS and HARQ (protocol.scheduler, since 2.2.0)."""
import math

import numpy as np
import pytest

import handoverlab as hl
from handoverlab import linklevel as ll
from handoverlab.config import ConfigError
from handoverlab.engine.scheduler import SlotScheduler


def test_mcs_and_cqi_tables_equal_the_text():
    """Criterion S2: TS 38.214 Tables 5.1.3.1-1 and 5.2.2.1-2 (spectral efficiencies as printed, 4 decimals)."""
    se = [0.2344, 0.3066, 0.3770, 0.4902, 0.6016, 0.7402, 0.8770, 1.0273, 1.1758, 1.3262, 1.3281, 1.4766, 1.6953,
          1.9141, 2.1602, 2.4063, 2.5703, 2.5664, 2.7305, 3.0293, 3.3223, 3.6094, 3.9023, 4.2129, 4.5234, 4.8164,
          5.1152, 5.3320, 5.5547]
    assert len(ll.MCS_TABLE1) == 29
    assert np.allclose([ll.spectral_efficiency(m) for m in range(29)], se, atol=6e-5)   # printed to 4 decimals
    cqi = [0.1523, 0.2344, 0.3770, 0.6016, 0.8770, 1.1758, 1.4766, 1.9141, 2.4063, 2.7305, 3.3223, 3.9023, 4.5234,
           5.1152, 5.5547]
    assert np.allclose([q * r / 1024 for q, r in ll.CQI_TABLE1], cqi, atol=6e-5)


def test_tbs_hand_values():
    """Criterion S1, values worked out by hand from the clause (see the comments)."""
    # 6732 REs (51 PRBs, 12 symbols, 12 DMRS REs): N_info = 6732 * 6 * 948 / 1024 = 37394.3; n = 15 - 5 = 10;
    # N' = 1024 * round(37370.3 / 1024 = 36.49) = 36864 > 8424, R > 1/4: C = ceil(36888 / 8424) = 5;
    # TBS = 40 * ceil(36888 / 40) - 24 = 40 * 923 - 24 = 36896
    assert ll.tbs(6732, 28) == 36896
    # 1000 REs, MCS 5: N_info = 1000 * 2 * 379 / 1024 = 740.2; n = max(3, 9 - 6) = 3; N' = 8 * 92 = 736 -> 736
    assert ll.tbs(1000, 5) == 736
    # 5000 REs, MCS 4 (R = 308/1024 > 1/4): N_info = 3007.8 <= 3824; n = 5; N' = 32 * 93 = 2976 -> 2976
    assert ll.tbs(5000, 4) == 2976
    # 20000 REs, MCS 2 (R = 193/1024 <= 1/4): N_info = 7539.1; n = 12 - 5 = 7; N' = 128 * round(58.71) = 7552;
    # C = ceil(7576 / 3816) = 2; TBS = 16 * ceil(7576 / 16) - 24 = 16 * 474 - 24 = 7560
    assert ll.tbs(20000, 2) == 7560
    # 3000 REs, MCS 21 (R = 616/1024): N_info = 10828.1; n = 13 - 5 = 8; N' = 256 * round(42.20) = 10752 > 8424:
    # C = ceil(10776 / 8424) = 2; TBS = 16 * ceil(10776 / 16) - 24 = 16 * 674 - 24 = 10760
    assert ll.tbs(3000, 21) == 10760
    # 1800 REs, MCS 21: N_info = 6496.9; n = 12 - 5 = 7; N' = 128 * round(50.57) = 6528 <= 8424:
    # TBS = 8 * ceil(6552 / 8) - 24 = 6528
    assert ll.tbs(1800, 21) == 6528


def test_bler_model_properties():
    """Criterion S3: monotone in SINR; the MCS rate below the Shannon capacity at the 10 % point; 10 % points
    increasing with the MCS index on a flat channel."""
    nre = ll.n_re(51)
    x = np.linspace(-12.0, 30.0, 841)
    pts = []
    for m in range(29):
        t = ll.tbs(nre, m)
        ncb = nre * ll.MCS_TABLE1[m][0]
        b = ll.bler(x, m, t, ncb)
        assert np.all(np.diff(b) <= 1e-12)
        s10 = x[np.argmax(b <= 0.1)]
        assert ll.spectral_efficiency(m) < math.log2(1 + 10 ** (s10 / 10))
        pts.append(s10)
    assert np.all(np.diff(pts) >= 0) and pts[-1] > pts[0] + 15


class _World:
    def __init__(self, seed=1):
        self.seed = seed
        self.scenario = hl.builtin_scenario("ns3-urban-3.5ghz")


def test_round_robin_shares_are_equal():
    """Criterion S4: equal PRB shares of the backlogged users of a cell (51 PRBs, 3 users: 17 each)."""
    s = SlotScheduler(_World(), 1, 3, "rr", 0.04)
    s.loss = -100.0                                    # error-free decoding: the shares alone decide
    got, used = s.serve(np.full(3, 100.0), np.full(3, 1e12), np.ones(3, dtype=bool), np.zeros(3, dtype=int),
                        np.ones(1))
    assert used[0] == pytest.approx(1.0) and got[0] == got[1] == got[2] > 0


def test_proportional_fair_equalises_time_shares():
    """Criterion S4: two full-buffer users with constant different rates get equal long-run slot shares."""
    s = SlotScheduler(_World(), 1, 2, "pf", 0.04)
    s.loss = -100.0
    tb = np.zeros(2)
    for _ in range(50):
        got, _ = s.serve(np.array([1000.0, 3.0]), np.full(2, 1e12), np.ones(2, dtype=bool), np.zeros(2, dtype=int),
                         np.ones(1))
        tb += got
    shares = tb / np.array([s.select(30.0, s.n_prb)[1], s.select(10 * np.log10(3.0), s.n_prb)[1]])
    assert shares[0] / shares.sum() == pytest.approx(0.5, abs=0.02)


def test_harq_loses_a_block_after_four_failed_transmissions():
    """Criterion S5: with a fixed error probability p per transmission and no combining gain, the lost share is
    p^4 (within the binomial 99 % interval)."""
    s = SlotScheduler(_World(seed=4), 1, 40, "rr", 0.04)
    p = 0.5
    import handoverlab.engine.scheduler as sm
    orig = sm.ll.bler_vec
    sm.ll.bler_vec = lambda sinr_db, mcs, tbs_bits, n_coded, loss_db=1.0: np.full(np.shape(sinr_db), p)
    try:
        for _ in range(40):
            s.serve(np.full(40, 1000.0), np.full(40, 1e12), np.ones(40, dtype=bool), np.zeros(40, dtype=int),
                    np.ones(1))
    finally:
        sm.ll.bler_vec = orig
    done = s.stats["tb_ok"] + s.stats["tb_lost"]
    lost = s.stats["tb_lost"] / done
    half = 2.58 * math.sqrt(p ** 4 * (1 - p ** 4) / done)
    assert abs(lost - p ** 4) <= half


SC = {"run.duration_s": 6.0, "run.warmup_s": 1.0, "mobility.users": 4, "traffic.model": "full_buffer"}


def test_option_off_changes_nothing_and_runs_are_reproducible():
    """Criterion S6 (the golden fingerprints check it for every card) and reproducibility with the option."""
    sc = hl.builtin_scenario("smoke").with_overrides(SC)
    a = hl.simulate(sc, [{"rule": "a3"}], seeds=[2])[0]
    b = hl.simulate(sc.with_overrides({"protocol.scheduler": None}), [{"rule": "a3"}], seeds=[2])[0]
    assert a.fingerprint == b.fingerprint and a.metrics == b.metrics
    assert "scheduler" not in sc.to_dict()["protocol"]
    s = sc.with_overrides({"protocol.scheduler": "rr"})
    c = hl.simulate(s, [{"rule": "a3"}], seeds=[2], debug=True)[0]
    d = hl.simulate(s, [{"rule": "a3"}], seeds=[2])[0]
    assert c.fingerprint == d.fingerprint and c.metrics == d.metrics
    assert c.metrics["rate_mbps"] != a.metrics["rate_mbps"]


def test_scheduler_options_are_checked():
    sc = hl.builtin_scenario("smoke")
    with pytest.raises(ConfigError, match="protocol.scheduler"):
        sc.with_overrides({"protocol.scheduler": "fifo"})
    with pytest.raises(ConfigError, match="protocol.harq_max_tx"):
        sc.with_overrides({"protocol.scheduler": "rr", "protocol.harq_max_tx": 0})
    with pytest.raises(ConfigError, match="protocol.scheduler"):
        hl.builtin_scenario("urban-grid-28ghz-beams").with_overrides({"protocol.scheduler": "pf"})
