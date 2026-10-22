# SPDX-License-Identifier: MIT
"""Value domains of the RRC parameters that HandoverLab exposes, from TS 38.331 V18.11.0 (since 2.1.0).

Every value set below was read from the ASN.1 and the field descriptions of the official TS 38.331 V18.11.0
(ETSI TS 138 331 V18.11.0, 2026-09); the page is the page of that PDF.

==========================  ======================================================================  =========
quantity                    TS 38.331 V18.11.0                                                      PDF page
==========================  ======================================================================  =========
time-to-trigger             TimeToTrigger ENUMERATED {ms0, ms40, ms64, ..., ms5120}                 1159
hysteresis                  Hysteresis INTEGER (0..30), actual value field value * 0.5 dB           811
A3 offset                   MeasTriggerQuantityOffset INTEGER (-30..30), field value * 0.5 dB       1043, 1045
cell individual offset      Q-OffsetRange ENUMERATED {dB-24, dB-22, ..., dB24}                     995
L3 filter coefficient       FilterCoefficient ENUMERATED {fc0 .. fc9, fc11, fc13, fc15, fc17, fc19}  801
report interval             ReportInterval ENUMERATED {ms120, ..., min30}                            1053
T310, N310, N311            RLF-TimersAndConstants                                                   1059
T304                        ReconfigurationWithSync t304 ENUMERATED {ms50, ..., ms10000}             701
SSB periodicity             ssb-periodicityServingCell ENUMERATED {ms5 .. ms160}                    1100
RSRP thresholds             RSRP-Range INTEGER (0..127), actual value (IE value - 156) dBm          1060
CHO candidates              maxNrofCondCells-r16 INTEGER ::= 8                                       1485
D1/D2 distance thresholds   distanceThreshFromReference1/2 INTEGER (0..65535), each step 50 m       1039, 1045
location hysteresis         HysteresisLocation INTEGER (0..32768), field value * 10 m               811-812
==========================  ======================================================================  =========

HandoverLab's A3 offsets (``off_db``, ``o_exec_db``, ``o_prep_db``, ...) are the sum a3-Offset + Hysteresis of
Event A3 (``off_db = Off + Hys``, TS 38.331 5.5.4.4 with Ofn = Ocn = Ofp = Ocp = 0), so they lie on a 0.5 dB grid
in [-15, 30] dB.  The values of LTM cell switches and of the preparation and command delays are network
decisions with no RRC value set; they are not checked.

:func:`check_rule` and :func:`check_scenario` list every value outside these sets; ``handoverlab verify``
(group ``values``) applies them to the built-in cards and rules, and a study refuses grid values outside them
(gate ``standard_values``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

SOURCE = "TS 38.331 V18.11.0"
TIME_TO_TRIGGER_S = (0.0, 0.04, 0.064, 0.08, 0.1, 0.128, 0.16, 0.256, 0.32, 0.48, 0.512, 0.64, 1.024, 1.28, 2.56,
                     5.12)
Q_OFFSET_RANGE_DB = (-24, -22, -20, -18, -16, -14, -12, -10, -8, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 8, 10,
                     12, 14, 16, 18, 20, 22, 24)
FILTER_COEFFICIENTS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 15, 17, 19)
REPORT_INTERVAL_S = (0.12, 0.24, 0.48, 0.64, 1.024, 2.048, 5.12, 10.24, 20.48, 40.96, 60.0, 360.0, 720.0, 1800.0)
T310_S = (0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 6.0)
N310 = (1, 2, 3, 4, 6, 8, 10, 20)
N311 = (1, 2, 3, 4, 5, 6, 8, 10)
T304_S = (0.05, 0.1, 0.15, 0.2, 0.5, 1.0, 2.0, 10.0)
SSB_PERIOD_S = (0.005, 0.01, 0.02, 0.04, 0.08, 0.16)
MAX_COND_CELLS = 8
A3_SUM_RANGE_DB = (-15.0, 30.0)        # a3-Offset (-15..15 dB) + Hysteresis (0..15 dB), both in 0.5 dB steps
RSRP_THRESHOLD_DBM = (-156, -30)       # RSRP-Range 0..126 (127 is a special value)
D_THRESH_STEP_M, D_THRESH_MAX_M = 50.0, 65535 * 50.0
HYS_LOCATION_STEP_M, HYS_LOCATION_MAX_M = 10.0, 32768 * 10.0

#: rule parameter -> kind of value domain
RULE_DOMAINS: Dict[str, Dict[str, str]] = {
    "a3": {"off_db": "a3sum", "ttt_s": "ttt"},
    "a3_mro": {"off_db": "a3sum", "ttt_s": "ttt", "step_db": "cio_walk"},
    "a3_bandit": {"arms_db": "a3sum", "ttt_s": "ttt"},
    "dqn": {"offsets_db": "a3sum", "ttt_s": "ttt"},
    "a3a5": {"off_db": "a3sum", "ttt_s": "ttt", "a5_thresh1_dbm": "rsrp", "a5_thresh2_dbm": "rsrp", "a5_hys_db": "hys",
             "a5_ttt_s": "ttt", "a5_down_thresh1_dbm": "rsrp", "a5_down_thresh2_dbm": "rsrp"},
    "daps": {"off_db": "a3sum", "ttt_s": "ttt"},
    "cho": {"o_prep_db": "a3sum", "o_exec_db": "a3sum", "ttt_exec_s": "ttt", "ttt_prep_s": "ttt", "n_max": "ncond"},
    "cho_d2": {"o_prep_db": "a3sum", "o_exec_db": "a3sum", "ttt_exec_s": "ttt", "ttt_prep_s": "ttt",
               "n_max": "ncond", "d_thresh1_m": "d_thresh", "d_thresh2_m": "d_thresh", "hys_m": "hys_loc",
               "ttt_d2_s": "ttt"},
    "ltm": {"o_prep_db": "a3sum", "n_max": "ncond"},
    "cltm": {"o_prep_db": "a3sum", "n_max": "ncond"},
}
PROTOCOL_DOMAINS = {"l3_k": "filter", "report_interval_s": "report_interval", "t310_s": "t310", "n310": "n310",
                    "n311": "n311", "t304_s": "t304", "ssb_period_s": "ssb"}


@dataclass(frozen=True)
class Finding:
    """A value outside the domain that TS 38.331 allows."""
    where: str
    key: str
    value: Any
    allowed: str

    def __str__(self) -> str:
        return "%s: %s = %r is not a value of %s (%s)" % (self.where, self.key, self.value, SOURCE, self.allowed)


def _in(v: float, values: Iterable[float]) -> bool:
    return any(abs(float(v) - x) < 1e-9 for x in values)


def _on_grid(v: float, step: float, lo: float, hi: float) -> bool:
    k = float(v) / step
    return lo - 1e-9 <= float(v) <= hi + 1e-9 and abs(k - round(k)) < 1e-6


def _cio_walk_ok(step: float, lo: float, hi: float) -> bool:
    """Every offset reachable from 0 dB in steps of ``step`` within [lo, hi] is a Q-OffsetRange value."""
    if step <= 0:
        return True
    n = int(math.floor(max(abs(lo), abs(hi)) / step + 1e-9))
    vals = [k * step for k in range(-n, n + 1) if lo - 1e-9 <= k * step <= hi + 1e-9]
    return all(_in(v, Q_OFFSET_RANGE_DB) for v in vals)


def allowed(kind: str) -> str:
    """Text of the domain of a kind of value."""
    return {
        "ttt": "TimeToTrigger: %s s" % ", ".join("%g" % x for x in TIME_TO_TRIGGER_S),
        "a3sum": "a3-Offset + Hysteresis: a multiple of 0.5 dB in [-15, 30] dB",
        "hys": "Hysteresis: a multiple of 0.5 dB in [0, 15] dB",
        "cio": "Q-OffsetRange: %s dB" % ", ".join("%d" % x for x in Q_OFFSET_RANGE_DB),
        "cio_walk": "every offset reached in steps of step_db within [min_db, max_db] must be a Q-OffsetRange value",
        "rsrp": "RSRP-Range threshold: an integer dBm in [-156, -30]",
        "ncond": "maxNrofCondCells: 1 to 8",
        "d_thresh": "distanceThreshFromReference: a multiple of 50 m in [0, 3276750] m",
        "hys_loc": "HysteresisLocation: a multiple of 10 m in [0, 327680] m",
        "filter": "FilterCoefficient: k in %s" % (FILTER_COEFFICIENTS,),
        "report_interval": "ReportInterval: %s s" % ", ".join("%g" % x for x in REPORT_INTERVAL_S),
        "t310": "T310: %s s" % ", ".join("%g" % x for x in T310_S),
        "n310": "N310: %s" % (N310,),
        "n311": "N311: %s" % (N311,),
        "t304": "T304: %s s" % ", ".join("%g" % x for x in T304_S),
        "ssb": "ssb-periodicityServingCell: %s s" % ", ".join("%g" % x for x in SSB_PERIOD_S),
    }[kind]


def value_ok(kind: str, v: Any) -> bool:
    """True if ``v`` lies in the domain of ``kind`` (see :func:`allowed`)."""
    if v is None:
        return kind in ("t304", "rsrp")            # not configured: no value to check
    if isinstance(v, (list, tuple)):
        return all(value_ok(kind, x) for x in v)
    v = float(v)
    if kind == "ttt":
        return _in(v, TIME_TO_TRIGGER_S)
    if kind == "a3sum":
        return _on_grid(v, 0.5, *A3_SUM_RANGE_DB)
    if kind == "hys":
        return _on_grid(v, 0.5, 0.0, 15.0)
    if kind == "cio":
        return _in(v, Q_OFFSET_RANGE_DB)
    if kind == "rsrp":
        return _on_grid(v, 1.0, *RSRP_THRESHOLD_DBM)
    if kind == "ncond":
        return _on_grid(v, 1.0, 1, MAX_COND_CELLS)
    if kind == "d_thresh":
        return _on_grid(v, D_THRESH_STEP_M, 0.0, D_THRESH_MAX_M)
    if kind == "hys_loc":
        return _on_grid(v, HYS_LOCATION_STEP_M, 0.0, HYS_LOCATION_MAX_M)
    if kind == "filter":
        return _in(v, FILTER_COEFFICIENTS)
    if kind == "report_interval":
        return _in(v, REPORT_INTERVAL_S)
    if kind == "t310":
        return _in(v, T310_S)
    if kind == "n310":
        return _in(v, N310)
    if kind == "n311":
        return _in(v, N311)
    if kind == "t304":
        return _in(v, T304_S)
    if kind == "ssb":
        return _in(v, SSB_PERIOD_S)
    raise ValueError("unknown kind of value %r" % kind)


def check_rule(spec: Dict[str, Any], where: str = "") -> List[Finding]:
    """Values of a rule specification (``{"rule": ..., param: value}``) outside TS 38.331, with the rule's defaults."""
    from .rules import make_rule
    name = spec.get("rule")
    doms = RULE_DOMAINS.get(name, {})
    if not doms:
        return []
    params = dict(make_rule(spec).params())
    where = where or str(spec.get("name") or name)
    out = []
    for key, kind in doms.items():
        if key not in params:
            continue
        if kind == "cio_walk":
            if not _cio_walk_ok(float(params[key]), float(params["min_db"]), float(params["max_db"])):
                out.append(Finding(where, "step_db/min_db/max_db", (params[key], params["min_db"], params["max_db"]),
                                   allowed("cio_walk")))
            continue
        if not value_ok(kind, params[key]):
            out.append(Finding(where, key, params[key], allowed(kind)))
    return out


