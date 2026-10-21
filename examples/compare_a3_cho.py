"""Compare A3 and conditional handover on the TR 37.885 street grid (3 x 3 blocks)."""
import handoverlab as hl

scenario = hl.Scenario.from_dict({
    "layout": {"kind": "street_grid", "blocks": [3, 3], "site_spacing_m": 150.0},
    "mobility": {"users": 20, "profile": "v60"},
    "run": {"duration_s": 60.0, "warmup_s": 10.0},
})
rules = [
    {"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16},
    {"rule": "cho", "name": "CHO", "o_prep_db": -2.0, "o_exec_db": 3.0, "ttt_exec_s": 0.08},
]
results = hl.simulate(scenario, rules, seeds=[1])   # both rules run on the same world

print("rule   handovers  unnecessary  failures  prepared   (per UE-minute)")
for r in results:
    m = r.metrics
    print("%-6s %9.2f %12.2f %9.2f %9.3f" % (r.rule, m["handovers_pm"], m["unnecessary_pm"],
                                            m["failures_pm"], m["prepared_cells_mean"]))
