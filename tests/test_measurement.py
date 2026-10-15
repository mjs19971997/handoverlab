# SPDX-License-Identifier: MIT
"""L3 filter and the trigger conditions of A3 and conditional handover."""
import numpy as np
import pytest

from handoverlab.measurement import (INF, L3Filter, a3_condition, held_for, l3_coefficient, select_prepared_set,
                                     ttt_expires_before, update_entry_times)


# ---------------------------------------------------------------- L3 filter
def test_l3_coefficient_reference_period():
    # TS 38.331: a = 1 / 2^(k/4); k = 4 -> 0.5 at the 200 ms reference period
    assert l3_coefficient(4, 0.2) == pytest.approx(0.5)
    assert l3_coefficient(8, 0.2) == pytest.approx(0.25)
    assert l3_coefficient(0, 0.04) == pytest.approx(1.0)       # k = 0: no filtering


def test_l3_coefficient_keeps_time_constant():
    # five 40 ms samples must decay like one 200 ms sample
    a = l3_coefficient(4, 0.04)
    assert (1.0 - a) ** 5 == pytest.approx(0.5)


def test_l3_filter_first_sample_and_step_response():
    f = L3Filter(k=4, sample_period_s=0.2)
    assert f.update(np.array([-80.0])) == pytest.approx([-80.0])      # F_0 = first sample
    out = [float(f.update(np.array([-70.0]))[0]) for _ in range(3)]
    assert out == pytest.approx([-75.0, -72.5, -71.25])


def test_l3_filter_is_elementwise():
    f = L3Filter(k=4, sample_period_s=0.2)
    f.update(np.array([[0.0, 10.0]]))
    assert f.update(np.array([[10.0, 10.0]])) == pytest.approx(np.array([[5.0, 10.0]]))


# ---------------------------------------------------------------- A3 trigger
def test_a3_condition_strict_and_excludes_serving():
    gap = np.array([[0.0, 3.0, 3.5], [-1.0, 0.0, 10.0]])
    serving = np.array([0, 1])
    cond = a3_condition(gap.copy(), 3.0, serving, np.array([True, True]))
    assert cond.tolist() == [[False, False, True], [False, False, True]]
    cond = a3_condition(np.array([[5.0, 0.0]]), -10.0, np.array([1]), np.array([True]))
    assert cond.tolist() == [[True, False]]                          # serving never triggers


def test_a3_condition_only_connected_users():
    gap = np.array([[0.0, 9.0], [0.0, 9.0]])
    cond = a3_condition(gap, 3.0, np.array([0, 0]), np.array([True, False]))
    assert cond.tolist() == [[False, True], [False, False]]


def test_a3_condition_per_neighbour_offset():
    gap = np.array([[0.0, 4.0, 4.0]])
    off = np.array([[0.0, 3.0, 5.0]])
    assert a3_condition(gap, off, np.array([0]), np.array([True])).tolist() == [[False, True, False]]


def test_entry_times_keep_first_instant_and_reset():
    te = np.full((1, 2), INF)
    te = update_entry_times(te, np.array([[False, True]]), 1.00)
    te = update_entry_times(te, np.array([[False, True]]), 1.04)
    assert te.tolist() == [[INF, 1.00]]
    te = update_entry_times(te, np.array([[False, False]]), 1.08)      # condition left: timer stops
    assert te.tolist() == [[INF, INF]]


def test_time_to_trigger_expiry_between_measurements():
    te = np.array([[INF, 1.00]])
    # TTT 0.16 s, measurements every 40 ms: expiry at 1.16 falls on the instant t = 1.16
    assert not ttt_expires_before(te, 0.16, 1.12, 0.04).any()
    assert ttt_expires_before(te, 0.16, 1.16, 0.04)[0, 1]
    # TTT 0.10 s expires between 1.08 and 1.12 -> reported at the instant 1.08 (report time te + ttt)
    assert not ttt_expires_before(te, 0.10, 1.04, 0.04).any()
    assert ttt_expires_before(te, 0.10, 1.08, 0.04)[0, 1]


def test_time_to_trigger_per_user():
    te = np.array([[INF, 1.0], [INF, 1.0]])
    ready = ttt_expires_before(te, np.array([0.0, 0.32]), 1.0, 0.04)
    assert ready[:, 1].tolist() == [True, False]


# ---------------------------------------------------------------- CHO trigger
def test_held_for():
    tx = np.array([[INF, 2.00, 2.04]])
    assert held_for(tx, 2.08, 0.08).tolist() == [[False, True, False]]
    assert held_for(tx, 2.08, 0.0).tolist() == [[False, True, True]]


def _select(score, reported, have, n_max=4, hys=3.0, stick=1.0, serving=0):
    U = score.shape[0]
    return select_prepared_set(np.asarray(score, float), np.asarray(reported), np.asarray(have),
                               np.ones(U, bool), np.full(U, serving), n_max, hys, stick)


def test_cho_preparation_threshold_and_serving():
    score = np.array([[9.0, 0.0, -0.5, 2.0]])
    rep = np.array([[True, True, True, True]])
    have = np.zeros((1, 4), bool)
    assert _select(score, rep, have).tolist() == [[False, True, False, True]]


def test_cho_unreported_cell_not_prepared():
    score = np.array([[0.0, 5.0]])
    assert not _select(score, np.array([[False, False]]), np.zeros((1, 2), bool)).any()


def test_cho_release_hysteresis_keeps_prepared_cell():
    score = np.array([[0.0, -2.0, -4.0]])
    have = np.array([[False, True, True]])
    rep = np.zeros((1, 3), bool)
    # held cells stay down to -3 dB, then they are released
    assert _select(score, rep, have).tolist() == [[False, True, False]]


def test_cho_prepared_set_limited_to_n_max():
    score = np.array([[0.0, 1.0, 5.0, 3.0, 2.0]])
    rep = np.ones((1, 5), bool)
    have = np.zeros((1, 5), bool)
    assert _select(score, rep, have, n_max=2).tolist() == [[False, False, True, True, False]]


def test_cho_stick_bonus_prefers_held_cell():
    score = np.array([[0.0, 2.5, 3.0]])
    rep = np.ones((1, 3), bool)
    have = np.array([[False, True, False]])
    # with n_max = 1 the held cell (2.5 + 1.0 bonus) beats the new one (3.0)
    assert _select(score, rep, have, n_max=1).tolist() == [[False, True, False]]
    assert _select(score, rep, have, n_max=1, stick=0.0).tolist() == [[False, False, True]]
