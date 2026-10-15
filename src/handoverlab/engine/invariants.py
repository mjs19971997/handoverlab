# SPDX-License-Identifier: MIT
"""Invariant checks of the protocol engine.

Two levels:

* **End of every run** (always on, cheap): attempts equal the sum of the
  outcomes; failures equal the sum of the causes; every attempt that was ever
  started got exactly one outcome; for conditional handover every requested
  preparation ended as lost, cancelled, used, unused or still open.
* **Debug mode** (``debug=True`` in :func:`handoverlab.simulate` and
  :class:`~handoverlab.engine.Engine`, ``handoverlab run --debug`` or the
  environment variable ``HANDOVERLAB_DEBUG=1``): additionally, at every step
  and measurement instant, the state of every user is consistent (valid
  serving cell and state, T310 only while connected, an attempt never targets
  the serving cell, an execution always belongs to an attempt), radio
  quantities are finite, outcomes and event-log times are in order, the
  values a rule returns have valid shapes and no NaN, and the observation
  given to a rule is read-only (a rule that writes into it fails at once).

Debug mode changes no result; it only costs time (it roughly doubles the run time).
A violation raises :class:`InvariantError` with the time, the user and the
rule.
"""
from __future__ import annotations

import os

import numpy as np

CONNECTED, EXECUTING, REESTABLISHING = 0, 1, 2


class InvariantError(RuntimeError):
    """An internal consistency check of the engine failed."""


def debug_from_env() -> bool:
    """True if the environment variable ``HANDOVERLAB_DEBUG`` asks for debug mode."""
    return os.environ.get("HANDOVERLAB_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


def _fail(eng, t, msg, users=None):
    where = ""
    if users is not None:
        users = np.atleast_1d(users)
        where = " (users %s)" % ", ".join(str(int(u)) for u in users[:5])
    raise InvariantError("invariant violated at t = %.4f s, rule %r: %s%s" % (t, eng.rule.name, msg, where))


def check_step(eng, t: float, sinr: np.ndarray) -> None:
    """State of all users after the link monitoring and procedure events of one step."""
    state, serv, M = eng.state, eng.serv, eng.M
    bad = (state < CONNECTED) | (state > REESTABLISHING)
    if bad.any():
        _fail(eng, t, "unknown connection state", np.nonzero(bad)[0])
    bad = (serv < 0) | (serv >= M)
    if bad.any():
        _fail(eng, t, "serving cell out of range", np.nonzero(bad)[0])
    bad = eng.run & (state != CONNECTED)
    if bad.any():
        _fail(eng, t, "T310 running for a user that is not connected", np.nonzero(bad)[0])
    bad = (state == EXECUTING) & ~eng.f_on
    if bad.any():
        _fail(eng, t, "execution without an attempt", np.nonzero(bad)[0])
    f = eng.f_on
    bad = f & ((eng.f_tgt == eng.f_src) | (eng.f_src != serv) | (eng.f_tgt < 0) | (eng.f_tgt >= M))
    if bad.any():
        _fail(eng, t, "attempt towards the serving cell, from a cell other than the serving cell, or to no cell",
              np.nonzero(bad)[0])
    bad = eng.w_on & (eng.w_src == eng.w_tgt)
    if bad.any():
        _fail(eng, t, "evaluation window of a handover to the same cell", np.nonzero(bad)[0])
    con = state == CONNECTED
    if not np.all(np.isfinite(sinr[con])) or np.any(sinr[con] < 0):
        _fail(eng, t, "serving SINR not finite or negative", np.nonzero(con & ~(np.isfinite(sinr) & (sinr >= 0)))[0])
    if not (np.all(np.isfinite(eng.qo)) and np.all(np.isfinite(eng.qi))):
        _fail(eng, t, "radio-link monitoring state not finite")
    _check_labels(eng, t)


def _check_labels(eng, t):
    C = eng.C
    open_ = int(np.count_nonzero(eng.f_on)) + int(np.count_nonzero(eng.w_on))
    if C["att_all"] != C["closed_all"] + open_:
        _fail(eng, t, "attempts started (%d) != outcomes given (%d) + attempts open (%d)"
              % (C["att_all"], C["closed_all"], open_))


def check_new_attempt(eng, u, tgt, t) -> None:
    if tgt == eng.serv[u] or not 0 <= tgt < eng.M:
        _fail(eng, t, "attempt towards cell %d, serving cell %d" % (tgt, eng.serv[u]), u)


def check_event(eng, row) -> None:
    """Times of a new event-log row: in log order and t_attempt <= t_exec <= t_end."""
    t_att, t_x, t_end = row[0], row[1], row[2]
    slack = eng.mdt + 1e-6                     # a report may be dated up to one measurement period ahead
    if t_end < eng.last_t_end - 1e-9:
        _fail(eng, t_end, "event-log time %.4f before the previous one %.4f" % (t_end, eng.last_t_end), row[3])
    if t_att > t_end + slack or (t_x != -1.0 and not (t_att - slack <= t_x <= t_end + 1e-9)):
        _fail(eng, t_end, "event times out of order: attempt %.4f, execution %.4f, end %.4f" % (t_att, t_x, t_end),
              row[3])
    eng.last_t_end = t_end


def check_rule_value(eng, hook, value, t, per_cell=True) -> None:
    """Value returned by a rule hook: a number, (U, M) if ``per_cell`` else (U,); no NaN."""
    a = np.asarray(value, dtype=float)
    shapes = [(), (eng.U, eng.M) if per_cell else (eng.U,)]
    if a.shape not in shapes:
        _fail(eng, t, "%s of rule %r returned shape %s; expected a number or %s"
              % (hook, eng.rule.name, a.shape, shapes[1]))
    if np.isnan(a).any():
        _fail(eng, t, "%s of rule %r returned NaN" % (hook, eng.rule.name))
    if hook == "time_to_trigger" and (a < 0).any():
        _fail(eng, t, "time_to_trigger of rule %r returned a negative value" % eng.rule.name)


def readonly_copy(a: np.ndarray) -> np.ndarray:
    b = np.array(a, copy=True)
    b.setflags(write=False)
    return b


def check_final(eng) -> None:
    """Conservation checks at the end of a run (always done)."""
    from .metrics import CAUSES, OUTCOMES
    C = eng.C
    T = eng.S * eng.dt
    if C["att"] != sum(C["n_" + o] for o in OUTCOMES):
        _fail(eng, T, "attempts (%d) != sum of outcomes (%d)" % (C["att"], sum(C["n_" + o] for o in OUTCOMES)))
    if C["fail"] != sum(C["f_" + c] for c in CAUSES):
        _fail(eng, T, "failures (%d) != sum of causes (%d)" % (C["fail"], sum(C["f_" + c] for c in CAUSES)))
    if C["att_all"] != C["closed_all"]:
        _fail(eng, T, "attempts started (%d) != outcomes given (%d)" % (C["att_all"], C["closed_all"]))
    left = eng.proc.open_preparations()
    used = C["prep_lost_all"] + C["prep_cancel_all"] + C["prep_used_all"] + C["prep_wasted_all"] + left
    if C["prep_req_all"] != used:
        _fail(eng, T, "preparations requested (%d) != lost %d + cancelled %d + used %d + unused %d + open %d"
              % (C["prep_req_all"], C["prep_lost_all"], C["prep_cancel_all"], C["prep_used_all"],
                 C["prep_wasted_all"], left))
