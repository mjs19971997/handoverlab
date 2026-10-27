# SPDX-License-Identifier: MIT
"""The optional Poisson-line LOS process (radio.los_process: poisson_lines): defaults untouched, the correlation
of the LOS state itself on the map and along the users' paths, the LOS share, seeds, soft LOS and validation."""
import numpy as np
import pytest
from scipy.special import ndtri

import handoverlab as hl
from handoverlab.channel import radiomap
from handoverlab.channel.pathloss import los_args, p_los
from handoverlab.channel.radiomap import RadioMap, poisson_line_field
from handoverlab.channel.source import RadioSource
from handoverlab.config import ConfigError, RadioConfig
from handoverlab.studies.runner import run_key

SHORT = {"mobility.users": 8, "run.duration_s": 10.0, "run.warmup_s": 1.0}
PL = {"radio.los_process": "poisson_lines"}
RULES = [{"rule": "a3", "name": "A3", "off_db": 2.0, "ttt_s": 0.08}]


def _sc(name, *ovs):
    d = dict(SHORT)
    for o in ovs:
        d.update(o)
    return hl.builtin_scenario(name).with_overrides(d)


def _key(sc, seed=3):
    return [(r.fingerprint, r.metrics["failures_pm"], r.metrics["handovers_pm"])
            for r in hl.run_world(hl.build_world(sc, seed), RULES)]


# ------------------------------------------------------------------ defaults and validation
def test_default_unchanged():
    assert RadioConfig().los_process == "gaussian"
    for name in ("smoke", "open-area-10ghz"):
        sc = _sc(name)
        explicit = _sc(name, {"radio.los_process": "gaussian"})
        d = sc.to_dict()
        assert "los_process" not in d["radio"]
        assert explicit.to_dict() == d                                  # same job IDs
        assert run_key(explicit.to_dict(), 3, "a3", {}) == run_key(d, 3, "a3", {})
        assert _key(explicit) == _key(sc)
    assert _sc("smoke", PL).to_dict()["radio"]["los_process"] == "poisson_lines"


@pytest.mark.parametrize("name,ov", [
    ("smoke", {"radio.los_process": "lines"}),
    ("ntn-leo600-2ghz", PL),                                            # own LOS model
    ("ntn-leo600-2ghz", dict(PL, **{"ntn.los_model": "probability"})),
    ("highway-tr37885-4ghz", PL),                                       # every link LOS
    ("ns3-urban-3.5ghz", PL),                                           # LOS from the buildings only
    ("open-area-10ghz", dict(PL, **{"radio.los_model": "los"}))])
def test_validation(name, ov):
    with pytest.raises(ConfigError, match="los_process"):
        _sc(name, ov)


def test_refused_with_a_radio_map_file(tmp_path):
    f = tmp_path / "map.npz"
    np.savez(str(f), a=np.zeros(2))                       # validation only needs the file to exist
    with pytest.raises(ConfigError, match="los_process"):
        _sc("smoke", PL, {"radio.map_file": str(f)})


# ------------------------------------------------------------------ the line field itself
def test_line_field_cells():
    L = 50.0
    x = np.arange(0.0, 20000.0, 5.0)
    M = 10
    P = len(x)
    ip, im = np.repeat(np.arange(P), M), np.tile(np.arange(M), P)
    v = poisson_line_field(np.random.default_rng(1), x, np.zeros(P), ip, im, M, L).reshape(P, M)
    assert abs(v.mean()) < 0.05 and abs(v.std() - 1.0) < 0.05             # standard normal values
    for d in (10.0, 50.0, 100.0):
        k = int(d / 5.0)
        same = (v[k:] == v[:-k]).mean()                                 # one cell: exp(-d / L)
        assert same == pytest.approx(np.exp(-d / L), abs=0.03)
        los = v < ndtri(0.3)
        c = np.corrcoef(los[k:].ravel(), los[:-k].ravel())[0, 1]
        assert c == pytest.approx(np.exp(-d / L), abs=0.04)
    assert (v < ndtri(0.3)).mean() == pytest.approx(0.3, abs=0.03)
    again = poisson_line_field(np.random.default_rng(1), x, np.zeros(P), ip, im, M, L).reshape(P, M)
    assert np.array_equal(v, again)


