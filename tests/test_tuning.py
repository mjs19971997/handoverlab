# SPDX-License-Identifier: MIT
"""Equal-budget tuning: sampling of settings, the selection rule and the gates."""
import pytest

from handoverlab.studies.tuning import (MethodTuning, evaluate_gates, first_round, grid_size, refine,
                                        seed_overlap_gate, select, setting_key)

GRID = {"off_db": [0.0, 1.0, 2.0, 3.0, 4.0], "ttt_s": [0.0, 0.04, 0.08, 0.16]}


def test_first_round_is_seeded_and_without_repetition():
    a = first_round("A3", GRID, 8)
    assert a == first_round("A3", GRID, 8)
    assert a != first_round("CHO", GRID, 8)
    assert len({setting_key(c) for c in a}) == 8
    assert all(c["off_db"] in GRID["off_db"] and c["ttt_s"] in GRID["ttt_s"] for c in a)
    assert len(first_round("A3", {"x": [1, 2]}, 8)) == 2                   # never more than the grid


def test_refinement_steps_around_the_best_then_fills_the_budget():
    taken = [{"off_db": 2.0, "ttt_s": 0.04}]
    one = refine("A3", GRID, taken[0], taken, 4)
    assert len(one) == 4
    for c in one:                                                         # one grid step along one parameter
        steps = sum(GRID[k].index(c[k]) != GRID[k].index(taken[0][k]) for k in GRID)
        assert steps == 1
    many = refine("A3", GRID, taken[0], taken, 15)                         # more than the neighbourhood
    keys = {setting_key(c) for c in many}
    assert len(many) == 15 and len(keys) == 15 and setting_key(taken[0]) not in keys
    assert len(refine("A3", GRID, taken[0], taken, 100)) == grid_size(GRID) - 1


def cand(u, f, p=0.0):
    return {"unnecessary_pm": u, "failures_pm": f, "prepared_cells_mean": p}


def test_selection_rule():
    c = [cand(1.0, 0.1), cand(0.5, 0.3), cand(0.6, 0.2), cand(0.62, 0.15, 0.0), cand(0.61, 0.2, 0.5)]
    s = select(c, budget=0.2)
    # within budget: 0, 2, 3, 4; best unnecessary 0.6; within 5 %: 2 (0.6), 3 (0.62), 4 (0.61);
    # lowest preparation overhead: 2 and 3 (0.0); then lowest failure rate: 3
    assert (s.index, s.met_budget, s.n_meeting, s.n_near) == (3, True, 4, 3)
    assert select(c, budget=0.2, tolerance=0.0).index == 2
    s = select(c, budget=0.05)                                            # nothing meets the budget
    assert (s.index, s.met_budget) == (0, False)                          # the lowest failure rate
    assert select([cand(1.0, 0.1), cand(1.0, 0.1)], 1.0).index == 0      # order breaks the last tie


def tuning(name, cands, grid=None, nb=None, n=None):
    grid = grid or GRID
    m = MethodTuning(name, grid, nb or {}, n or len(cands), cands)
    return m


def full(setting, u, f, p=0.0):
    return dict(cand(u, f, p), setting=setting)


def run_gates(methods, budgets, ref_failures=50, policy=None, **kw):
    for m in methods:
        for b, v in budgets.items():
            m.selected[b] = select(m.candidates, v)
    pol = dict(grid_edge="block", budget_binding="warn", budget_met="warn", equal_budget="block",
               flat_optimum="warn")
    pol.update(policy or {})
    return {(g.gate, g.method, g.budget): g for g in evaluate_gates("g", methods, budgets, ref_failures, pol, **kw)}


