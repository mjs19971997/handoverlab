# SPDX-License-Identifier: MIT
"""HandoverLab dashboard (Streamlit page).  Start it with ``handoverlab gui``.

The page only lays out widgets and shows what :mod:`handoverlab.gui.logic`
computes; all logic lives there.
"""
import time

import streamlit as st

from handoverlab import __version__
from handoverlab.gui import logic


def _rule_widgets(i: int, default: str) -> logic.RuleSettings:
    with st.container(border=True):
        c1, c2 = st.columns([1, 1])
        key = c1.selectbox("Rule %d" % (i + 1), list(logic.RULES), index=list(logic.RULES).index(default),
                           format_func=lambda k: logic.RULES[k], key="r%d_rule" % i)
        name = c2.text_input("Name", value="%s-%d" % (key.upper(), i + 1), key="r%d_name_%s" % (i, key))
        params = {}
        cols = st.columns(len(logic.RULE_PARAMS[key]))
        for col, (p, (label, lo, hi, step, val)) in zip(cols, logic.RULE_PARAMS[key].items()):
            params[p] = col.slider(label, lo, hi, val, step, key="r%d_%s_%s" % (i, key, p))
        return logic.RuleSettings(key, name, params)


def main() -> None:
    """The page (run by Streamlit as the main script)."""
    st.set_page_config(page_title="HandoverLab", layout="wide")
    # ------------------------------------------------------------------------ sidebar: scenario
    sb = st.sidebar
    sb.title("HandoverLab")
    sb.caption("Version %s. Runs on this computer; nothing is sent anywhere." % __version__)
    sb.header("Scenario")
    layout = sb.radio("Layout", list(logic.LAYOUTS), format_func=lambda k: logic.LAYOUTS[k])
    blocks = sb.slider("Blocks per side", 1, 4, 2, help="The grid has blocks x blocks building blocks of "
                       "433 m x 250 m (TR 37.885); the open area has the same size without buildings.")
    spacing = sb.slider("Site spacing [m]", 50, 300, 150, 10)
    carrier = sb.select_slider("Carrier frequency [GHz]", options=list(logic.FREQUENCIES), value=10.0)
    pathloss = sb.selectbox("Path loss (TR 38.901)", list(logic.PATHLOSS), format_func=lambda k: logic.PATHLOSS[k])
    sb.header("Users")
    users = sb.slider("Users", 2, 80, 20)
    profile = sb.selectbox("Speed profile", list(logic.PROFILES), index=2, format_func=lambda k: logic.PROFILES[k])
    traffic = sb.selectbox("Traffic", list(logic.TRAFFIC), format_func=lambda k: logic.TRAFFIC[k])
    sb.header("Run")
    duration = sb.slider("Run length [s]", 10, 180, 40, 5)
    warmup = sb.slider("Warm-up, not counted [s]", 0, 60, 10, 5)
    seeds = sb.slider("Seeds", 1, 10, 3, help="Every rule runs on the same world per seed (paired comparison); "
                      "confidence intervals need two or more.")
    first_seed = sb.number_input("First seed", 0, 10**6, 1)
    settings = logic.Settings(layout, blocks, float(spacing), float(carrier), pathloss, users, profile, float(duration),
                              float(warmup), seeds, int(first_seed), traffic)

    # ---------------------------------------------------------------------------- main: rules and run
    st.title("Handover dashboard")
    st.write("Choose the scenario on the left and the handover rules below, then run. Every rule runs on the same "
             "radio samples, so differences come only from the rules.")
    with st.expander("Handover rules", expanded=True):
        n_rules = st.radio("Number of rules", [1, 2, 3, 4], index=1, horizontal=True)
        rules = [_rule_widgets(i, "a3" if i % 2 == 0 else "cho") for i in range(n_rules)]

    problems = settings.check()
    for p in problems:
        st.error(p)
    if st.button("Run", type="primary", disabled=bool(problems)):
        bar = st.progress(0.0, text="starting")
        try:
            def progress(share, text):
                bar.progress(min(share, 1.0), text=text)
            st.session_state["outcome"] = logic.run(settings, rules, progress=progress)
            st.session_state["experiment"] = logic.experiment_yaml(settings, rules)
            bar.progress(1.0, text="done in %.1f s" % st.session_state["outcome"].seconds)
        except ValueError as e:
            bar.empty()
            st.error(str(e))

    out = st.session_state.get("outcome")
    if out is None:
        st.info("No results yet: press Run. A run of the default settings takes a few seconds.")
        return

    st.caption("Results of the last run: %s, %d users (%s), %d seed(s), %.0f s; %s." % (
        logic.LAYOUTS[out.settings.layout], out.settings.users, out.settings.profile, out.settings.seeds,
        out.settings.duration_s, ", ".join(out.rule_names)))
    tab_map, tab_events, tab_cmp, tab_charts, tab_table, tab_study, tab_dl = st.tabs(
        ["Map", "Where", "Compare", "Charts", "Table", "Study", "Downloads"])

    with tab_map:
        c1, c2, c3 = st.columns([2, 5, 1])
        rule_i = c1.selectbox("Rule", range(len(out.rule_names)), format_func=lambda i: out.rule_names[i])
        step = float(out.times[1] - out.times[0])
        t_end = float(out.times[-1])
        frame = c2.slider("Time [s]", 0.0, t_end, min(float(out.settings.warmup_s), t_end), step)
        play = c3.button("Play")
        m1, m2 = st.columns([3, 1])
        holder = m1.empty()
        info = m2.empty()
        k = int(round(frame / step))
        for f in (range(k, len(out.times)) if play else [k]):
            holder.pyplot(logic.map_figure(out, rule_i, f), clear_figure=True)
            cnt = logic.counts_until(out, rule_i, float(out.times[f]))
            info.dataframe({"so far (seed %d)" % out.settings.first_seed: list(cnt), "count": list(cnt.values())},
                           hide_index=True)
            if play:
                time.sleep(0.05)
        m1.caption("Users of the first seed (seed %d). Triangles are sites (numbered), lines join each user to its "
                   "serving site; near cells have different colours. Grey users are executing a handover or "
                   "re-establishing after a failure." % out.settings.first_seed)

    with tab_events:
        ev_rule = st.selectbox("Rule ", range(len(out.rule_names)), format_func=lambda i: out.rule_names[i])
        st.pyplot(logic.events_map_figure(out, ev_rule), clear_figure=True)
        st.caption("Grey lines are the paths of the users of the first seed. Dots mark handovers, circles "
                   "unnecessary handovers and crosses failures, at the place where they happened.")

    with tab_cmp:
        st.pyplot(logic.comparison_figure(out), clear_figure=True)
        st.dataframe(logic.comparison_rows(out), hide_index=True)
        st.caption("Each rule against the first one on the same worlds (paired over the seeds); 'significant' "
                   "means that the 95 % interval of the difference excludes zero. Use several seeds.")

    with tab_study:
        folder = st.text_input("Study folder", help="The output folder of `handoverlab study`; this shows what "
                               "`handoverlab status` prints, also while the study runs.")
        if folder:
            st.code("\n".join(logic.study_status_lines(folder)), language=None)

    with tab_charts:
        st.pyplot(logic.metrics_figure(out), clear_figure=True)
        c1, c2 = st.columns(2)
        c1.pyplot(logic.causes_figure(out), clear_figure=True)
        c2.pyplot(logic.timeline_figure(out), clear_figure=True)

    with tab_table:
        st.dataframe(logic.summary_rows(out), hide_index=True)
        st.caption("Means over the seeds; rates per UE-minute of the measured part (after the warm-up). Metric "
                   "definitions: the user guide, section 7.")

    with tab_dl:
        st.write("Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.download_button("Metrics (CSV)", logic.metrics_csv(out), "metrics.csv", "text/csv")
        c2.download_button("Results (JSON)", logic.results_json(out), "results.json", "application/json")
        c3.download_button("Event logs (CSV)", logic.events_csv(out), "events.csv", "text/csv")
        c4.download_button("Traces, first seed (CSV)", logic.trace_csv(out), "trace.csv", "text/csv")
        st.download_button("Comparison with intervals (CSV)", logic.comparison_csv(out), "comparison.csv", "text/csv")
        st.write("Figures")
        c1, c2, c3, c4 = st.columns(4)
        c1.download_button("Map at the chosen time (PNG)", logic.png(logic.map_figure(out, rule_i, k)), "map.png",
                           "image/png")
        c2.download_button("Metrics (PNG)", logic.png(logic.metrics_figure(out)), "metrics.png", "image/png")
        c3.download_button("Failure causes (PNG)", logic.png(logic.causes_figure(out)), "causes.png", "image/png")
        c4.download_button("Timeline (PNG)", logic.png(logic.timeline_figure(out)), "timeline.png", "image/png")
        c1, c2 = st.columns(2)
        c1.download_button("Where handovers happen (PNG)", logic.png(logic.events_map_figure(out, rule_i)),
                           "where.png", "image/png")
        c2.download_button("Comparison (PNG)", logic.png(logic.comparison_figure(out)), "comparison.png", "image/png")
        st.write("Experiment file: repeat this run with `handoverlab run dashboard.yaml`")
        st.download_button("Experiment (YAML)", st.session_state.get("experiment", ""), "dashboard.yaml", "text/yaml")


# Streamlit runs this file as __main__; a worker process that imports it as __mp_main__ shows nothing.
if __name__ == "__main__":
    main()
