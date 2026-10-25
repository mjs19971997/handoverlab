# SPDX-License-Identifier: MIT
"""The files of an exported ns-3 package (``handoverlab ns3 export``), standard library only.

``RUN_PY`` reads ``manifest.json`` and runs every ns-3 command line in it: resumable (a run whose JSON exists
is kept), several at a time, and at the end it zips the results for ``handoverlab ns3 import``.
"""

RUN_PY = r'''# SPDX-License-Identifier: MIT
"""ns-3 side of the study %(name)s, exported by HandoverLab %(version)s (handoverlab ns3 export).

  python run.py [WORKERS] [--exe PROGRAM] [--path DIRS] [--dry-run] [--zip-only]

Runs the %(n_runs)d command lines of manifest.json with the program handoverlab-ns3-a3 (built by build.sh,
or given with --exe), WORKERS at a time (default: CPU threads - 2, at most 20). Resumable: a run whose JSON
file exists in %(runs_dir)s/ is kept, so the same line can be run again after a stop (Ctrl+C). At the end the
results (run JSONs, event CSVs and, with outputs.ctrl_csv, the _ctrl.csv files; no logs) are zipped into
%(zip)s; bring it back with
  handoverlab ns3 import %(zip)s --out reference.json
--path puts folders (ns-3 libraries, compiler runtime) in front of PATH; the default is the one of the study.
Standard library only.
"""
import argparse
import json
import os
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def find_exe(given):
    if given:
        return given
    for name in ("handoverlab-ns3-a3.exe", "handoverlab-ns3-a3"):
        if os.path.exists(os.path.join(HERE, name)):
            return os.path.join(HERE, name)
    return None


def main(argv=None):
    with open(os.path.join(HERE, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    ap = argparse.ArgumentParser(description="ns-3 side of the study %%s" %% man["name"])
    ap.add_argument("workers", nargs="?", type=int, default=max(1, min(20, (os.cpu_count() or 2) - 2)))
    ap.add_argument("--exe", help="the built program (default: handoverlab-ns3-a3[.exe] next to this file)")
    ap.add_argument("--path", default=man.get("path", ""), help="folders put in front of PATH for the program")
    ap.add_argument("--dry-run", action="store_true", help="list the command lines and stop")
    ap.add_argument("--zip-only", action="store_true", help="zip the finished runs and stop")
    a = ap.parse_args(argv)
    out = os.path.join(HERE, man["runs_dir"])
    runs = man["runs"]
    if a.dry_run:
        for r in runs:
            print(" ".join(["handoverlab-ns3-a3"] + r["args"] + ["--outDir=" + man["runs_dir"]]))
        print("%%d runs" %% len(runs))
        return 0
    if not a.zip_only:
        exe = find_exe(a.exe)
        if not exe or not os.path.exists(exe):
            print("error: program not found; build it with build.sh (or run.ps1) or give --exe", file=sys.stderr)
            return 2
        env = dict(os.environ)
        if a.path:
            env["PATH"] = a.path + os.pathsep + env.get("PATH", "")
        os.makedirs(out, exist_ok=True)

        def job(r):
            if os.path.exists(os.path.join(out, r["tag"] + ".json")):
                return r["tag"] + " (done earlier)"
            args = [exe] + r["args"] + ["--outDir=" + out.replace("\\", "/")]
            with open(os.path.join(out, r["tag"] + ".log"), "w") as log:
                rc = subprocess.call(args, stdout=log, stderr=subprocess.STDOUT, env=env)
            ok = rc == 0 and os.path.exists(os.path.join(out, r["tag"] + ".json"))
            return "%%s %%s" %% (r["tag"], "ok" if ok else "FAILED (exit %%d, see the .log)" %% rc)

        print("%%d runs, %%d at a time" %% (len(runs), a.workers), flush=True)
        with ThreadPoolExecutor(a.workers) as pool:
            for n, msg in enumerate(pool.map(job, runs), 1):
                print("%%3d/%%d %%s" %% (n, len(runs), msg), flush=True)
    done = 0
    ctrl = bool(man.get("study", {}).get("outputs", {}).get("ctrl_csv"))
    with zipfile.ZipFile(os.path.join(HERE, man["zip"]), "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(HERE, "manifest.json"), "manifest.json")
        for f in sorted(os.listdir(out)) if os.path.isdir(out) else []:
            if f.endswith(".log") or f.endswith(".tmp") or (f.endswith("_ctrl.csv") and not ctrl):
                continue
            z.write(os.path.join(out, f), man["runs_dir"] + "/" + f)
            done += f.endswith(".json")
    print("%%d of %%d runs finished; wrote %%s" %% (done, len(runs), man["zip"]), flush=True)
    return 0 if done == len(runs) else 1


if __name__ == "__main__":
    sys.exit(main())
'''

