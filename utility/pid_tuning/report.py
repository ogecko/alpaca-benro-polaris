#!/usr/bin/env python3
"""
Generate a human-readable HTML report from results.jsonl -- one row per run,
grouped columns per axis (RMS Error / Overshoot / Settle Time x M1/M2/M3), so
runs can be compared value-by-value without paging through raw JSON.
Self-contained, no external assets except the Google Fonts stylesheet link.

Usage:
  uv run python utility/pid_tuning/report.py [-o OUTPUT.html]
"""
import argparse
import html
import json
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.jsonl"
# Equatorial (RA/Dec/PA) is the primary decision metric -- it's what actually reflects
# sky-tracking quality (RA/Dec error is star trailing; PA matters less, it's field
# rotation). Motor/base-frame (M1/M2/M3) is secondary -- useful for mechanical diagnosis
# (which axis is doing the work) but doesn't map 1:1 onto tracking accuracy.
EQ_AXES = [("RA", "RA"), ("Dec", "Dec"), ("PA", "PA")]
MOTOR_AXES = [("M1_az", "M1"), ("M2_alt", "M2"), ("M3_roll", "M3")]
AXES = EQ_AXES + MOTOR_AXES


def load_results():
    if not RESULTS_PATH.exists():
        return []
    return [json.loads(line) for line in open(RESULTS_PATH) if line.strip()]


def axis_stats(run, axis_key):
    """Return (rms, overshoot, settle, unsettled_n) for one axis of one run,
    None for whichever don't apply to this run's test type."""
    m = run.get("metrics", {}).get(axis_key)
    if not m:
        return None, None, None, 0
    if run["test"] == "steady":
        return m.get("rms_arcsec"), None, None, 0
    return None, m.get("mean_overshoot_arcsec"), m.get("median_settling_time_s"), m.get("n_unsettled", 0)


def compute_bests(rows):
    """Best (lowest) value seen per (axis, metric) across all rows, for highlighting."""
    best = {}
    for ax_key, _ in AXES:
        for metric_i in range(3):
            vals = []
            for r in rows:
                rms, ov, settle, _ = axis_stats(r, ax_key)
                v = (rms, ov, settle)[metric_i]
                if v is not None:
                    vals.append(v)
            best[(ax_key, metric_i)] = min(vals) if vals else None
    return best


def fmt_gain(gains, key):
    v = gains.get(key)
    if v is None:
        return "&mdash;"
    return "/".join(f"{x:g}" for x in v)


def fmt_kf_triple(kf_params, key, offset):
    """kf_measure_noise/kf_process_noise are 6-element [pos1,pos2,pos3,vel1,vel2,vel3]
    arrays -- pull out the M1/M2/M3 sub-triple (offset 0=pos, 3=vel) as a compact
    'x/x/x' string, 2 significant figures (these values span orders of magnitude,
    e.g. 5e-05 to 0.02, so fixed decimals would either truncate or pad uselessly --
    but this is a scan/compare display, not the source of truth, so keep it terse)."""
    v = kf_params.get(key)
    if v is None or len(v) < offset + 3:
        return "&mdash;"
    return "/".join(f"{x:.2g}" for x in v[offset:offset + 3])


def fmt_num(v, unit, decimals=2):
    if v is None:
        return '<span class="na">&mdash;</span>'
    return f'{v:.{decimals}f}<span class="unit">{unit}</span>'


PULSEGUIDE_DIR_LABEL = {0: "N", 1: "S", 2: "E", 3: "W"}


def test_badge(run):
    if run["test"] == "steady":
        return "steady", "steady"
    dp = run.get("disturbance_params", {})
    kind = dp.get("kind")
    if not kind:
        return "disturbance", "dist-unknown"
    axis = dp.get("axis")
    axis_str = f" [{html.escape(axis)}]" if axis else ""
    if kind == "pulseguide":
        direction = PULSEGUIDE_DIR_LABEL.get(dp.get("pulseguide_direction"), "?")
        duration = dp.get("pulseguide_duration_ms")
        magnitude = f"{duration:g}ms {direction}" if duration is not None else "?"
    else:
        arcsec = dp.get("event_arcsec")
        magnitude = f"{arcsec:g}&Prime;" if arcsec is not None else "?"
    return f"disturbance &middot; {kind} {magnitude}{axis_str}", f"dist-{kind}"


