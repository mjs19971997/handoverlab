# Command line

Generated from the argument parser of `handoverlab` (`python -m handoverlab` works as well). Every command prints its own help with `-h`.

```text
usage: handoverlab [-h] [--version]
                   {run,verify,scenarios,study,report,status,gui,ns3,rules,init} ...

System-level handover simulator.

positional arguments:
  {run,verify,scenarios,study,report,status,gui,ns3,rules,init}
    run                 run an experiment configuration
    verify              run the verification checks and print a pass/fail report
    scenarios           list the built-in scenarios or show a scenario card
    study               run or resume a study (tuning with gates, test stage, tables)
    report              write the Markdown/HTML report of a study directory
    status              finished, failed and remaining jobs of a study and the time still needed
    gui                 start the browser dashboard (pip install handoverlab[gui])
    ns3                 export a study to ns-3 / 5G-LENA, import its results, compare (F1-F4)
    rules               list the available handover rules
    init                write an example configuration

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## run

```text
usage: handoverlab run [-h] [-o OUTPUT] [--seeds SEEDS [SEEDS ...]] [--events FILE]
                       [--event-level {summary,full}] [--debug] [-q]
                       config

positional arguments:
  config                configuration file (.yaml, .yml, .toml or .json)

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        result file (.csv or .json)
  --seeds SEEDS [SEEDS ...]
                        override the seeds of the configuration
  --events FILE         also write the event logs to FILE (.parquet if pyarrow is installed, else
                        .csv)
  --event-level {summary,full}
                        with --events: 'summary' (one row per attempt and failure, default) or
                        'full' (also the procedure trace, written next to FILE as FILE-trace)
  --debug               check the engine invariants while running (slower)
  -q, --quiet           print nothing but errors
```

## verify

```text
usage: handoverlab verify [-h] [--only GROUP [GROUP ...]] [--full] [--ns3] [--ns3-seeds NS3_SEEDS]
                          [--ns3-reference FILE] [--ns3-comparison] [--results FILE]
                          [--sample SAMPLE] [--json OUT] [-q]

