# SPDX-License-Identifier: MIT
"""``handoverlab ns3 export``: an ns-3 study as a ready-to-run package of the program ``handoverlab-ns3-a3.cc``."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from typing import Any, Dict, List, Optional, Union

from .. import __version__
from .study import Cell, Ns3BridgeError, Ns3Study, load_ns3_study
from .templates import BUILD_SH, README_MD, RUN_PS1, RUN_PY

PROGRAM = "handoverlab-ns3-a3.cc"
UDP_INTERVAL_MS = 100                    # the light traffic of every reference run (one 200-byte packet per 100 ms)
NS3_BUILD = ("ns-3.48 plus the upstream ns-3-dev commits b5520504a, ae5529988 (MR 2883), fa33c33cf (MR 2929) and, "
             "on Windows, 2beb9d9a6; 5G-LENA contrib/nr v5.1 with one local change in NrSpectrumPhy::StartRxSrs "
             "(benchmarks/ns3/README.md)")


def program_source(program: Optional[str] = None) -> str:
    """Path of the ns-3 program: ``program``, else ``benchmarks/ns3/handoverlab-ns3-a3.cc`` of a source checkout.

    The program is GPL-2.0-only and not part of the Python package; with an installed package give its
    path (from benchmarks/ns3 of the HandoverLab repository).
    """
    if program:
        if not os.path.isfile(program):
            raise Ns3BridgeError("program %s: no such file" % program)
        return program
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "..", "..", "benchmarks", "ns3", PROGRAM))
    if not os.path.isfile(path):
        raise Ns3BridgeError("the ns-3 program %s is not part of the Python package; give its path with "
                             "--program (benchmarks/ns3/%s of the HandoverLab repository)" % (PROGRAM, PROGRAM))
    return path


def command_args(study: Ns3Study, cell: Cell, seed: int) -> List[str]:
    """The program options of one run (without the program and ``--outDir``, which ``run.py`` adds last)."""
    args = ["--scen=urban", "--rule=a3", "--hyst=%g" % cell.offset_db, "--ttt=%d" % cell.ttt_ms,
            "--isd=%d" % cell.isd_m, "--speed=%g" % cell.speed_mps, "--rngRun=%d" % seed,
            "--simTime=%g" % study.duration_s, "--discard=%g" % study.discard_s, "--nUe=%d" % study.users,
            "--udpInterval=%d" % UDP_INTERVAL_MS, "--fading=%d" % int(cell.fading), "--traffic=" + cell.traffic]
    for key, opt in (("events", "--events=1"), ("ctrl_csv", "--ctrlCsv=1"), ("meas_csv", "--measCsv=1")):
        if study.outputs.get(key):
            args.append(opt)
    return args + ["--tag=" + study.tag(cell, seed)]


def runs(study: Ns3Study) -> List[Dict[str, Any]]:
    """Every run of the study: tag, condition, seed and program options, in run order."""
    out = []
    for cell in study.cells():
        for seed in study.seeds:
            out.append(dict(tag=study.tag(cell, seed), seed=seed,
                            cell=dict(isd_m=cell.isd_m, speed_mps=cell.speed_mps, ttt_ms=cell.ttt_ms,
                                      offset_db=cell.offset_db, traffic=cell.traffic, fading=cell.fading),
                            args=command_args(study, cell, seed)))
    return out


def manifest(study: Ns3Study, program_sha256: str = "") -> Dict[str, Any]:
    """The content of ``manifest.json``."""
    return dict(format="handoverlab-ns3-export", schema=1, name=study.name, study_sha256=study.sha256(),
                handoverlab=__version__, program=PROGRAM, program_sha256=program_sha256, ns3_build=NS3_BUILD,
                runs_dir="runs", zip="%s_results.zip" % study.name, path=study.build["path"],
                study=study.resolved(), runs=runs(study))


def export(study: Union[str, os.PathLike, Dict[str, Any], Ns3Study], out: str, program: Optional[str] = None,
           overwrite: bool = False) -> Dict[str, Any]:
    """Write the ns-3 package of ``study`` to the folder ``out`` and return its manifest.

    The study is checked first (unsupported options raise :class:`Ns3BridgeError` naming the option)
    and nothing is written unless it passes.  ``out`` must not exist or be empty unless ``overwrite``.
    """
    st = load_ns3_study(study)
    src = program_source(program)
    if os.path.isdir(out) and os.listdir(out) and not overwrite:
        raise Ns3BridgeError("%s exists and is not empty (use overwrite / --force)" % out)
    with open(src, "rb") as f:
        code = f.read()
    man = manifest(st, hashlib.sha256(code).hexdigest())
    os.makedirs(out, exist_ok=True)
    shutil.copyfile(src, os.path.join(out, PROGRAM))
    copying = os.path.join(os.path.dirname(src), "COPYING")
    if os.path.isfile(copying):
        shutil.copyfile(copying, os.path.join(out, "COPYING"))
    fill = dict(name=st.name, version=__version__, n_runs=len(man["runs"]), runs_dir=man["runs_dir"],
                zip=man["zip"], ns3_dir=st.build["ns3_dir"], msys2=st.build["msys2"].replace("\\", "/"),
                msys2_win=st.build["msys2"].replace("/", "\\"), sha=man["study_sha256"][:16],
                description=st.description)
    for name, text in (("run.py", RUN_PY), ("build.sh", BUILD_SH), ("run.ps1", RUN_PS1), ("README.md", README_MD)):
        eol = "\r\n" if name.endswith(".ps1") else "\n"
        with open(os.path.join(out, name), "w", encoding="utf-8", newline=eol) as f:
            f.write(text % fill)
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    return man