def test_grid_edge_gate_and_natural_bounds():
    m = tuning("A3", [full({"off_db": 4.0, "ttt_s": 0.0}, 0.1, 0.1), full({"off_db": 2.0, "ttt_s": 0.04}, 0.5, 0.1)])
    g = run_gates([m], {"std": 0.2})[("grid_edge", "A3", "std")]
    assert not g.ok and g.blocking
    assert "off_db = 4 is the largest grid value" in g.message and "ttt_s = 0 is the smallest" in g.message
    m = tuning("A3", m.candidates, nb={"ttt_s": "lower"})
    g = run_gates([m], {"std": 0.2})[("grid_edge", "A3", "std")]
    assert "ttt_s" not in g.message and "off_db" in g.message
    m = tuning("A3", [full({"off_db": 2.0, "ttt_s": 0.04}, 0.1, 0.1)])
    assert run_gates([m], {"std": 0.2})[("grid_edge", "A3", "std")].ok
    m = tuning("A3", [full({"off_db": 4.0, "ttt_s": 0.04}, 0.1, 0.1)])
    gw = run_gates([m], {"std": 0.2}, policy={"grid_edge": "warn"})[("grid_edge", "A3", "std")]
    assert not gw.ok and not gw.blocking and gw.status == "warn"
    assert ("grid_edge", "A3", "std") not in run_gates([m], {"std": 0.2}, policy={"grid_edge": "off"})


def test_budget_binding_gate():
    loose = [full({"off_db": 2.0, "ttt_s": 0.04}, 0.1 * i, 0.01) for i in range(10)]
    g = run_gates([tuning("A3", loose)], {"std": 0.2})[("budget_binding", "", "std")]
    assert not g.ok and "of every method meet the budget" in g.message
    tight = loose[:5] + [full({"off_db": 2.0, "ttt_s": 0.04}, 0.1, 0.5) for _ in range(5)]
    assert run_gates([tuning("A3", tight)], {"std": 0.2})[("budget_binding", "", "std")].ok
    g = run_gates([tuning("A3", tight)], {"std": 0.2}, ref_failures=2)[("budget_binding", "", "std")]
    assert not g.ok and "only 2 failures" in g.message


def test_budget_met_equal_budget_and_flat_optimum_gates():
    a = tuning("A3", [full({"off_db": 2.0, "ttt_s": 0.04}, 0.1, 0.5), full({"off_db": 3.0, "ttt_s": 0.04}, 0.2, 0.6)])
    b = tuning("CHO", [full({"off_db": 2.0, "ttt_s": 0.04}, 0.1, 0.1)] * 3, n=3)
    g = run_gates([a, b], {"std": 0.2})
    assert not g[("budget_met", "A3", "std")].ok and g[("budget_met", "CHO", "std")].ok
    assert not g[("equal_budget", "", "")].ok and g[("equal_budget", "", "")].blocking
    assert "declared budgets differ" in g[("equal_budget", "", "")].message
    b = tuning("CHO", [full({"off_db": 2.0, "ttt_s": 0.04}, 0.1, 0.1)], n=2)         # one setting missing
    g = run_gates([a, b], {"std": 0.2})
    assert not g[("equal_budget", "", "")].ok and "CHO 1 of 2" in g[("equal_budget", "", "")].message
    small = {"off_db": [1.0, 2.0]}                                        # grid smaller than the budget
    c = tuning("CHO", [full({"off_db": 1.0}, 0.1, 0.1), full({"off_db": 2.0}, 0.1, 0.1)], grid=small, n=2)
    a2 = tuning("A3", a.candidates, n=2)
    assert run_gates([a2, c], {"std": 0.7})[("equal_budget", "", "")].ok
    flat = tuning("A3", [full({"off_db": 2.0, "ttt_s": 0.04}, 1.0 + 0.01 * i, 0.1) for i in range(4)])
    assert not run_gates([flat], {"std": 0.2})[("flat_optimum", "A3", "std")].ok


def test_seed_overlap_gate():
    g = seed_overlap_gate([1, 2, 3], [3, 4], "block")
    assert g.blocking and "3" in g.message
    assert seed_overlap_gate([1, 2], [3, 4], "block").ok


def test_gate_policy_off_hides_the_gate():
    m = tuning("A3", [full({"off_db": 4.0, "ttt_s": 0.0}, 0.1, 0.1)])
    gates = run_gates([m], {"std": 0.2}, policy={"flat_optimum": "off"})
    assert not any(k[0] == "flat_optimum" for k in gates)


@pytest.mark.parametrize("tolerance, idx", [(0.05, 1), (0.0, 0)])
def test_selection_uses_the_tolerance_and_the_tie_breaks(tolerance, idx):
    c = [cand(0.50, 0.12, 0.3), cand(0.51, 0.10, 0.3)]
    assert select(c, 0.15, tolerance).index == idx
