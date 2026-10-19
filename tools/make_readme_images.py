# SPDX-License-Identifier: MIT
"""Rebuild the dashboard figures shown in the README and the dashboard guide (docs/images).

Run from the repository root:  python tools/make_readme_images.py   (about two minutes; needs matplotlib)
"""
import os

from handoverlab.gui import logic

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "images")


def main() -> None:
    s = logic.Settings(layout="street_grid", blocks=2, site_spacing_m=150.0, users=30, profile="veh16",
                       duration_s=60.0, warmup_s=10.0, seeds=5, first_seed=1)
    rules = [logic.RuleSettings("a3", "A3", {"off_db": 3.0, "ttt_s": 0.16}),
             logic.RuleSettings("cho", "CHO", {"o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08})]
    out = logic.run(s, rules)
    for name, fig in (("dashboard-where.png", logic.events_map_figure(out, 0)),
                      ("dashboard-compare.png", logic.comparison_figure(out))):
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(logic.png(fig))
        print("wrote", name)


if __name__ == "__main__":
    main()
