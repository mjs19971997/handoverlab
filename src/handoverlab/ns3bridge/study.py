# SPDX-License-Identifier: MIT
"""The ns-3 study file: what the bridge can run in both simulators, checked before anything is written.

A small YAML, TOML or JSON file with the keys ``schema``, ``name``, ``description`` and the section ``ns3``::

    schema: 1
    name: V1
    ns3:
      scenario: ns3-urban-3.5ghz          # the only card the ns-3 program reproduces
      rule: a3                            # the only rule of the program (stock NrA3RsrpHandoverAlgorithm)
      users: 20
      duration_s: 180                     # simulated time including the discarded prefix
      discard_s: 60
      conditions:                         # full factorial
        isd_m: [200, 300]                 # 200, 300 or 400 m (the site lists of handoverlab.verify.ns3)
        speed_mps: [10, 28]
        ttt_ms: [80, 320]
        offset_db: [3]                    # A3 offset (program option --hyst)
        traffic: [light]                  # light, mixed or full (mixed: export only)
        fading: [false]                   # TR 38.901 fast fading in ns-3; tdl-c in HandoverLab
      seeds: {first: 401, last: 405}      # ns-3 --rngRun and the HandoverLab seeds
      outputs: {events: true, ctrl_csv: false, meas_csv: false}
      handoverlab: {run_length: study}    # 'card' (150 s / 60 s) only reproduces the registered N3 and V1
                                          # analyses, which had the wrong run length; not for new comparisons
      build: {ns3_dir: ~/ns-3-dev, path: "", msys2: "C:/msys64"}

Everything else is refused with an error that names the option: another card or scenario changes
(``scenario: {base: ..., radio: {beams: ...}}``), another rule (CHO, DAPS, LTM, ...), another site
distance, unknown keys.
"""
from __future__ import annotations

import hashlib
import itertools
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ..config import ConfigError, read_file

SCHEMA = 1
CARD = "ns3-urban-3.5ghz"
ISDS = (200, 300, 400)                  # the site lists of handoverlab.verify.ns3 (and of the ns-3 program)
TRAFFIC = ("light", "mixed", "full")
RUN_LENGTHS = ("study", "card")
_TOP = ("schema", "name", "description", "ns3")
_NS3 = ("scenario", "rule", "users", "duration_s", "discard_s", "conditions", "seeds", "outputs", "handoverlab",
        "build")
_CONDITIONS = ("isd_m", "speed_mps", "ttt_ms", "offset_db", "traffic", "fading")
_OUTPUTS = ("events", "ctrl_csv", "meas_csv")
_HANDOVERLAB = ("run_length",)
_BUILD = ("ns3_dir", "path", "msys2")
_BUILD_DEFAULTS = {"ns3_dir": "~/ns-3-dev", "path": "", "msys2": "C:/msys64"}
# what the refusals say about the things the program cannot do
_RULE_NOTE = ("the ns-3 program has only Event A3 (stock NrA3RsrpHandoverAlgorithm, options --hyst and --ttt); "
              "CHO, DAPS, LTM and the other rules of HandoverLab have no counterpart in it")
_SCENARIO_NOTE = ("the ns-3 program reproduces the card %s only (TR 37.885 urban grid, one carrier, omni sites); "
                  "beams, layers, NTN, dual connectivity and the other cards have no counterpart in it" % CARD)


class Ns3BridgeError(ConfigError):
    """A study or a result set the bridge cannot handle; the message names the option."""


@dataclass
class Cell:
    """One condition of the factorial: everything but the seed."""
    isd_m: int
    speed_mps: float
    ttt_ms: int
    offset_db: float
    traffic: str
    fading: bool

    def key(self) -> Tuple:
        return (self.traffic, self.fading, self.offset_db, self.isd_m, self.speed_mps, self.ttt_ms)