def build_row(run, best):
    label = html.escape(run["label"])
    run_id = html.escape(run["run_id"])
    badge_text, badge_class = test_badge(run)
    o = run["actual_orientation"]
    orientation = f"Az{o['az']:.0f}/Alt{o['alt']:.0f}/Roll{o['roll']:.0f}"
    gains = run["gains"]
    kf_params = run.get("kf_params", {})
    notes = html.escape(run.get("notes", "") or "")
    align_reset = run.get("alignment_reset", None)

    cells_html = []
    for axis_idx, (ax_key, _) in enumerate(AXES):
        rms, ov, settle, unsettled = axis_stats(run, ax_key)
        secondary = axis_idx >= len(EQ_AXES)
        major_boundary = axis_idx == len(EQ_AXES)  # divider between Equatorial and Motor groups
        for metric_i, (val, unit, dec) in enumerate([(rms, '&Prime;', 2), (ov, '&Prime;', 2), (settle, 's', 1)]):
            is_best = val is not None and best.get((ax_key, metric_i)) == val
            flag = ""
            if metric_i == 2 and unsettled:
                flag = f'<span class="flag" title="{unsettled} event(s) did not settle">&#9888;{unsettled}</span>'
            classes = ["cell"]
            if is_best:
                classes.append("best")
            if secondary:
                classes.append("secondary")
            if metric_i == 0:
                classes.append("group-start")
            if major_boundary and metric_i == 0:
                classes.append("major-boundary")
            group = "motor" if secondary else "eq"
            cells_html.append(f'<td data-group="{group}" class="{" ".join(classes)}">{fmt_num(val, unit, dec)}{flag}</td>')

    extra_lines = []
    if notes:
        extra_lines.append(f'<div class="ctx-note">{notes}</div>')
    if align_reset is False:
        extra_lines.append('<div class="ctx-warn">MPA not reset for this run</div>')

    return f'''
    <tr>
      <td class="ctx">
        <div class="ctx-top">
          <span class="ctx-label">{label}</span>
          <span class="badge {badge_class}">{badge_text}</span>
        </div>
        <div class="ctx-gains">
          <span><b>Kp</b> {fmt_gain(gains, 'pid_Kp')}</span>
          <span><b>Ki</b> {fmt_gain(gains, 'pid_Ki')}</span>
          <span><b>Kd</b> {fmt_gain(gains, 'pid_Kd')}</span>
        </div>
        <div class="ctx-gains ctx-kf">
          <span><b>KFmeas</b> P{fmt_kf_triple(kf_params, 'kf_measure_noise', 0)} V{fmt_kf_triple(kf_params, 'kf_measure_noise', 3)}</span>
        </div>
        <div class="ctx-gains ctx-kf">
          <span><b>KFproc</b> P{fmt_kf_triple(kf_params, 'kf_process_noise', 0)} V{fmt_kf_triple(kf_params, 'kf_process_noise', 3)}</span>
        </div>
        <div class="ctx-meta">{orientation} &middot; {run_id}</div>
        {"".join(extra_lines)}
      </td>
      {"".join(cells_html)}
    </tr>'''


