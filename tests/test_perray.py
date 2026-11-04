# SPDX-License-Identifier: MIT
"""Per-ray beam gains (radio.beams.angular_spread "per_ray"): defaults untouched, the TR 38.901 tables, the
cluster procedure, a single ray against the geometric gain, the compiled loops against the NumPy path (same
process, ==), whole runs under both backends, invariance to chunks, blocks and shared radio, and validation."""
import json
import math

import numpy as np
import pytest

import handoverlab as hl
from handoverlab.channel import _perray_kernels as pk
from handoverlab.channel import perray as pr
from handoverlab.channel.antenna import beam_azimuths_deg, beam_gain_db
from handoverlab.channel.extended import ExtendedSource
from handoverlab.config import BeamConfig, ConfigError
from handoverlab.simulate import run_shared

BEAMS = {"sectors": 3, "sector_az0_deg": 30.0, "n_ssb": 8, "panel": [8, 8], "tilt_deg": 102.0}
SHORT = {"mobility.users": 4, "run.duration_s": 2.5, "run.warmup_s": 0.5}
TINY = {"mobility.users": 2, "run.duration_s": 1.2, "run.warmup_s": 0.2}
RULES = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.256}]


def _uma(**beam_keys):
    return hl.builtin_scenario("urban-macro-tr37885-4ghz").with_overrides(
        dict(SHORT, **{"radio.beams": dict(BEAMS, **beam_keys)}))


def _f(**over):
    sc = hl.builtin_scenario("urban-grid-28ghz-beams")
    beams = dict(sc.to_dict(full=True)["radio"]["beams"], angular_spread="per_ray")
    return sc.with_overrides(dict(SHORT, **{"radio.beams": beams}, **over))


def _runs(sc, seed=7, **kw):
    """Fingerprints and metrics as JSON (NaN compares equal to NaN)."""
    return [(r.fingerprint, json.dumps(r.metrics, sort_keys=True))
            for r in hl.run_world(hl.build_world(sc, seed), RULES, **kw)]


# ---------------------------------------------------------------------------------------------- defaults and runs
def test_default_unchanged():
    assert BeamConfig().angular_spread == "none" and BeamConfig().per_ray_prune_db == 40.0
    d = _uma().to_dict()["radio"]["beams"]
    assert "angular_spread" not in d and "per_ray_prune_db" not in d
    assert _runs(_uma()) == _runs(_uma(angular_spread="none", per_ray_prune_db=40.0))


def test_option_changes_the_run_and_is_reproducible():
    sc = _uma(angular_spread="per_ray")
    assert sc.to_dict()["radio"]["beams"]["angular_spread"] == "per_ray"
    a = _runs(sc)
    assert a != _runs(_uma()) and a != _runs(_uma(angular_spread="tr38901")) and a == _runs(sc)


def test_validation():
    with pytest.raises(ConfigError, match="angular_spread"):
        _uma(angular_spread="rays")
    with pytest.raises(ConfigError, match="per_ray_prune_db"):
        _uma(angular_spread="per_ray", per_ray_prune_db=0.0)
    with pytest.raises(ConfigError, match="uma or umi_street_canyon"):
        hl.builtin_scenario("highway-tr37885-30ghz").with_overrides(
            {"radio.beams": dict(BEAMS, angular_spread="per_ray"), "radio.pathloss": "rma"})
    with pytest.raises(ConfigError, match="isotropic UE"):
        _uma(angular_spread="per_ray", ue_panels=1)
    assert _uma(angular_spread="per_ray", per_ray_prune_db=None).radio.beams.per_ray_prune_db is None