BUILD_SH = r'''#!/bin/bash
# Builds handoverlab-ns3-a3 next to this script (study %(name)s, exported by HandoverLab %(version)s).
#   bash build.sh [NS3_DIR]            default NS3_DIR: %(ns3_dir)s (or the variable NS3_DIR)
# ns-3 as documented in benchmarks/ns3/README.md of HandoverLab: ns-3.48 plus the listed upstream commits,
# 5G-LENA (contrib/nr) v5.1 with its one local change, configured with -d optimized --enable-modules=nr.
# BUILD=scratch (default): copies the program into NS3_DIR/scratch, builds it with ./ns3 and copies the binary
#   here; NS3_DIR/scratch gets the program file, nothing else in the ns-3 tree changes.
# BUILD=direct: compiles and links against the built ns-3.48 libraries without touching the ns-3 tree
#   (MSYS2 UCRT64 on Windows, as for the reference runs; UCRT gives the toolchain prefix).
HERE="$(cd "$(dirname "$0")" && pwd)"
NS3="${1:-${NS3_DIR:-%(ns3_dir)s}}"
NS3="${NS3/#\~/$HOME}"
SRC="$HERE/handoverlab-ns3-a3.cc"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) EXT=.exe ;; *) EXT= ;; esac
OUT="$HERE/handoverlab-ns3-a3$EXT"
if [ ! -d "$NS3" ]; then echo "ns-3 not found at $NS3 (give its folder as the first argument)"; exit 1; fi
if [ "${BUILD:-scratch}" = "scratch" ]; then
    cp "$SRC" "$NS3/scratch/handoverlab-ns3-a3.cc" || exit 1
    (cd "$NS3" && ./ns3 build handoverlab-ns3-a3) || exit 2
    BIN="$(ls "$NS3"/build/scratch/ns3.*-handoverlab-ns3-a3-*$EXT 2>/dev/null | head -n 1)"
    if [ -z "$BIN" ]; then echo "built program not found in $NS3/build/scratch"; exit 3; fi
    cp "$BIN" "$OUT" || exit 3
    echo "built $OUT"
    exit 0
fi
UCRT="${UCRT:-%(msys2)s/ucrt64}"
export PATH="$UCRT/bin:$PATH"
L=$NS3/build/lib
c++ -DEIGEN_MPL2_ONLY -DHAVE_EIGEN3 -DHAVE_SQLITE3 -DNS3_BUILD_PROFILE_OPTIMIZED \
    -DPROJECT_SOURCE_PATH=\"$NS3\" -DSTACKTRACE_LIBRARY_IS_LINKED=1 -D_USE_MATH_DEFINES \
    -I$NS3/build/include -isystem $UCRT/include/eigen3 \
    -O3 -DNDEBUG -std=c++23 -fno-semantic-interposition -Wall -Wpedantic -march=native -mtune=native \
    -c "$SRC" -o "$OUT.obj" || exit 1
c++ -O3 -DNDEBUG "$OUT.obj" -o "$OUT" -L$L \
    -Wl,--no-as-needed $L/libns3.48-nr-optimized.dll.a -Wl,--as-needed \
    $L/libns3.48-config-store-optimized.dll.a $L/libns3.48-csma-optimized.dll.a \
    $L/libns3.48-applications-optimized.dll.a $L/libns3.48-point-to-point-optimized.dll.a \
    $L/libns3.48-virtual-net-device-optimized.dll.a $L/libns3.48-spectrum-optimized.dll.a \
    $L/libns3.48-buildings-optimized.dll.a $L/libns3.48-propagation-optimized.dll.a \
    $L/libns3.48-mobility-optimized.dll.a $L/libns3.48-antenna-optimized.dll.a \
    $L/libns3.48-flow-monitor-optimized.dll.a $L/libns3.48-internet-apps-optimized.dll.a \
    $L/libns3.48-internet-optimized.dll.a $L/libns3.48-traffic-control-optimized.dll.a \
    $L/libns3.48-bridge-optimized.dll.a $L/libns3.48-network-optimized.dll.a \
    $L/libns3.48-stats-optimized.dll.a $L/libns3.48-core-optimized.dll.a \
    -Wl,--no-as-needed -lwsock32 -lws2_32 $UCRT/lib/libsqlite3.dll.a -Wl,--as-needed \
    -lstdc++exp -lkernel32 -luser32 -lgdi32 -lwinspool -lshell32 -lole32 -loleaut32 -luuid -lcomdlg32 -ladvapi32 \
    || exit 2
echo "built $OUT"
'''

