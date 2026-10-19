# SPDX-License-Identifier: MIT
"""Traffic models of 1.4.0 (traffic.model): offered traffic is delivered, defaults are unchanged."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.config import ConfigError
from handoverlab.traffic import MODELS, offered_bits

BASE = {"mobility.users": 12, "run.duration_s": 30.0, "run.warmup_s": 5.0}


def _metrics(**over):
    sc = hl.builtin_scenario("smoke").with_overrides(dict(BASE, **{"traffic." + k: v for k, v in over.items()}))
    return sc, hl.run_world(hl.build_world(sc, 2), [hl.A3()])[0].metrics


@pytest.mark.parametrize("model,offered_mbps", [("periodic", 0.04), ("ftp3", 2.0)])
def test_offered_traffic_is_delivered(model, offered_mbps):
    sc, m = _metrics(model=model, ftp_rate_hz=0.5)
    assert m["rate_mbps"] == pytest.approx(offered_mbps, rel=0.15)        # light load: all of it gets through
    assert m["delivered_share"] > 0.9


def test_full_buffer_fills_the_cells():
    _, fixed = _metrics()
    _, full = _metrics(model="full_buffer")
    assert full["mean_load"] > fixed["mean_load"] + 0.1 and full["rate_mbps"] > 10 * fixed["rate_mbps"]


def test_offered_bits():
    from types import SimpleNamespace
    rng = np.random.default_rng(0)
    per = offered_bits(SimpleNamespace(model="periodic", period_s=0.02, packet_bytes=100), 500, 0.04, 3, rng)
    assert per.shape == (500, 3) and per.sum(0) == pytest.approx(np.full(3, 500 * 2 * 800.0), abs=800)
    ftp = offered_bits(SimpleNamespace(model="ftp3", ftp_rate_hz=1.0, ftp_file_bytes=1000), 20000, 0.04, 2, rng)
    assert ftp.sum() / (20000 * 0.04 * 2) == pytest.approx(8000.0, rel=0.1)   # 1 file of 8000 bit per second
    assert offered_bits(SimpleNamespace(model="fixed"), 10, 0.04, 2, rng) is None


def test_several_rules_with_buffered_traffic():
    sc = hl.builtin_scenario("smoke").with_overrides(dict(BASE, **{"traffic.model": "ftp3", "run.duration_s": 10.0}))
    res = hl.run_world(hl.build_world(sc, 1), [hl.A3(), hl.CHO()])     # not batched; each engine has its buffers
    assert len(res) == 2 and all(r.metrics["rate_mbps"] > 0 for r in res)


def test_validation():
    assert MODELS[0] == "fixed" and hl.Scenario().traffic.model == "fixed"
    with pytest.raises(ConfigError, match="traffic.model"):
        hl.builtin_scenario("smoke").with_overrides({"traffic.model": "voip"}).validate()