# ------------------------------------------------------------------ map (street grid)
def _street_rows(rm):
    rows = []
    for iy in range(rm.ny):
        row = rm.idx[iy]
        if (row < rm.n_pix).mean() > 0.95:                              # a full row of street pixels
            rows.append(rm.los[row[row < rm.n_pix]])
    return rows


def _map_corr(monkeypatch, process, seed=1):
    """Correlation of the LOS indicator at the lag los_corr_m along the streets (LOS probability 1/2)."""
    monkeypatch.setattr(radiomap, "p_los", lambda d, *a, **kw: np.full(np.shape(d), 0.5))
    sc = _sc("smoke", {"radio.building_los": False, "radio.los_process": process})
    rm = RadioMap(hl.build_world(sc, seed).radio_map.layout, sc.radio, seed)
    monkeypatch.undo()
    k = int(round(sc.radio.los_corr_m / rm.res))
    rows = _street_rows(rm)
    a = np.concatenate([r[k:] for r in rows]).astype(float)
    b = np.concatenate([r[:-k] for r in rows]).astype(float)
    return float(np.mean([np.corrcoef(a[:, m], b[:, m])[0, 1] for m in range(a.shape[1])])), rm.los_share


def test_map_state_correlation(monkeypatch):
    c, share = _map_corr(monkeypatch, "poisson_lines")
    assert c == pytest.approx(np.exp(-1.0), abs=0.07)
    assert share == pytest.approx(0.5, abs=0.05)
    g, _ = _map_corr(monkeypatch, "gaussian")
    assert g < c - 0.05                                                 # Gaussian field: faster decorrelation


def test_map_los_share():
    sc = _sc("smoke", PL, {"radio.building_los": False})
    rm = hl.build_world(sc, 2).radio_map
    YY, XX = np.nonzero(rm.idx < rm.n_pix)
    order = np.argsort(rm.idx[YY, XX])
    x, y = rm.x0 + XX[order] * rm.res, rm.y0 + YY[order] * rm.res
    d2 = rm.layout.distances(x, y)
    expect = float(np.mean(p_los(d2, sc.radio.pathloss, **los_args(sc.radio))))
    assert rm.los_share == pytest.approx(expect, abs=0.04)


def test_map_runs_deterministic_and_change():
    base = _key(_sc("smoke"))
    a = _key(_sc("smoke", PL))
    assert a == _key(_sc("smoke", PL))
    assert a != base
    soft = {"radio.soft_los": True}
    s = _key(_sc("smoke", PL, soft))
    assert s == _key(_sc("smoke", PL, soft)) and s != _key(_sc("smoke", soft))


# ------------------------------------------------------------------ along the users' paths (open area)
def _route(process, n=4000):
    sc = _sc("open-area-10ghz", {"radio.los_process": process})
    src = RadioSource(hl.build_world(sc, 5))
    g = np.concatenate([src._los_users(n // 2), src._los_users(n // 2)])   # across a chunk boundary
    k = np.rint(sc.radio.los_corr_m / (src.V * sc.protocol.step_s)).astype(int)   # steps per los_corr_m
    return g, k


def test_route_state_correlation():
    g, k = _route("poisson_lines")
    los = g < 0.0
    same = np.mean([(g[k[u]:, u] == g[:-k[u], u]).mean() for u in range(g.shape[1])])
    assert same == pytest.approx(np.exp(-1.0), abs=0.05)
    c = np.mean([np.corrcoef(los[k[u]:, u].ravel(), los[:-k[u], u].ravel())[0, 1] for u in range(g.shape[1])])
    assert c == pytest.approx(np.exp(-1.0), abs=0.07)
    assert los.mean() == pytest.approx(0.5, abs=0.05)
    h, _ = _route("gaussian")
    los = h < 0.0
    assert np.mean([np.corrcoef(los[k[u]:, u].ravel(), los[:-k[u], u].ravel())[0, 1]
                    for u in range(h.shape[1])]) < c - 0.05


def test_route_runs_deterministic_and_change():
    a = _key(_sc("open-area-10ghz", PL))
    assert a == _key(_sc("open-area-10ghz", PL))
    assert a != _key(_sc("open-area-10ghz"))
    s = _key(_sc("indoor-office-4ghz", PL))                             # soft LOS state along the path
    assert s == _key(_sc("indoor-office-4ghz", PL)) and s != _key(_sc("indoor-office-4ghz"))