def check_scenario(scenario, where: str = "") -> List[Finding]:
    """Values of the protocol section of ``scenario`` outside TS 38.331."""
    where = where or scenario.name or "scenario"
    p = scenario.protocol
    return [Finding(where, "protocol." + key, getattr(p, key), allowed(kind)) for key, kind in PROTOCOL_DOMAINS.items()
            if not value_ok(kind, getattr(p, key))]


def domain_of(rule: str, param: str) -> Optional[str]:
    """Kind of value domain of a rule parameter, or None if TS 38.331 has none for it."""
    kind = RULE_DOMAINS.get(rule, {}).get(param)
    return None if kind == "cio_walk" else kind


def extend(kind: str, values: Sequence[float], side: str, steps: int) -> List[float]:
    """``steps`` values of the domain ``kind`` beyond the ``side`` end of ``values`` (grid extension of a study)."""
    vals = sorted(float(v) for v in values)
    if kind == "ttt":
        if side == "upper":
            nxt = [x for x in TIME_TO_TRIGGER_S if x > vals[-1] + 1e-9]
        else:
            nxt = [x for x in reversed(TIME_TO_TRIGGER_S) if x < vals[0] - 1e-9]
        return nxt[:steps]
    if kind == "a3sum" and len(vals) >= 2:
        step = max(0.5, round(abs(vals[-1] - vals[-2]) * 2) / 2)
        lo, hi = A3_SUM_RANGE_DB
        out = []
        for i in range(1, steps + 1):
            v = vals[-1] + step * i if side == "upper" else vals[0] - step * i
            if not lo - 1e-9 <= v <= hi + 1e-9 or (side == "lower" and vals[0] >= 0 > v):
                break
            out.append(round(v, 10))
        return out
    return []


__all__ = ["SOURCE", "TIME_TO_TRIGGER_S", "Q_OFFSET_RANGE_DB", "FILTER_COEFFICIENTS", "REPORT_INTERVAL_S", "T310_S",
           "N310", "N311", "T304_S", "SSB_PERIOD_S", "MAX_COND_CELLS", "RULE_DOMAINS", "PROTOCOL_DOMAINS", "Finding",
           "allowed", "value_ok", "check_rule", "check_scenario", "domain_of", "extend"]