@dataclass
class Ns3Study:
    """A study that runs, unchanged, in ns-3 (``handoverlab-ns3-a3.cc``) and in HandoverLab."""
    name: str
    description: str = ""
    users: int = 20
    duration_s: float = 180.0
    discard_s: float = 60.0
    isd_m: Tuple[int, ...] = (200,)
    speed_mps: Tuple[float, ...] = (16.0,)
    ttt_ms: Tuple[int, ...] = (300,)
    offset_db: Tuple[float, ...] = (3.0,)
    traffic: Tuple[str, ...] = ("light",)
    fading: Tuple[bool, ...] = (False,)
    seeds: Tuple[int, ...] = (1,)
    outputs: Dict[str, bool] = field(default_factory=lambda: {"events": True, "ctrl_csv": False,
                                                                "meas_csv": False})
    run_length: str = "study"
    build: Dict[str, str] = field(default_factory=lambda: dict(_BUILD_DEFAULTS))

    def cells(self) -> List[Cell]:
        """The conditions in run order (traffic, fading, offset, site distance, speed, time-to-trigger)."""
        return [Cell(i, v, t, h, tr, f) for tr, f, h, i, v, t in
                itertools.product(self.traffic, self.fading, self.offset_db, self.isd_m, self.speed_mps,
                                  self.ttt_ms)]

    def tag(self, cell: Cell, seed: Optional[int] = None) -> str:
        """Run tag, such as ``V1_light_d200_v10_t80_s401``; offset and fading appear only when they vary."""
        t = "%s_%s" % (self.name, cell.traffic)
        if len(self.offset_db) > 1:
            t += "_h%g" % cell.offset_db
        t += "_d%d_v%g_t%d" % (cell.isd_m, cell.speed_mps, cell.ttt_ms)
        if len(self.fading) > 1:
            t += "_f%d" % int(cell.fading)
        return t if seed is None else t + "_s%d" % seed

    def resolved(self) -> Dict[str, Any]:
        """The study as a plain dictionary (the input of :meth:`sha256`)."""
        return dict(schema=SCHEMA, name=self.name, description=self.description, users=self.users,
                    duration_s=self.duration_s, discard_s=self.discard_s,
                    conditions=dict(isd_m=list(self.isd_m), speed_mps=list(self.speed_mps),
                                    ttt_ms=list(self.ttt_ms), offset_db=list(self.offset_db),
                                    traffic=list(self.traffic), fading=list(self.fading)),
                    seeds=list(self.seeds), outputs=dict(self.outputs), run_length=self.run_length,
                    build=dict(self.build))

    def sha256(self) -> str:
        """Hash of what defines the ns-3 runs (name, users, run length, conditions, seeds, outputs); the
        HandoverLab run length, the build paths and the description do not enter it."""
        from ..studies.config import canonical
        d = {k: v for k, v in self.resolved().items() if k not in ("run_length", "build", "description")}
        return hashlib.sha256(canonical(d).encode()).hexdigest()


def _list(v: Any, where: str) -> list:
    v = list(v) if isinstance(v, (list, tuple)) else [v]
    if not v:
        raise Ns3BridgeError("%s: needs at least one value" % where)
    if len(set(map(repr, v))) != len(v):
        raise Ns3BridgeError("%s: values must not repeat" % where)
    return v


def _num(v: Any, where: str, lo: float, integer: bool = False) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (integer and float(v) != int(v)):
        raise Ns3BridgeError("%s: expected %s, got %r" % (where, "an integer" if integer else "a number", v))
    if v < lo:
        raise Ns3BridgeError("%s: must be at least %g, got %r" % (where, lo, v))
    return float(v)


def _check_keys(d: Any, allowed: Sequence[str], where: str) -> Dict[str, Any]:
    if not isinstance(d, dict):
        raise Ns3BridgeError("%s: expected a mapping" % where.rstrip("."))
    for k in d:
        if k not in allowed:
            raise Ns3BridgeError("unsupported option '%s%s': not part of the ns-3 bridge; allowed: %s"
                                 % (where, k, ", ".join(allowed)))
    return d


def _flat(d: Dict[str, Any], prefix: str = "") -> List[str]:
    out = []
    for k, v in d.items():
        if isinstance(v, dict) and v:
            out += _flat(v, prefix + k + ".")
        else:
            out.append(prefix + k)
    return out


def _scenario(v: Any) -> None:
    if isinstance(v, dict):
        base = v.get("base", v.get("name"))
        _scenario(base)
        extra = [k for k in _flat(v) if k not in ("base", "name")]
        if extra:
            raise Ns3BridgeError("unsupported option 'ns3.scenario.%s': %s; give conditions, users and run length "
                                 "in the ns3 section instead" % (extra[0], _SCENARIO_NOTE))
        return
    if v != CARD:
        raise Ns3BridgeError("unsupported option 'ns3.scenario: %s': %s" % (v, _SCENARIO_NOTE))


def _rule(v: Any) -> None:
    if isinstance(v, dict):
        _rule(v.get("rule"))
        extra = [k for k in v if k not in ("rule", "name")]
        if extra:
            raise Ns3BridgeError("unsupported option 'ns3.rule.%s': the A3 offset and time-to-trigger are "
                                 "conditions (ns3.conditions.offset_db, ttt_ms); %s" % (extra[0], _RULE_NOTE))
        return
    if v != "a3":
        raise Ns3BridgeError("unsupported option 'ns3.rule: %s': %s" % (v, _RULE_NOTE))


