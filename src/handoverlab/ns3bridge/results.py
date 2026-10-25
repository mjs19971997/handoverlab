# SPDX-License-Identifier: MIT
"""``handoverlab ns3 import``: the run JSONs of ``handoverlab-ns3-a3`` as a reference file.

The output has the format of :func:`handoverlab.verify.ns3.load_reference` (``sites`` and ``rows``): one row
per condition with the means over its runs (``part: "S"``), plus what the checks of
:func:`handoverlab.ns3bridge.compare` need: the failure count and UE-minutes summed over the runs and one entry
per run.
"""
from __future__ import annotations

import json
import os
import zipfile
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

from .study import Ns3BridgeError

FORMAT = "handoverlab-ns3-reference"
# fields of a run JSON the import reads (written by handoverlab-ns3-a3.cc)
_NEEDED = ("tag", "rngRun", "isd", "speed", "hyst", "ttt_ms", "nUe", "simTime", "discard", "fading", "traffic",
           "ue_min", "attempts", "failures", "ho_pm", "uho_pm", "fail_pm", "sinr_db")


def _members(source: str) -> Iterator[Tuple[str, bytes]]:
    if os.path.isdir(source):
        for root, _dirs, files in os.walk(source):
            for f in sorted(files):
                if f.endswith(".json"):
                    with open(os.path.join(root, f), "rb") as fh:
                        yield os.path.relpath(os.path.join(root, f), source), fh.read()
    elif zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            for n in sorted(z.namelist()):
                if n.endswith(".json"):
                    yield n, z.read(n)
    else:
        raise Ns3BridgeError("%s: neither a folder nor a zip file" % source)


def read_runs(source: str) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """The run JSONs in the folder or zip file ``source`` and its ``manifest.json`` (None if there is none)."""
    if not os.path.exists(source):
        raise Ns3BridgeError("%s: no such file or folder" % source)
    runs, man = [], None
    for name, data in _members(source):
        try:
            d = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise Ns3BridgeError("%s: not a JSON file (%s)" % (name, e)) from None
        if os.path.basename(name) == "manifest.json" and isinstance(d, dict) and d.get("format") == \
                "handoverlab-ns3-export":
            man = d
        elif isinstance(d, dict) and "rngRun" in d and "tag" in d:
            missing = [k for k in _NEEDED if k not in d]
            if missing:
                raise Ns3BridgeError("%s: run JSON without %s (another version of the program?)"
                                     % (name, ", ".join(missing)))
            runs.append(d)
    if not runs:
        raise Ns3BridgeError("%s: no run JSON of handoverlab-ns3-a3 found" % source)
    return runs, man


def reference_from_runs(runs: List[Dict[str, Any]], man: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Group the runs by condition and return the reference dictionary."""
    from ..verify.ns3 import load_reference
    groups: Dict[tuple, list] = {}
    for m in runs:
        key = (int(m["isd"]), float(m["speed"]), float(m["hyst"]), int(m["ttt_ms"]), str(m["traffic"]),
               bool(int(m["fading"])), int(m["nUe"]), float(m["simTime"]), float(m["discard"]))
        groups.setdefault(key, []).append(m)
    rows = []
    for key in sorted(groups):
        isd, v, h, t, tr, fd, n_ue, sim, disc = key
        ms = sorted(groups[key], key=lambda m: int(m["rngRun"]))
        seeds = [int(m["rngRun"]) for m in ms]
        if len(set(seeds)) != len(seeds):
            raise Ns3BridgeError("condition %d m, %g m/s, %g dB / %d ms: seed %d appears twice"
                                 % (isd, v, h, t, [s for s in seeds if seeds.count(s) > 1][0]))
        ho = [float(m["ho_pm"]) for m in ms]
        rows.append(dict(part="S", isd_m=isd, speed_mps=v, a3_offset_db=h, ttt_ms=t, traffic=tr, fading=fd,
                         users=n_ue, duration_s=sim, discard_s=disc, runs=len(ms), seeds=seeds,
                         handovers_pm=float(np.mean(ho)),
                         unnecessary_pm=float(np.mean([float(m["uho_pm"]) for m in ms])),
                         failures_pm=float(np.mean([float(m["fail_pm"]) for m in ms])),
                         sinr_db=float(np.mean([float(m["sinr_db"]) for m in ms])),
                         handovers_pm_sd=float(np.std(ho, ddof=1)) if len(ms) > 1 else None,
                         failures=int(sum(int(m["failures"]) for m in ms)),
                         ue_min=float(sum(float(m["ue_min"]) for m in ms)),
                         per_run=[dict(seed=int(m["rngRun"]), tag=m["tag"], ho_pm=float(m["ho_pm"]),
                                       uho_pm=float(m["uho_pm"]), failures=int(m["failures"]),
                                       ue_min=float(m["ue_min"]), sinr_db=float(m["sinr_db"])) for m in ms]))
    ref = dict(format=FORMAT, schema=1,
               description="ns-3 / 5G-LENA results of handoverlab-ns3-a3.cc (urban scenario), imported by "
                           "handoverlab ns3 import; rows of part 'S': one per condition, means over its runs.",
               sites=load_reference()["sites"], rows=rows, n_runs=len(runs))
    if man:
        ref.update(study=man.get("name"), study_sha256=man.get("study_sha256"),
                   exported_by=man.get("handoverlab"), program_sha256=man.get("program_sha256"))
    return ref


def import_results(source: str, out: Optional[str] = None) -> Dict[str, Any]:
    """Read the ns-3 results in ``source`` (the zip of ``run.py`` or a folder of run JSONs) and return the
    reference; with ``out`` also write it there as JSON."""
    runs, man = read_runs(source)
    ref = reference_from_runs(runs, man)
    if out:
        d = os.path.dirname(os.path.abspath(out))
        os.makedirs(d, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(ref, f, indent=1)
            f.write("\n")
    return ref
