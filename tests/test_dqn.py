# SPDX-License-Identifier: MIT
"""The DQN rule (optional PyTorch, since 1.11.0)."""
import numpy as np
import pytest

import handoverlab as hl
from handoverlab.cli import main
from handoverlab.rules import dqn as dqn_mod

SHORT = {"run.duration_s": 40.0, "run.warmup_s": 5.0}


def test_rules_list_names_the_missing_package(monkeypatch, capsys):
    monkeypatch.setattr(dqn_mod.DQNA3, "installed", staticmethod(lambda: False))
    assert main(["rules"]) == 0
    line = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("dqn")][0]
    assert "needs PyTorch" in line


def test_without_torch_the_rule_says_how_to_install(monkeypatch):
    def missing():
        raise ImportError(dqn_mod.INSTALL_HINT)
    monkeypatch.setattr(dqn_mod, "_torch", missing)
    with pytest.raises(ImportError, match=r"handoverlab\[torch\]"):
        hl.make_rule({"rule": "dqn"})


def test_features_are_scaled():
    obs = type("O", (), {})()
    obs.gap_db = np.array([[0.0, -3.0, 2.0], [5.0, 0.0, -40.0]])
    obs.meas_dbm = np.array([[-80.0, -83.0, -78.0], [-95.0, -100.0, -140.0]])
    obs.serving = np.array([0, 1])
    obs.speed = np.array([15.0, 30.0])
    f = dqn_mod.features(obs)
    assert f.shape == (2, 5)
    assert np.allclose(f[0], [1.0, 0.2, -0.3, -3.0, 0.5]) and np.allclose(f[1], [0.0, 0.5, -4.0, -3.0, 1.0])


def test_dqn_contract_training_and_reproducibility(tmp_path):
    pytest.importorskip("torch")
    from handoverlab.testing import check_rule
    check_rule("dqn")
    sc = hl.builtin_scenario("smoke").with_overrides(SHORT)
    path = str(tmp_path / "w.pt")
    rule = dqn_mod.train(sc, [101], path, train_every=2, batch=16)
    assert rule.n_rewards > 0 and rule.n_steps > 0
    spec = {"rule": "dqn", "mode": "test", "weights": path}
    a = hl.simulate(sc, [spec], seeds=[1])[0]
    b = hl.simulate(sc, [spec], seeds=[1])[0]
    assert a.fingerprint == b.fingerprint and a.params["weights"] == path
    q = hl.make_rule(spec)
    q.reset(type("C", (), {"n_users": 2, "rng": np.random.default_rng(0)})())
    assert np.allclose(q.q_values(np.zeros((1, 5))), rule.q_values(np.zeros((1, 5))))