options:
  -h, --help            show this help message and exit
  --only GROUP [GROUP ...]
                        check groups: pathloss radio calibration invariants equivalences
                        fingerprints extended highway values fading (default: all of them); on
                        request only: learning ntn scenarios
  --full                longer checks (three seeds for the radio statistics)
  --ns3                 compare with the stored ns-3 / 5G-LENA results (several minutes); only
                        this check unless --only names groups
  --ns3-seeds NS3_SEEDS
                        seeds per condition for --ns3 (default 1)
  --ns3-reference FILE  with --ns3: compare with this reference file instead of the stored one
                        (written by benchmarks/ns3/run_benchmark.py)
  --ns3-comparison      with --ns3: run HandoverLab with the ns-3 comparison setting of 2.5.0
                        (interferer load 0.15 at link monitoring, ideal execution, the in-car loss
                        of ns-3): a setting that brings the failure level closer (0.5-1.3 of
                        ns-3's, depending on the set), not validated; not a default
  --results FILE        recompute a JSON result file of 'run' and compare fingerprints
  --sample SAMPLE       with --results: recompute only this many runs, chosen at random
  --json OUT            also write the report as JSON
  -q, --quiet           print only the summary line
```

## scenarios

```text
usage: handoverlab scenarios [-h] [--markdown] [--svg FILE] [--docs DIR] [name]

positional arguments:
  name        scenario to show

options:
  -h, --help  show this help message and exit
  --markdown  print the card as Markdown
  --svg FILE  write a drawing of the layout
  --docs DIR  write Markdown cards and layout drawings of all scenarios
```

## study

```text
usage: handoverlab study [-h] [-o DIR] [--workers WORKERS] [--tuning-only] [--dry-run] [--status]
                         [--report] [-q]
                         study

positional arguments:
  study                 study file (.yaml, .yml, .toml or .json)

options:
  -h, --help            show this help message and exit
  -o DIR, --output DIR  study directory (default: 'output' of the study file)
  --workers WORKERS     worker processes (default: the study file's 'workers', else the CPUs minus
                        four)
  --tuning-only         stop after the tuning gates
  --dry-run             show what would run, run nothing
  --status              show finished, failed and remaining jobs
  --report              write the report when the study is complete
  -q, --quiet           print nothing but errors
```

## report

```text
usage: handoverlab report [-h] [-o OUT] [--format {md,html} [{md,html} ...]] [--no-figures] dir

positional arguments:
  dir                   study directory

options:
  -h, --help            show this help message and exit
  -o OUT, --output OUT  report directory (default: DIR/report)
  --format {md,html} [{md,html} ...]
  --no-figures          tables only
```

## status

```text
usage: handoverlab status [-h] [-o DIR] [--workers WORKERS] target

positional arguments:
  target                study file or study directory

options:
  -h, --help            show this help message and exit
  -o DIR, --output DIR  study directory (for a study file; default: its 'output')
  --workers WORKERS     workers assumed for the estimate (default: those of the last session)
```

## gui

```text
usage: handoverlab gui [-h] [--port PORT] [--address ADDRESS] [--headless]

options:
  -h, --help         show this help message and exit
  --port PORT        port of the local server (default 8501)
  --address ADDRESS  address to listen on (default localhost)
  --headless         do not open a browser window
```

## ns3

```text
usage: handoverlab ns3 [-h] {export,import,compare} ...

positional arguments:
  {export,import,compare}
    export              write a ready-to-run ns-3 package of an ns-3 study file
    import              read the ns-3 run JSONs (zip of run.py or a folder) into a reference file
    compare             run HandoverLab on the cells and seeds of a reference and check F1-F4

options:
  -h, --help            show this help message and exit
```

### ns3 export

```text
usage: handoverlab ns3 export [-h] --out DIR [--program FILE] [--force] study

positional arguments:
  study           ns-3 study file (.yaml, .yml, .toml or .json; docs/guides/ns3-bridge.md)

options:
  -h, --help      show this help message and exit
  --out DIR       package folder (must not exist or be empty)
  --program FILE  the ns-3 program handoverlab-ns3-a3.cc (default: benchmarks/ns3 of a source
                  checkout)
  --force         write into a folder that is not empty
```

### ns3 import

```text
usage: handoverlab ns3 import [-h] --out REF results

positional arguments:
  results     the results zip written by run.py, or a folder of run JSONs

options:
  -h, --help  show this help message and exit
  --out REF   reference file to write (.json)
```

### ns3 compare

```text
usage: handoverlab ns3 compare [-h] [--comparison] [--workers WORKERS] [-o OUT] [--level LO HI]
                               [--rank-min RANK_MIN] [--ho-ratio LO HI] [--ttt-share TTT_SHARE]
                               [--min-failures MIN_FAILURES] [-q]
                               study reference

positional arguments:
  study                 ns-3 study file
  reference             reference file written by 'ns3 import'

options:
  -h, --help            show this help message and exit
  --comparison          run HandoverLab with the ns-3 comparison setting of 2.5.0 (interferer load
                        0.15 at link monitoring): brings the failure level closer (0.5-1.3 of
                        ns-3's), not validated; not a default
  --workers WORKERS     processes for the HandoverLab runs (default 1)
  -o OUT, --output OUT  also write the cells and checks as JSON
  --level LO HI         F1: limits of the failure level HandoverLab / ns-3 (default 0.67 1.5)
  --rank-min RANK_MIN   F2: least rank correlation (default 0.8)
  --ho-ratio LO HI      F3: limits of the median handover-rate ratio (default 0.8 1.25)
  --ttt-share TTT_SHARE
                        F4: least share of TTT pairs with the sign of ns-3 (default 0.75)
  --min-failures MIN_FAILURES
                        F1 and F2 need at least this many ns-3 failures in total (default 20)
  -q, --quiet           print only the checks
```

## rules

```text
usage: handoverlab rules [-h]

options:
  -h, --help  show this help message and exit
```

## init

```text
usage: handoverlab init [-h] [--force] [path]

positional arguments:
  path

options:
  -h, --help  show this help message and exit
  --force
```
