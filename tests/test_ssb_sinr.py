# SPDX-License-Identifier: MIT
"""The optional SS-SINR of beam cells (radio.beams.ssb_sinr "ssb", since 2.9.0): defaults untouched, the share
0 equal to today's model, the interference on the SSS resource elements by hand, and validation."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel.extended import ExtendedSource
from handoverlab.config import BeamConfig, ConfigError
from handoverlab.engine.extended import ExtEngine
from handoverlab.world import build_world

BEAMS = {"radio.beams": {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8, "panel": [8, 8], "tilt_deg": 102.0}}
SHORT = {"mobility.users": 8, "run.duration_s": 8.0, "run.warmup_s": 1.0}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.256}]


def _sc(**beam_keys):
    b = dict(BEAMS["radio.beams"], **beam_keys)
    return hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(dict(SHORT, **{"radio.beams": b}))


def _fp(sc, seed=4):
    return [(r.fingerprint, r.metrics["failures_pm"]) for r in hl.run_world(hl.build_world(sc, seed), RULES)]


def test_default_unchanged():
    assert (BeamConfig().ssb_sinr, BeamConfig().ssb_overlap) == ("data", 1.0)
    d = _sc().to_dict()["radio"]["beams"]
    assert "ssb_sinr" not in d and "ssb_overlap" not in d
    assert _fp(_sc()) == _fp(_sc(ssb_sinr="data"))


def test_share_zero_is_the_data_model():
    # with ssb_overlap 0 every SSS resource element sees the data-channel interference: bit for bit today's model
    assert _fp(_sc(ssb_sinr="ssb", ssb_overlap=0.0)) == _fp(_sc())


def test_full_overlap_changes_the_run():
    assert _fp(_sc(ssb_sinr="ssb")) != _fp(_sc())
    assert "ssb_sinr" in _sc(ssb_sinr="ssb").to_dict()["radio"]["beams"]


def test_interference_by_hand():
    sc = _sc(ssb_sinr="ssb", ssb_overlap=0.7)
    w = build_world(sc, 3)
    e = ExtEngine(w, hl.make_rule(RULES[0]))
    ch = next(ExtendedSource(w, 50).chunks())
    e.advance(ch)
    i = 7
    ln = ch.lin[i]
    totc = e._tot(ln, e.rc)
    users = np.arange(e.U)
    beams = np.array([u % 8 for u in users])
    got = e._ssb_interference(i, ch, users, beams, ln, totc)
    ext = w.ext
    for u in users:
        c = int(e.serv[u])
        full = sum(10.0 ** ((float(ch.site_db[i, u, ext.cell_site[m]]) + float(ext.p0[m])
                             + float(ch.bg[i // ch.mp, u, m, beams[u]])) / 10.0) for m in range(e.M) if m != c)
        data = float(totc[u, 0] - e.rc[c] * ln[u, c])
        want = 0.7 * full + 0.3 * data + float(e.noise_c[c])
        assert abs(got[u] - want) <= 1e-6 * want


def test_attach_starts_monitoring_from_the_ss_sinr():
    # after a handover or re-establishment, link monitoring and beam failure detection start from the SS-SINR of
    # the joined beam, not from the data-channel SINR
    w = build_world(_sc(ssb_sinr="ssb"), 3)
    e = ExtEngine(w, hl.make_rule(RULES[0]))
    ch = next(ExtendedSource(w, 50).chunks())
    e.advance(ch)
    u = 2
    cell = int(e.serv[u])
    e._attach(u, cell, 1.0, 0.5)
    i = e._i
    ln = ch.lin[i]
    totc = e._tot(ln, e.rc)
    p = e._beam_power(i, ch, np.array([u]), np.array([cell]), np.array([e.sb[u]]))[0]
    want = p / e._ssb_interference(i, ch, np.array([u]), np.array([e.sb[u]]), ln, totc)[0]
    assert abs(e.qo[u] - want) <= 1e-9 * want and abs(e.bfd_q[u] - want) <= 1e-9 * want
    data = p / (totc[u, 0] - e.rc[cell] * ln[u, cell] + e.noise_c[cell])
    assert abs(want - data) > 1e-6 * data


def test_full_overlap_lowers_the_link_quality():
    # neighbours' SSBs are sent whatever the load: on average the SS-SINR is below the data-channel SINR
    out = []
    for keys in ({}, {"ssb_sinr": "ssb"}):
        w = build_world(_sc(**keys), 3)
        e = ExtEngine(w, hl.make_rule(RULES[0]))
        q = []
        for ch in ExtendedSource(w, 50).chunks():
            e.advance(ch)
            q.append(np.median(10.0 * np.log10(e.sl_now)))
        out.append(np.mean(q))
    assert out[1] < out[0] - 1.0


@pytest.mark.parametrize("over, word", [
    ({"radio.beams.ue_panels": 1}, "ssb_sinr"),
    ({"radio.beams.rlm_rs": "beams"}, "ssb_sinr"),
    ({"protocol.lm_load": 0.5}, "ssb_sinr"),
    ({"protocol.lm_load_per_ue": 0.1}, "ssb_sinr"),
    ({"radio.layers": [{"name": "fr2", "carrier_ghz": 28.0}]}, "ssb_sinr"),
    ({"radio.beams.ssb_sinr": "sss"}, "ssb_sinr"),
    ({"radio.beams.ssb_overlap": 1.5}, "ssb_overlap"),
])
def test_validation(over, word):
    with pytest.raises(ConfigError, match=word):
        _sc(ssb_sinr="ssb").with_overrides(over)