def build_summary(rows):
    """Best steady-state RMS per axis, Equatorial (RA/Dec/PA) only -- that's the
    metric that actually reflects sky-tracking quality; M1/M2/M3 stays out of this
    summary since it's secondary/diagnostic (see AXES comment above)."""
    steady = [r for r in rows if r["test"] == "steady"]
    if not steady:
        return ""
    best_per_axis = {}
    for ax_key, ax_label in EQ_AXES:
        candidates = [(r, axis_stats(r, ax_key)[0]) for r in steady]
        candidates = [(r, v) for r, v in candidates if v is not None]
        if candidates:
            best_per_axis[ax_key] = min(candidates, key=lambda x: x[1])
    if not best_per_axis:
        return ""
    cells = []
    for ax_key, ax_label in EQ_AXES:
        if ax_key not in best_per_axis:
            continue
        r, v = best_per_axis[ax_key]
        cells.append(f'''
        <div class="summary-cell">
          <div class="summary-axis">{ax_label}</div>
          <div class="summary-value">{v:.2f}<span class="unit">&Prime; RMS</span></div>
          <div class="summary-run">{html.escape(r['label'])}</div>
        </div>''')
    return f'''
    <section class="summary">
      <h2>Best steady-state RMS seen &middot; Equatorial (RA / Dec / PA)</h2>
      <div class="summary-grid">{"".join(cells)}</div>
    </section>'''


def build_header():
    group_cells = []
    sub_cells = []
    for axis_idx, (_, ax_label) in enumerate(AXES):
        secondary = axis_idx >= len(EQ_AXES)
        major_boundary = axis_idx == len(EQ_AXES)
        group = "motor" if secondary else "eq"
        th_classes = (" secondary" if secondary else "") + (" major-boundary" if major_boundary else "")
        group_cells.append(f'<th colspan="3" data-group="{group}" class="{th_classes.strip()}">{ax_label}</th>')
        for metric_i, metric_label in enumerate(["RMS", "Overshoot", "Settle"]):
            sub_classes = []
            if metric_i == 0:
                sub_classes.append("group-start")
            if major_boundary and metric_i == 0:
                sub_classes.append("major-boundary")
            sub_cells.append(f'<th data-group="{group}" class="{" ".join(sub_classes)}">{metric_label}</th>')
    return f'''
        <tr class="group-row">
          <th class="ctx-head"></th>
          {"".join(group_cells)}
        </tr>
        <tr class="sub-row">
          <th class="ctx-head">Run</th>
          {"".join(sub_cells)}
        </tr>'''