# ---------------------------------------------------------------------------------------------- tables
def test_table_values():
    p = pr.link_params("uma", 4.0, "nlos")
    assert (p["N"], p["r_tau"], p["zeta"], p["c_asd"], p["c_phi"], p["c_theta"]) == (20, 2.3, 3.0, 1.8, 1.289, 1.178)
    assert p["D"]["C"] == 50.0 and p["D"]["ASD"] == 50.0
    p = pr.link_params("uma", 4.0, "los")
    assert (p["N"], p["k"], p["c_asd"], p["D"]["C"], p["D"]["K"]) == (12, (9.0, 3.5), 3.58, 40.0, 12.0)
    p = pr.link_params("umi_street_canyon", 28.0, "nlos")
    assert (p["N"], p["r_tau"], p["c_asd"], p["c_phi"], p["c_theta"], p["D"]["C"]) == (19, 2.1, 10.0, 1.273, 1.184,
                                                                                       15.0)
    f = math.log10(29.0)
    assert p["asd"] == pytest.approx((-0.24 * f + 1.54, 0.10 * f + 0.33))
    p = pr.link_params("umi_street_canyon", 28.0, "los")
    assert p["k"] == (9.0, 5.0) and p["D"]["C"] == 12.0
    assert pr.link_params("uma", 4.0, "o2i")["asd"] == (0.58, 0.7)
    for pl in ("uma", "umi_street_canyon"):
        for st in ("los", "nlos", "o2i"):
            L = pr.link_params(pl, 3.5, st)["chol"]       # positive definite (Cholesky exists), unit diagonal
            assert np.allclose(np.diag(L @ L.T), 1.0)
    with pytest.raises(ValueError):
        pr.link_params("rma", 4.0, "los")
    assert pr.ALPHA[0] == 0.0447 and pr.ALPHA[1] == -0.0447 and pr.ALPHA[19] == -2.1551
    assert sorted(np.concatenate(pr.SUB_CLUSTERS).tolist()) == list(range(20))


def test_cross_correlation_entries():
    L = pr.link_params("uma", 4.0, "los")["chol"]                  # order K, ASD, ZSD, ASA, ZSA
    C = L @ L.T
    assert C[1, 2] == pytest.approx(0.5) and C[0, 3] == pytest.approx(-0.2) and C[2, 3] == pytest.approx(-0.3)
    assert C[3, 4] == pytest.approx(0.4) and C[0, 1] == pytest.approx(0.0)
    L = pr.link_params("umi_street_canyon", 28.0, "nlos")["chol"]   # ASD, ZSD, ASA, ZSA
    C = L @ L.T
    assert C[0, 1] == pytest.approx(0.5) and C[0, 3] == pytest.approx(0.5) and C[2, 3] == pytest.approx(0.2)


# ---------------------------------------------------------------------------------------------- random numbers
def test_mixed_normals_are_standard_and_continuous():
    link = pr._comb(pr._U(123), np.arange(20000, dtype=pr._U))
    idx = np.arange(3, dtype=pr._U)
    for s in (0.0, 13.0, 49.9):
        z = pr.mixed_normals(link, 8, 50.0, np.full(len(link), s), idx)
        assert abs(z.mean()) < 0.03 and abs(z.std() - 1.0) < 0.03
    one = link[:1]
    at = [pr.mixed_normals(one, 8, 50.0, np.array([v]), idx)[0] for v in (49.999, 50.0, 50.001)]
    assert np.abs(at[0] - at[1]).max() < 1e-3 and np.abs(at[2] - at[1]).max() < 1e-3
    # the knot value itself at s = k D, the same normals whatever the batch
    a = pr.mixed_normals(link[:5], 8, 50.0, np.full(5, 100.0), idx)
    b = pr.mixed_normals(link[2:7], 8, 50.0, np.full(5, 100.0), idx)
    assert np.array_equal(a[2:], b[:3])
    # correlation over the distance: high at D / 10, low at 3 D
    z0 = pr.mixed_normals(link, 8, 50.0, np.zeros(len(link)), idx)[:, 0]
    assert np.corrcoef(z0, pr.mixed_normals(link, 8, 50.0, np.full(len(link), 5.0), idx)[:, 0])[0, 1] > 0.95
    assert abs(np.corrcoef(z0, pr.mixed_normals(link, 8, 50.0, np.full(len(link), 150.0), idx)[:, 0])[0, 1]) < 0.05


def test_coupling_is_a_permutation_within_sub_clusters():
    keys = np.random.default_rng(0).random((4, 3, 20))
    free, sub = pr.coupling_pair(keys)
    for perm in (free, sub):
        assert (np.sort(perm, axis=-1) == np.arange(20)).all()
    for r in pr.SUB_CLUSTERS:
        assert np.isin(sub[..., r], r).all()
    strongest = np.array([[True, False, True]] * 4)
    c = pr.coupling(keys, strongest)
    assert (c[:, 0] == sub[:, 0]).all() and (c[:, 1] == free[:, 1]).all()


