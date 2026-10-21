# SPDX-License-Identifier: MIT
"""The same handover rule under the four traffic models of HandoverLab (traffic.model, since 1.4.0).

Run it:  python examples/traffic_models.py
"fixed" keeps the constant service rates; "full_buffer" lets every user take what the link carries;
"periodic" sends a small packet every 20 ms (as VoIP); "ftp3" downloads 0.5 Mbyte files that arrive
at random (TR 36.814 FTP model 3).  The busier the cells, the stronger the interference and the
lower the SINR. One seed gives only a few failures; compare failure rates over several seeds.
"""
import handoverlab as hl

base = hl.builtin_scenario("urban-grid-10ghz").with_overrides({
    "mobility.users": 30, "run.duration_s": 60.0, "run.warmup_s": 10.0})
rule = [{"rule": "a3", "name": "A3", "off_db": 3.0, "ttt_s": 0.16}]

print("model        cell load  rate [Mbit/s]  delivered  SINR [dB]  failures/UE-min")
for model, extra in (("fixed", {}), ("full_buffer", {}), ("periodic", {}), ("ftp3", {"traffic.ftp_rate_hz": 1.0})):
    sc = base.with_overrides(dict({"traffic.model": model}, **extra))
    m = hl.simulate(sc, rule, seeds=[1])[0].metrics
    print("%-12s %9.2f %14.2f %10.2f %10.1f %16.2f" % (model, m["mean_load"], m["rate_mbps"], m["delivered_share"],
                                                       m["sinr_db"], m["failures_pm"]))