PAGE_TEMPLATE = '''<title>TRACK PID Tuning</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root {{
  --bg: #f5f6f8;
  --surface: #ffffff;
  --surface-2: #eef0f3;
  --ink: #171b21;
  --muted: #5b6472;
  --border: #dde1e7;
  --accent: #0a7f92;
  --accent-tint: #e3f3f5;
  --cat2: #6a4fd6;
  --cat2-tint: #ece8fa;
  --good: #1e9e6b;
  --good-tint: #e6f6ef;
  --warn: #b9770e;
  --bad: #c0392b;
  --bad-tint: #fbeaea;
  --shadow: 0 1px 2px rgba(23,27,33,0.06), 0 1px 8px rgba(23,27,33,0.04);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #11151b;
    --surface: #191e26;
    --surface-2: #20262f;
    --ink: #e8ecf2;
    --muted: #8b93a3;
    --border: #2b323d;
    --accent: #4fc6d9;
    --accent-tint: #163338;
    --cat2: #a892f0;
    --cat2-tint: #292244;
    --good: #3fbe8b;
    --good-tint: #163329;
    --warn: #e0a23c;
    --bad: #e36657;
    --bad-tint: #33201d;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 4px 16px rgba(0,0,0,0.25);
  }}
}}
:root[data-theme="dark"] {{
  --bg: #11151b;
  --surface: #191e26;
  --surface-2: #20262f;
  --ink: #e8ecf2;
  --muted: #8b93a3;
  --border: #2b323d;
  --accent: #4fc6d9;
  --accent-tint: #163338;
  --cat2: #a892f0;
  --cat2-tint: #292244;
  --good: #3fbe8b;
  --good-tint: #163329;
  --warn: #e0a23c;
  --bad: #e36657;
  --bad-tint: #33201d;
  --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 4px 16px rgba(0,0,0,0.25);
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "IBM Plex Sans", system-ui, sans-serif;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}

.masthead {{ margin-bottom: 2rem; }}
.masthead-top {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.6rem;
}}
.coord-select {{
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
}}
.coord-select select {{
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 0.85rem;
  text-transform: none;
  letter-spacing: normal;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.45rem 0.7rem;
  cursor: pointer;
}}
.coord-select select:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
.masthead .eyebrow {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 0.4rem;
}}
.masthead h1 {{
  font-size: clamp(1.6rem, 3vw, 2.1rem);
  font-weight: 700;
  margin: 0 0 0.4rem;
  text-wrap: balance;
}}
.masthead p {{
  color: var(--muted);
  max-width: 62ch;
  margin: 0;
  font-size: 0.95rem;
}}

.summary {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow);
  padding: 1.4rem 1.6rem;
  margin-bottom: 2rem;
}}
.summary h2 {{
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  margin: 0 0 1rem;
  font-weight: 600;
}}
.summary-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1.5rem;
}}
.summary-axis {{ font-size: 0.8rem; color: var(--muted); margin-bottom: 0.15rem; }}
.summary-value {{
  font-family: "IBM Plex Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 1.7rem;
  font-weight: 600;
  color: var(--good);
}}
.summary-value .unit {{ font-size: 0.95rem; color: var(--muted); margin-left: 0.15rem; }}
.summary-run {{ font-family: "IBM Plex Mono", monospace; font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }}

.table-scroll {{
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow);
  background: var(--surface);
}}
table.runs {{
  border-collapse: collapse;
  width: 100%;
  min-width: 900px;
}}
table.runs[data-coord="both"] {{ min-width: 1650px; }}
table.runs th, table.runs td {{
  padding: 0.5rem 0.6rem;
  text-align: left;
  vertical-align: top;
}}
/* Coordinate-frame selector: hide the non-selected group's columns entirely.
   Default (no data-coord yet, before the init script runs) matches "eq". */
table.runs[data-coord="eq"] [data-group="motor"],
table.runs:not([data-coord]) [data-group="motor"] {{ display: none; }}
table.runs[data-coord="motor"] [data-group="eq"] {{ display: none; }}
thead .group-row th {{
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent);
  font-weight: 600;
  padding-top: 0.9rem;
  padding-bottom: 0.3rem;
  border-bottom: 1px solid var(--border);
}}
thead .group-row th.ctx-head {{ border-bottom-color: transparent; }}
thead .group-row th[colspan] {{ text-align: center; border-left: 1px solid var(--border); }}
thead .group-row th.major-boundary {{ border-left: 2px solid var(--accent); }}
thead .sub-row th {{
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--muted);
  font-weight: 600;
  padding-top: 0.2rem;
  padding-bottom: 0.6rem;
  border-bottom: 2px solid var(--border);
  text-align: center;
  white-space: nowrap;
}}
thead .sub-row th.group-start {{ border-left: 1px solid var(--border); }}
thead .sub-row th.major-boundary {{ border-left: 2px solid var(--accent); }}
thead .group-row th.secondary {{ color: var(--muted); }}

tbody tr {{ border-bottom: 1px solid var(--border); }}
tbody tr:last-child {{ border-bottom: none; }}
tbody tr:hover {{ background: var(--surface-2); }}

td.ctx {{
  min-width: 15rem;
  max-width: 19rem;
}}
.ctx-top {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.3rem; }}
.ctx-label {{ font-weight: 600; font-size: 0.92rem; }}
.badge {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.65rem;
  letter-spacing: 0.02em;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--muted);
  white-space: nowrap;
}}
.badge.steady {{ background: var(--accent-tint); color: var(--accent); }}
.badge[class*="dist-"] {{ background: var(--cat2-tint); color: var(--cat2); }}
.ctx-gains {{
  display: flex;
  flex-wrap: wrap;
  gap: 0 0.9rem;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.76rem;
  color: var(--muted);
  margin-bottom: 0.25rem;
}}
.ctx-gains b {{ color: var(--ink); font-weight: 600; margin-right: 0.15rem; }}
.ctx-gains.ctx-kf {{ font-size: 0.68rem; opacity: 0.75; margin-bottom: 0.15rem; }}
.ctx-gains.ctx-kf b {{ color: var(--muted); font-weight: 600; }}
.ctx-meta {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.7rem;
  color: var(--muted);
  opacity: 0.8;
}}
.ctx-note {{ margin-top: 0.3rem; font-size: 0.78rem; color: var(--muted); font-style: italic; }}
.ctx-warn {{ margin-top: 0.3rem; font-size: 0.72rem; color: var(--warn); }}

td.cell {{
  font-family: "IBM Plex Mono", monospace;
  font-variant-numeric: tabular-nums;
  font-size: 0.88rem;
  text-align: center;
  vertical-align: middle;
  white-space: nowrap;
  width: 4.6rem;
}}
td.cell.group-start {{ border-left: 1px solid var(--border); }}
td.cell.major-boundary {{ border-left: 2px solid var(--accent); }}
td.cell.best {{ background: var(--good-tint); color: var(--good); font-weight: 600; }}
td.cell.secondary {{ opacity: 0.7; font-size: 0.8rem; }}
td.cell.secondary.best {{ opacity: 1; }}
td.cell .unit {{ font-size: 0.72em; color: inherit; opacity: 0.7; margin-left: 0.1em; }}
td.cell .na {{ color: var(--muted); opacity: 0.4; }}
.flag {{
  display: inline-block;
  margin-left: 0.2rem;
  font-size: 0.68rem;
  color: var(--bad);
}}

@media (max-width: 720px) {{
  td.ctx {{ min-width: 12rem; }}
}}
</style>

<div class="wrap">
  <div class="masthead">
    <div class="masthead-top">
      <div>
        <p class="eyebrow">Alpaca Benro Polaris &middot; PID Tuning</p>
        <h1>TRACK-mode gain sweep</h1>
      </div>
      <label class="coord-select">
        <span>Coordinates</span>
        <select id="coordSelect" onchange="document.querySelector('table.runs').setAttribute('data-coord', this.value); try {{ localStorage.setItem('pidReportCoord', this.value) }} catch (e) {{}}">
          <option value="eq">Equatorial (RA/Dec/PA)</option>
          <option value="motor">Motor (M1/M2/M3)</option>
          <option value="both">Both</option>
        </select>
      </label>
    </div>
    <p>Every run below slews to its stated orientation, resets the alignment model for a
    clean baseline, then measures steady-state tracking error (RMS) or disturbance-rejection
    (overshoot / settling time) per axis. <b>RA / Dec / PA</b> (equatorial) is the metric that
    actually reflects sky-tracking quality &mdash; RA/Dec error is star trailing, PA matters less
    (field rotation). <b>M1 / M2 / M3</b> are the driver's raw motor/base-frame axes (theta1-3)
    &mdash; useful for mechanical diagnosis, not the scoring metric. Green cells mark the best
    value seen for that axis and metric across all runs so far. Newest run first.</p>
  </div>
  {summary}
  <div class="table-scroll">
    <table class="runs">
      <thead>
        {header}
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</div>
<script>
  (function () {{
    var saved = 'eq';
    try {{ saved = localStorage.getItem('pidReportCoord') || 'eq'; }} catch (e) {{}}
    var table = document.querySelector('table.runs');
    var select = document.getElementById('coordSelect');
    if (table) table.setAttribute('data-coord', saved);
    if (select) select.value = saved;
  }})();
</script>
'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--output", default=str(HERE / "report.html"))
    args = p.parse_args()

    rows = load_results()
    rows.sort(key=lambda r: r["timestamp"], reverse=True)
    best = compute_bests(rows)

    n_cols = 1 + len(AXES) * 3
    rows_html = "\n".join(build_row(r, best) for r in rows) if rows else \
        f'<tr><td colspan="{n_cols}" style="color:var(--muted); text-align:center; padding:2rem;">No runs yet.</td></tr>'
    summary_html = build_summary(rows)
    header_html = build_header()

    out = PAGE_TEMPLATE.format(rows=rows_html, summary=summary_html, header=header_html)
    Path(args.output).write_text(out)
    print(f"wrote {args.output} ({len(rows)} runs)")


if __name__ == "__main__":
    main()
