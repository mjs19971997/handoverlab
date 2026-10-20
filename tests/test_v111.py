# SPDX-License-Identifier: MIT
"""Other additions of 1.11.0: layer shadowing, memory keys of baseline handovers, the bandit's record, numba."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel.extended import _layer_radio
from handoverlab.config import LayerConfig, RadioConfig, Scenario
from handoverlab.rules import A3, make_rule
from handoverlab.verify.golden import cases, load

SHORT = {"run.duration_s": 30.0, "run.warmup_s": 5.0}


def test_layer_shadowing_keys():
    base = RadioConfig()
    lr = _layer_radio(base, LayerConfig(shadow_nlos_db=6.0, shadow_decorr_m=50.0))
    assert lr.shadow_nlos_db == 6.0 and lr.shadow_decorr_m == 50.0 and lr.shadow_los_db == base.shadow_los_db
    sc = hl.builtin_scenario("dense-urban-2layer")
    assert sc.radio.shadow_nlos_db == 6.0 and sc.radio.layers[0].shadow_nlos_db == 7.82
    assert sc.radio.penetration_db == 9.0 and sc.radio.penetration_sd_db == 5.0
    plain = Scenario().with_overrides({"radio.layers": [{"name": "x", "carrier_ghz": 28.0}]}).to_dict()
    assert "shadow_nlos_db" not in plain["radio"]["layers"][0]          # unset layer keys keep the job IDs


class KeyedA3(A3):
    """A3 that remembers every attempt under the key 7."""
    learns = True

    def reset(self, ctx):
        super().reset(ctx)
        self.keys = []

    def memory_key(self, obs):
        return np.full(self.ctx.n_users, 7)

    def on_outcome(self, rec):
        self.keys.append(rec.key)


def test_baseline_handovers_carry_the_memory_key():
    from handoverlab.channel.source import RadioSource
    from handoverlab.engine.core import Engine
    from handoverlab.world import build_world
    w = build_world(hl.builtin_scenario("smoke").with_overrides(SHORT), 1)
    rule = KeyedA3()
    eng = Engine(w, rule, False, None)
    for ch in RadioSource(w).chunks():
        eng.advance(ch)
    eng.finish()
    assert rule.keys and set(rule.keys) == {7}
    a, b = hl.simulate(w.scenario, [{"rule": "a3"}, KeyedA3()], seeds=[1])
    assert a.fingerprint == b.fingerprint                              # the key does not change the decisions


def test_bandit_keeps_a_record_and_one_arm_is_a3():
    sc = hl.builtin_scenario("smoke").with_overrides(SHORT)
    a, b = hl.simulate(sc, [{"rule": "a3", "off_db": 2.0, "ttt_s": 0.16},
                            {"rule": "a3_bandit", "arms_db": [2.0]}], seeds=[1])
    assert a.fingerprint == b.fingerprint
    from handoverlab.verify.learning import bandit_vs_grid
    r = bandit_vs_grid(duration_s=60.0, seeds=(1,))
    assert r["same_log"] and len(r["objective"]) == 5 and 0.0 <= r["share"] <= 1.0
    rule = make_rule({"rule": "a3_bandit"})
    assert not hasattr(rule, "outcomes")                               # filled at reset, per run


def test_backend_is_checked_and_left_out_of_job_ids():
    with pytest.raises(hl.ConfigError, match="run.backend"):
        Scenario().with_overrides({"run.backend": "cython"})
    try:
        import numba  # noqa: F401
    except ImportError:
        with pytest.raises(hl.ConfigError, match="pip install handoverlab"):
            Scenario().with_overrides({"run.backend": "numba"})
        return
    sc = Scenario().with_overrides({"run.backend": "numba"})
    assert "backend" not in sc.to_dict()["run"] and sc.to_dict(full=True)["run"]["backend"] == "numba"


def test_numba_backend_gives_the_golden_fingerprints():
    pytest.importorskip("numba")
    ref = load()["cases"]
    for name in ("smoke", "smoke-stress", "smoke-3gpp", "smoke-mro"):
        c = cases()[name]
        res = hl.simulate(c["scenario"].with_overrides({"run.backend": "numba"}), c["rules"], seeds=[c["seed"]])
        assert [r.fingerprint for r in res] == [w["fingerprint"] for w in ref[name]], name