# ---------------------------------------------------------------------------------------------- the procedure
def _clusters(state="nlos", E=6, seed=0, arrival=False, pathloss="uma", fc=4.0, lsp=None):
    rng = np.random.default_rng(seed)
    p = pr.link_params(pathloss, fc, state)
    los = state == "los"
    n_lsp = len(p["names"]) if arrival else len([n for n in p["names"] if n not in ("ASA", "ZSA")])
    d = rng.uniform(30.0, 400.0, E)
    mz, sz = pr._lg_zsd(pathloss, los, d, 1.5, 25.0)
    off = np.zeros(E) if los else pr.zod_offset_deg(pathloss, d, 1.5, fc)
    th = 90.0 + np.degrees(np.arctan2(23.5, d))
    return pr.generate_clusters(p, rng.standard_normal((E, n_lsp)),
                                rng.standard_normal((E, p["N"], pr.N_CVAR if arrival else pr.N_CVAR_DEP)),
                                rng.random((E, p["N"], 4)), rng.random((E, p["N"], 20)), rng.uniform(-180, 180, E),
                                th, np.broadcast_to(mz, (E,)), sz, off, los, arrival, 180.0 - th, lsp)


def test_cluster_powers_and_los_anchor():
    cl = _clusters("los", arrival=True)
    E = cl["theta"].shape[0]
    total = cl["ray_power"].sum(-1) * 20 + cl["los_power"]
    assert np.all(total <= 1.0 + 1e-12) and np.all(total > 0.99)
    # Eq. 7.5-12 / 7.5-17: the first cluster (largest power share in angle) sits at the LOS direction
    first_phi = np.isclose(cl["phi"], cl["phi_los"][:, None], atol=1e-9).any(-1)
    first_th = np.isclose(cl["theta"], cl["theta_los"][:, None], atol=1e-9).any(-1)
    assert first_phi.all() and first_th.all() and E == 6
    assert np.isclose(cl["aoa"], cl["aoa_los"][:, None], atol=1e-9).any(-1).all()
    cl = _clusters("nlos")
    pn = cl["ray_power"] * 20
    kept = pn > 0
    assert np.all(pn[kept] >= pn.max(-1, keepdims=True).repeat(20, -1)[kept] * 10 ** -2.5 * (1 - 1e-12))
    assert np.all(pn.sum(-1) <= 1.0 + 1e-12)


def test_ray_directions():
    cl = _clusters("los")
    th, ph, pw = pr.ray_directions(cl)
    assert th.shape == ph.shape == pw.shape == (6, 1 + 12 * 20)
    assert np.array_equal(th[:, 0], cl["theta_los"]) and np.array_equal(pw[:, 0], cl["los_power"])
    assert (th >= 0.0).all() and (th <= 180.0).all()
    assert pw[:, 1:].sum(-1) == pytest.approx(cl["ray_power"].sum(-1) * 20)


def test_fixed_lsp_hook_scales_the_spread():
    narrow = _clusters("nlos", E=400, lsp={"ASD": 2.0, "ZSD": 1.0})
    wide = _clusters("nlos", E=400, lsp={"ASD": 40.0, "ZSD": 1.0})

    def rms(cl):
        w = cl["ray_power"]
        d = (cl["phi"] - cl["phi"][:, :1] + 180.0) % 360.0 - 180.0
        return np.sqrt((w * d ** 2).sum(-1) / w.sum(-1)).mean()
    assert rms(wide) > 8 * rms(narrow)


def _ext(sectors=3, panel=(8, 8), n_ssb=8, backend="numpy", am=30.0, tilt=102.0):
    class L:
        pass
    L.beams = BeamConfig(sectors=sectors, sector_az0_deg=30.0, n_ssb=n_ssb, panel=tuple(panel), tilt_deg=tilt,
                         am_db=am, angular_spread="per_ray")
    L.radio = type("R", (), dict(pathloss="uma", carrier_ghz=4.0, bs_height_m=25.0))
    L.sectors = sectors
    L.boresight = (30.0 + np.arange(sectors) * 360.0 / sectors) % 360.0
    L.beam_az = beam_azimuths_deg(n_ssb, 360.0 / sectors)
    return pr.PerRay(1, L, 1.5, backend=backend)


