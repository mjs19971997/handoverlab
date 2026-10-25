# Command line

Generated from the argument parser of `handoverlab` (`python -m handoverlab` works as well). Every command prints its own help with `-h`.

```text
usage: handoverlab [-h] [--version] {run,verify,scenarios,study,report,status,gui,rules,init} ...

System-level handover simulator.

positional arguments:
  {run,verify,scenarios,study,report,status,gui,rules,init}
    run                 run an experiment configuration
    verify              run the verification checks and print a pass/fail report
    scenarios           list the built-in scenarios or show a scenario card
    study               run or resume a study (tuning with gates, test stage, tables)
    report              write the Markdown/HTML report of a study directory
    status              finished, failed and remaining jobs of a study and the time still needed
    gui                 start the browser dashboard (pip install handoverlab[gui])
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
                        of ns-3; passed on one fresh ns-3 set with TTT 80/320 ms, failed the level
                        on one with TTT 640 ms; not a default)
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
