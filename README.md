# HandoverLab

A system-level simulator for studying handover in dense 5G and beyond-5G networks, written in Python.

> **Status: early development.** The code is being built in stages. Interfaces may change until the first release.

## Goals

- Street-grid and open-area scenarios following 3GPP TR 37.885 / TR 38.901 assumptions
- Mobility, blockage, measurement and handover models in one readable Python package
- Pluggable handover algorithms (A3, conditional handover, and your own)
- Fair comparisons: equal tuning effort, paired seeds, and an automatic check that tuned settings are not at the edge of their tuning range
- Reproducible runs on Windows, Linux and macOS
- A browser dashboard for setting up scenarios and watching results, next to a command-line mode for batch runs

## Licence

MIT. See [LICENSE](LICENSE).

## Authors

Mostafa Jalili Sanjarani and Yasser Elmi Sola
