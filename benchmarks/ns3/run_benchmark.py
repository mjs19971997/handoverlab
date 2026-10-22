# SPDX-License-Identifier: MIT
"""Run the ns-3 side of the HandoverLab benchmark and write a reference file for ``handoverlab verify``.

The program ``handoverlab-ns3-a3.cc`` (GPL-2.0-only, in this folder) is the ns-3.48 + 5G-LENA nr v5.1 scenario
behind the stored reference of HandoverLab (``handoverlab/verify/data/ns3_urban_a3.json``).  This script runs its
three parts and writes the results in the same format:

  part A   24 Event-A3 settings (hysteresis 1-6 dB x time-to-trigger 100-1000 ms) on four conditions (site distance
           200 / 400 m x 16 / 30 m/s), one 150 s run each (seeds 101-104), the first 60 s discarded
  part B   the settings 1 dB / 300 ms and 6 dB / 100 ms on six conditions (200 / 400 m x 8 / 16 / 30 m/s),
           --runs-b runs of 180 s each (seeds 1, 2, ...)
  part C   6 dB / 100 ms with one parameter changed per cell (users, preparation delay, T310, site distance, run
           length, speed), --runs-c runs each

  python run_benchmark.py --exe PATH_TO_BUILT_PROGRAM [--parts A B C] [--workers 6] [--out results] [--fading]
  handoverlab verify --ns3 --ns3-reference results/reference.json

With --fading every run uses the TR 38.901 fast fading of ns-3 (program option --fading=1; run tags end in "f"),
for the comparison with the optional fast fading of HandoverLab (radio.fast_fading, since 2.2.0).

Finished runs are kept (one JSON file per run in OUT/runs); running the script again only runs what is missing.
No dependency beyond the Python standard library.
On Windows pass --path with the ns-3 library folder and the compiler runtime (for example
"C:/ns-3-dev/build/lib;C:/msys64/ucrt64/bin") so that the program finds its DLLs.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

N_UE, DISCARD, UDP_INTERVAL_MS = 20, 60.0, 100
A3_GRID = [(h, t) for h in (1, 2, 3, 4, 5, 6) for t in (100, 300, 500, 1000)]
PART_A_TRACES = [(400, 16, 101), (400, 30, 102), (200, 16, 103), (200, 30, 104)]   # (site distance, speed, seed)
PART_B_SETTINGS = [(1, 300), (6, 100)]
PART_B_CELLS = [(isd, v) for isd in (200, 400) for v in (8, 16, 30)]
# part C: (site distance, speed, program options, HandoverLab overrides, run length)
PART_C_CELLS = [
    (300, 16, [], {}, 180.0), (200, 16, [], {}, 600.0), (400, 16, [], {}, 600.0),
    (200, 16, ["--prepDelay=100"], {"protocol.prep_s": 0.1}, 180.0),
    (400, 16, ["--prepDelay=100"], {"protocol.prep_s": 0.1}, 180.0),
    (200, 16, ["--prepDelay=20"], {"protocol.prep_s": 0.02}, 180.0),
    (400, 16, ["--prepDelay=20"], {"protocol.prep_s": 0.02}, 180.0),
    (200, 16, ["--t310=2000"], {"protocol.t310_s": 2.0}, 180.0),
    (400, 16, ["--t310=2000"], {"protocol.t310_s": 2.0}, 180.0),
    (200, 16, ["--t310=500"], {"protocol.t310_s": 0.5}, 180.0),
    (400, 16, ["--t310=500"], {"protocol.t310_s": 0.5}, 180.0),
    (200, 16, ["--nUe=10"], {"mobility.users": 10}, 180.0),
    (400, 16, ["--nUe=10"], {"mobility.users": 10}, 180.0),
    (200, 16, ["--nUe=40"], {"mobility.users": 40}, 180.0),
    (400, 16, ["--nUe=40"], {"mobility.users": 40}, 180.0),
    (400, 16, ["--nUe=60"], {"mobility.users": 60}, 180.0),
    (200, 3, [], {}, 180.0), (400, 3, [], {}, 180.0), (200, 42, [], {}, 180.0), (400, 42, [], {}, 180.0),
]
# the seven sites of the program (urban scenario): the hexagonal plan moved to the street centre lines
SITES = {"200": [[0, 0], [200, 0], [-200, 0], [100, 250], [-100, 250], [100, -250], [-100, -250]],
         "300": [[0, 0], [300, 0], [-300, 0], [150, 250], [-150, 250], [150, -250], [-150, -250]],
         "400": [[0, 0], [400, 0], [-400, 0], [200, 250], [-200, 250], [200, -250], [-200, -250]]}


def jobs(parts, runs_b, runs_c, fading=False):
    out = []
    if "A" in parts:
        for isd, v, seed in PART_A_TRACES:
            for h, t in A3_GRID:
                out.append(dict(part="A", isd=isd, speed=v, h=h, t=t, seed=seed, sim=150.0, opts=[], ov={}))
    if "B" in parts:
        for seed in range(1, runs_b + 1):
            for isd, v in PART_B_CELLS:
                for h, t in PART_B_SETTINGS:
                    out.append(dict(part="B", isd=isd, speed=v, h=h, t=t, seed=seed, sim=180.0, opts=[], ov={}))
    if "C" in parts:
        for seed in range(1, runs_c + 1):
            for k, (isd, v, opts, ov, sim) in enumerate(PART_C_CELLS):
                out.append(dict(part="C", cell=k, isd=isd, speed=v, h=6, t=100, seed=seed, sim=sim, opts=opts, ov=ov))
    for j in out:
        j["tag"] = "%s%s_h%g_t%d_d%d_v%d_s%d%s" % (j["part"], j.get("cell", ""), j["h"], j["t"], j["isd"], j["speed"],
                                                   j["seed"], "f" if fading else "")
        j["fading"] = fading
    return out


def run_one(job, exe, rundir, env):
    path = os.path.join(rundir, job["tag"] + ".json")
    if os.path.exists(path):
        return job["tag"], "kept"
    args = [exe, "--scen=urban", "--rule=a3", "--hyst=%g" % job["h"], "--ttt=%d" % job["t"], "--isd=%d" % job["isd"],
            "--speed=%d" % job["speed"], "--rngRun=%d" % job["seed"], "--simTime=%g" % job["sim"],
            "--discard=%g" % DISCARD, "--nUe=%d" % N_UE, "--udpInterval=%d" % UDP_INTERVAL_MS,
            "--fading=%d" % int(job.get("fading", False)),
            "--tag=" + job["tag"], "--outDir=" + rundir.replace("\\", "/")] + job["opts"]
    with open(os.path.join(rundir, job["tag"] + ".log"), "w") as log:
        rc = subprocess.call(args, stdout=log, stderr=subprocess.STDOUT, env=env)
    return job["tag"], "ok" if rc == 0 and os.path.exists(path) else "FAILED (exit %d)" % rc


def reference(all_jobs, rundir, fading=False):
    """The runs in the format of handoverlab/verify/data/ns3_urban_a3.json."""
    groups = {}
    for j in all_jobs:
        path = os.path.join(rundir, j["tag"] + ".json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            m = json.load(f)
        key = (j["part"], j.get("cell"), j["isd"], j["speed"], j["h"], j["t"])
        groups.setdefault(key, (j, []))[1].append([m["ho_pm"], m["uho_pm"], m["fail_pm"], m["sinr_db"]])
    rows = []
    for (part, cell, isd, v, h, t), (j, vals) in sorted(groups.items(), key=lambda kv: str(kv[0])):
        col = [[float(x[k]) for x in vals] for k in range(4)]
        row = dict(part=part, isd_m=isd, speed_mps=v, a3_offset_db=float(h), ttt_ms=t, runs=len(vals),
                   handovers_pm=statistics.fmean(col[0]), unnecessary_pm=statistics.fmean(col[1]),
                   failures_pm=statistics.fmean(col[2]), sinr_db=statistics.fmean(col[3]),
                   handovers_pm_sd=statistics.stdev(col[0]) if len(vals) > 1 else None)
        if part == "C":
            row.update(overrides=j["ov"], duration_s=j["sim"])
        rows.append(row)
    return dict(description="ns-3 / 5G-LENA results written by benchmarks/ns3/run_benchmark.py (program "
                            "handoverlab-ns3-a3.cc, urban scenario%s); same format as the stored reference."
                            % (", TR 38.901 fast fading" if fading else ""),
                sites=SITES, rows=rows, fading=bool(fading))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--exe", required=True, help="the built handoverlab-ns3-a3 program")
    ap.add_argument("--out", default="results", help="output folder (default: results)")
    ap.add_argument("--parts", nargs="+", default=["A"], choices=["A", "B", "C"], help="parts to run (default: A)")
    ap.add_argument("--runs-b", type=int, default=20, help="runs per cell of part B (default 20)")
    ap.add_argument("--runs-c", type=int, default=10, help="runs per cell of part C (default 10)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2), help="runs at a time")
    ap.add_argument("--path", help="folders to put in front of PATH for the program (ns-3 libraries, runtime)")
    ap.add_argument("--dry-run", action="store_true", help="list the runs and stop")
    ap.add_argument("--fading", action="store_true", help="TR 38.901 fast fading in ns-3 (--fading=1)")
    a = ap.parse_args(argv)
    todo = jobs(a.parts, a.runs_b, a.runs_c, a.fading)
    rundir = os.path.abspath(os.path.join(a.out, "runs"))
    os.makedirs(rundir, exist_ok=True)
    if a.dry_run:
        for j in todo:
            print(j["tag"])
        print("%d runs" % len(todo))
        return 0
    env = dict(os.environ)
    if a.path:
        env["PATH"] = a.path + os.pathsep + env.get("PATH", "")
    failed = 0
    with ThreadPoolExecutor(a.workers) as pool:
        for i, (tag, status) in enumerate(pool.map(lambda j: run_one(j, a.exe, rundir, env), todo)):
            failed += status.startswith("FAILED")
            print("%4d/%d %s %s" % (i + 1, len(todo), tag, status), flush=True)
    ref = reference(todo, rundir, a.fading)
    path = os.path.join(a.out, "reference.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ref, f, indent=1)
    print("wrote %s (%d rows); %d run(s) failed" % (path, len(ref["rows"]), failed))
    print("compare: handoverlab verify --ns3 --ns3-reference %s" % path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