RUN_PS1 = r'''# ns-3 side of the study %(name)s (%(n_runs)d runs), exported by HandoverLab %(version)s.
# On Windows with MSYS2 (the folder in the variable MSYS2, else the one of the study).
# Run in PowerShell from this folder:   powershell -ExecutionPolicy Bypass -File .\run.ps1
# Runs at a time: add a number, e.g.  .\run.ps1 20  (default: CPU threads - 2, at most 20).
# Progress:  (Get-ChildItem .\%(runs_dir)s\*.json).Count   -> finished runs (%(n_runs)d).
# Resumable: if it stops, run the same line again; finished runs are kept.
# Builds the program first if it is missing (build.sh with BUILD=direct against the ns-3 libraries).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$msys = if ($env:MSYS2) { $env:MSYS2 } else { '%(msys2_win)s' }
$env:MSYSTEM = 'UCRT64'; $env:CHERE_INVOKING = '1'
if (-not (Test-Path .\handoverlab-ns3-a3.exe)) {
    $sh = (Join-Path $here 'build.sh') -replace '\\', '/'
    $env:BUILD = 'direct'
    & (Join-Path $msys 'usr\bin\bash.exe') -lc "bash '$sh'"
    if (-not (Test-Path .\handoverlab-ns3-a3.exe)) { Write-Host "BUILD FAILED"; exit 1 }
}
$py = Join-Path $msys 'ucrt64\bin\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }
& $py run.py $args
Write-Host "DONE: send back %(zip)s"
'''

README_MD = '''# ns-3 package of the study %(name)s

Exported by HandoverLab %(version)s with `handoverlab ns3 export` (study hash `%(sha)s`).
%(description)s

| File | What it is |
|---|---|
| `handoverlab-ns3-a3.cc` | the ns-3 program (GPL-2.0-only, `COPYING`) |
| `build.sh` | builds it next to this file (`bash build.sh NS3_DIR`) |
| `run.py` | runs the %(n_runs)d command lines of `manifest.json` and zips the results into `%(zip)s` |
| `run.ps1` | the same on Windows with MSYS2: builds if needed, then runs `run.py` |
| `manifest.json` | the study, its hash, the HandoverLab version and every ns-3 command line |

ns-3 as for the reference runs: ns-3.48 plus the upstream commits listed in `benchmarks/ns3/README.md` of
HandoverLab, 5G-LENA v5.1 with its one local change.

    bash build.sh ~/ns-3-dev
    python run.py 6
    handoverlab ns3 import %(zip)s --out reference.json
    handoverlab ns3 compare STUDY.yaml reference.json
'''