@pytest.mark.parametrize("sectors", [1, 3, 4])
@pytest.mark.parametrize("panel,n_ssb", [((8, 8), 8), ((10, 1), 1), ((4, 8), 8)])
def test_single_direction_is_the_geometric_gain(sectors, panel, n_ssb):
    """All rays in one direction: the per-ray gain is beam_gain_db of the antenna module (single-precision
    phases: within 0.002 dB where the gain is above -30 dB)."""
    x = _ext(sectors, panel, n_ssb)
    rng = np.random.default_rng(3)
    E, N = 40, 1
    th = rng.uniform(91.0, 120.0, (E, N))
    ph = rng.uniform(-180.0, 180.0, (E, N))
    cl = dict(theta=th, phi=ph, ray_power=np.full((E, N), 1.0 / 20), perm=np.tile(np.arange(20), (E, N, 1)),
              dtheta=np.zeros((E, 20)), dphi=np.zeros(20), los=False, theta_los=th[:, 0], phi_los=ph[:, 0])
    g = x.cluster_gains(cl, np.ones((E, sectors), dtype=bool))
    for k in range(sectors):
        ref = beam_gain_db(th[:, 0], ((ph[:, 0] - x.boresight[k] + 180.0) % 360.0) - 180.0, x.beam_az, 102.0,
                           panel[0], panel[1])
        got = 10 * np.log10(np.maximum(g[:, k], 1e-30))
        ok = ref > ref.max(-1, keepdims=True) - 30.0
        assert np.abs(got - ref)[ok].max() < 0.002


def test_spread_lowers_the_best_beam():
    """NLOS clusters of the 8 x 8 panel: the best beam loses several dB against the geometric gain (TR 38.901
    clause 7.5; the A6.1 Monte Carlo gave a median of 5.85 dB)."""
    x = _ext()
    cl = _clusters("nlos", E=300, seed=4)
    g = x.cluster_gains(cl, np.ones((300, 3), dtype=bool))
    rel = (cl["phi_los"][:, None] - x.boresight[None, :] + 180.0) % 360.0 - 180.0
    geo = 10 ** (beam_gain_db(np.repeat(cl["theta_los"][:, None], 3, 1), rel, x.beam_az, 102.0, 8, 8) / 10)
    loss = 10 * np.log10(geo.max(-1).max(-1) / g.max(-1).max(-1))
    assert 2.0 < np.median(loss) < 12.0


# ---------------------------------------------------------------------------------------------- loops == NumPy
def _kernel_sets():
    out = [pytest.param("python", id="python")]
    if pk.numba is not None:
        out.append(pytest.param("numba", id="numba"))
    return out


@pytest.mark.parametrize("kind", _kernel_sets())
@pytest.mark.parametrize("state", ["los", "nlos"])
@pytest.mark.parametrize("sectors,panel,n_ssb", [(3, (8, 8), 8), (1, (10, 1), 1), (3, (4, 8), 8), (4, (8, 8), 4),
                                                 (1, (8, 8), 1)])
def test_loops_equal_numpy_on_random_inputs(kind, state, sectors, panel, n_ssb):
    E = 3 if kind == "python" else 25
    cl = _clusters(state, E=E, seed=sectors + panel[0])
    if kind == "python":                                       # a few clusters keep the plain loops short
        for k in ("theta", "phi", "ray_power", "perm"):
            cl[k] = cl[k][:, :2]
    ref_x = _ext(sectors, panel, n_ssb)
    x = _ext(sectors, panel, n_ssb)
    x.kern = pk.kernels() if kind == "numba" else pk.python_kernels()
    keep = np.random.default_rng(1).random((E, sectors)) < 0.8
    keep[0] = True
    cl["ray_power"][0, 0] = 0.0                                 # a removed cluster: its rays add nothing
    a, b = ref_x.cluster_gains(cl, keep), x.cluster_gains(cl, keep)
    assert np.array_equal(a, b)
    assert (a[~keep] == 0.0).all() and (a[keep] >= 0.0).all()


@pytest.mark.parametrize("kind", _kernel_sets())
def test_loops_on_wrap_edges(kind):
    """Zenith offsets across 0 and 180 deg and beyond 360, azimuths beyond +-540 deg: the same values as NumPy."""
    cl = _clusters("nlos", E=4, seed=9)
    for k in ("theta", "phi", "ray_power", "perm"):
        cl[k] = cl[k][:, :3]
    cl["theta"][:] = [[-1.0, 179.5, 359.0], [-200.0, 0.2, 181.0], [400.0, -0.1, 90.0], [720.5, -365.0, 180.0]]
    cl["phi"][:] = [[-600.0, 539.9, 0.0], [179.99, -180.0, 900.0], [-1e-14, 360.0, 720.0], [-720.0, 1e-14, -359.9]]
    cl["dtheta"][:] = cl["dtheta"] * 50.0
    x, y = _ext(), _ext()
    y.kern = pk.kernels() if kind == "numba" else pk.python_kernels()
    keep = np.ones((4, 3), dtype=bool)
    assert np.array_equal(x.cluster_gains(cl, keep), y.cluster_gains(cl, keep))


