# SPDX-License-Identifier: MIT
"""Browser dashboard (optional extra ``gui``): ``pip install handoverlab[gui]``, then ``handoverlab gui``.

The dashboard runs on your own computer: ``handoverlab gui`` starts a local
Streamlit server (default http://localhost:8501) and opens it in the browser.
No account, server or domain is needed.  It lets you choose a scenario
(street grid or open area, speed profile, carrier frequency, path loss,
users, run length, seeds) and up to four handover rules with their
parameters, runs them with a progress bar, shows the users moving on the
layout coloured by their serving cell, charts of handovers, failures and
rate, a table of metrics, and offers the results (CSV, JSON, event logs,
traces), the figures (PNG) and an experiment file for ``handoverlab run``
as downloads.

Only :mod:`handoverlab.gui.app` imports Streamlit; the logic behind it
(:mod:`handoverlab.gui.logic`) needs NumPy and matplotlib only, and the core
package does not depend on either.
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")


def streamlit_args(port: int = 8501, headless: bool = False, address: str = "localhost") -> List[str]:
    """Command-line arguments of ``streamlit run`` for the dashboard."""
    return ["run", APP, "--server.port", str(int(port)), "--server.address", address,
            "--server.headless", "true" if headless else "false", "--browser.gatherUsageStats", "false",
            "--theme.base", "light", "--global.developmentMode", "false",
            "--client.toolbarMode", "minimal"]


def launch(port: int = 8501, headless: bool = False, address: str = "localhost",
           argv: Optional[List[str]] = None) -> int:
    """Start the dashboard server in this process (blocks until it is stopped with Ctrl+C)."""
    try:
        from streamlit.web import cli as stcli
    except ImportError as e:
        print("error: the dashboard needs Streamlit and matplotlib: pip install \"handoverlab[gui]\" (%s)" % e,
              file=sys.stderr)
        return 2
    sys.argv = ["streamlit"] + (argv if argv is not None else streamlit_args(port, headless, address))
    try:
        stcli.main()
    except SystemExit as e:                                   # click ends with SystemExit
        return int(e.code or 0)
    return 0


__all__ = ["APP", "launch", "streamlit_args"]