def study_from_dict(data: Dict[str, Any], name: Optional[str] = None) -> Ns3Study:
    """Check ``data`` (the content of an ns-3 study file) and return the study; refusals raise
    :class:`Ns3BridgeError` naming the option."""
    _check_keys(data, _TOP, "")
    if data.get("schema", SCHEMA) != SCHEMA:
        raise Ns3BridgeError("schema: this version reads ns-3 study files of schema %d, got %r"
                             % (SCHEMA, data.get("schema")))
    if "ns3" not in data:
        raise Ns3BridgeError("missing section 'ns3' (docs/guides/ns3-bridge.md)")
    d = _check_keys(data["ns3"], _NS3, "ns3.")
    nm = str(data.get("name") or name or "ns3")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", nm):
        raise Ns3BridgeError("name: %r; use letters, digits, '_', '-' and '.' (it starts every run tag)" % nm)
    _scenario(d.get("scenario", CARD))
    _rule(d.get("rule", "a3"))
    st = Ns3Study(name=nm, description=str(data.get("description") or ""))
    st.users = int(_num(d.get("users", 20), "ns3.users", 1, integer=True))
    st.duration_s = _num(d.get("duration_s", 180.0), "ns3.duration_s", 1.0)
    st.discard_s = _num(d.get("discard_s", 60.0), "ns3.discard_s", 0.0)
    if st.discard_s >= st.duration_s:
        raise Ns3BridgeError("ns3.discard_s: must be shorter than ns3.duration_s")
    c = _check_keys(d.get("conditions", {}), _CONDITIONS, "ns3.conditions.")
    isd = [int(_num(x, "ns3.conditions.isd_m", 1, integer=True)) for x in _list(c.get("isd_m", 200),
                                                                                 "ns3.conditions.isd_m")]
    for x in isd:
        if x not in ISDS:
            raise Ns3BridgeError("unsupported option 'ns3.conditions.isd_m: %d': the site lists of the program "
                                 "and of HandoverLab exist for %s m" % (x, ", ".join(map(str, ISDS))))
    st.isd_m = tuple(isd)
    st.speed_mps = tuple(_num(x, "ns3.conditions.speed_mps", 0.1) for x in _list(c.get("speed_mps", 16),
                                                                                "ns3.conditions.speed_mps"))
    st.ttt_ms = tuple(int(_num(x, "ns3.conditions.ttt_ms", 0, integer=True))
                      for x in _list(c.get("ttt_ms", 300), "ns3.conditions.ttt_ms"))
    st.offset_db = tuple(_num(x, "ns3.conditions.offset_db", -30.0) for x in _list(c.get("offset_db", 3.0),
                                                                                  "ns3.conditions.offset_db"))
    tr = _list(c.get("traffic", "light"), "ns3.conditions.traffic")
    for x in tr:
        if x not in TRAFFIC:
            raise Ns3BridgeError("unsupported option 'ns3.conditions.traffic: %s': the program has %s"
                                 % (x, ", ".join(TRAFFIC)))
    st.traffic = tuple(tr)
    fd = _list(c.get("fading", False), "ns3.conditions.fading")
    if not all(isinstance(x, bool) for x in fd):
        raise Ns3BridgeError("ns3.conditions.fading: expected true or false")
    st.fading = tuple(fd)
    from ..studies.config import _seed_list
    try:
        st.seeds = _seed_list(d.get("seeds", [1]), "ns3.seeds")
    except ConfigError as e:
        raise Ns3BridgeError(str(e)) from None
    o = _check_keys(d.get("outputs", {}), _OUTPUTS, "ns3.outputs.")
    for k, v in o.items():
        if not isinstance(v, bool):
            raise Ns3BridgeError("ns3.outputs.%s: expected true or false" % k)
        st.outputs[k] = v
    h = _check_keys(d.get("handoverlab", {}), _HANDOVERLAB, "ns3.handoverlab.")
    st.run_length = h.get("run_length", "study")
    if st.run_length not in RUN_LENGTHS:
        raise Ns3BridgeError("ns3.handoverlab.run_length: %r; use %s" % (st.run_length, " or ".join(RUN_LENGTHS)))
    b = _check_keys(d.get("build", {}), _BUILD, "ns3.build.")
    for k, v in b.items():
        if not isinstance(v, str):
            raise Ns3BridgeError("ns3.build.%s: expected a text" % k)
        st.build[k] = v
    return st


def load_ns3_study(source: Union[str, os.PathLike, Dict[str, Any], Ns3Study]) -> Ns3Study:
    """An :class:`Ns3Study` from a YAML, TOML or JSON file, a dictionary or a study (returned as it is)."""
    if isinstance(source, Ns3Study):
        return source
    if isinstance(source, dict):
        return study_from_dict(source)
    path = os.fspath(source)
    return study_from_dict(read_file(path) or {}, os.path.splitext(os.path.basename(path))[0])