def test_numba_backend_without_numba_uses_numpy(monkeypatch):
    monkeypatch.setattr(pk, "numba", None)
    assert pk.kernels() is None
    assert _ext(backend="numba").kern is None


@pytest.mark.parametrize("sc", [
    pytest.param(lambda: _uma(angular_spread="per_ray"), id="U"),
    pytest.param(lambda: _f(**{"radio.blockage": "a"}), id="F-blockage"),
    pytest.param(lambda: _f(**{"radio.blockage": "a", "radio.blockage_mode": "landscape"}).with_overrides(TINY),
                 id="F-landscape"),
    pytest.param(lambda: _uma(angular_spread="per_ray", per_ray_prune_db=None).with_overrides(TINY), id="U-noprune"),
])
def test_numba_backend_runs_equal_numpy(monkeypatch, sc):
    pytest.importorskip("numba")
    sc = sc()
    ref = _runs(sc)
    calls = []
    kern = pk.kernels()

    def spy(*a):
        calls.append(1)
        return kern[0](*a)
    monkeypatch.setattr(pr, "kernels", lambda: (spy, kern[1], kern[2]))
    assert _runs(sc.with_overrides({"run.backend": "numba"})) == ref
    assert calls                                                # the compiled loops ran


def test_loop_logic_in_a_run_without_numba(monkeypatch):
    """The loops as plain Python in a whole run: the same fingerprints and metrics as the NumPy path."""
    sc = _uma(angular_spread="per_ray").with_overrides({"mobility.users": 2, "run.duration_s": 0.4,
                                                         "run.warmup_s": 0.1})
    ref = _runs(sc)
    init = pr.PerRay.__init__
    used = []

    def python_init(self, *a, **kw):
        init(self, *a, **kw)
        self.kern = pk.python_kernels()
        used.append(1)
    monkeypatch.setattr(pr.PerRay, "__init__", python_init)
    assert _runs(sc) == ref and used


# ---------------------------------------------------------------------------------------------- invariance
def test_invariant_to_chunks_and_blocks(monkeypatch):
    sc = _uma(angular_spread="per_ray").with_overrides(TINY)
    ref = _runs(sc)
    assert _runs(sc, chunk_steps=120) == ref
    monkeypatch.setattr(pr, "ENTRY_BLOCK", 29)
    assert _runs(sc) == ref


def test_shared_radio():
    """Variants that differ only in engine keys share the per-ray samples: the same results as separate runs."""
    a = _uma(angular_spread="per_ray").with_overrides(TINY)
    b = _uma(angular_spread="per_ray", bfd=False).with_overrides(TINY)
    seed = 5
    worlds = [hl.build_world(sc, seed) for sc in (a, b)]
    shared = run_shared(worlds, [RULES, RULES])
    for sc, got in zip((a, b), shared):
        alone = hl.run_world(hl.build_world(sc, seed), RULES)
        assert [(r.fingerprint, json.dumps(r.metrics, sort_keys=True)) for r in got] == \
            [(r.fingerprint, json.dumps(r.metrics, sort_keys=True)) for r in alone]


def test_blockage_moves_into_the_beam_gains():
    """With per_ray the site gains carry no blockage factor (each cluster is attenuated instead)."""
    sc = _f(**{"radio.blockage": "a"}).with_overrides(TINY)
    src = ExtendedSource(hl.build_world(sc, 3))
    assert all(s.per_ray for s in src.sources) and src.sources[0].blockage is not None
    ch = next(src.chunks())
    assert src.sources[0].chunk_blk is not None and np.isfinite(ch.bg).all()
    ref = ExtendedSource(hl.build_world(_f().with_overrides(TINY), 3))
    ch0 = next(ref.chunks())
    assert np.array_equal(ch.site_db, ch0.site_db)              # the same site gains as without blockage


def test_pruned_pairs_keep_the_geometric_gain():
    sc = _uma(angular_spread="per_ray", per_ray_prune_db=10.0).with_overrides(TINY)
    w = hl.build_world(sc, 3)
    ch = next(ExtendedSource(w).chunks())
    geo = next(ExtendedSource(hl.build_world(_uma().with_overrides(TINY), 3)).chunks())
    same = (ch.bg == geo.bg).all(-1)
    assert same.any() and (~same).any()
