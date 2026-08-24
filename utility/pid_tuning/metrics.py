"""
Metrics for the two standard PID test scenarios:

- "steady": undisturbed sidereal tracking -- measures test (d), the priority
  case. Just RMS/max/mean of error_signal (theta_sp - theta_pv) once past the
  initial settle.
- "disturbance": a train of known sync-offset events -- measures test (c),
  disturbance rejection. Per event: peak overshoot and settling time (first
  moment error stays under threshold for hold_s continuously), correlated to
  each event by wall-clock time.

Axis order throughout is [M1(az), M2(alt), M3(roll)], matching theta1-3 /
the pid telemetry's θ_sp/θ_pv arrays.
"""
import statistics as st

AXES = ["M1_az", "M2_alt", "M3_roll"]


def _pid_records(records):
    return [r for r in records if r.get("topic") == "pid"]


def error_signal_arcsec(r, axis_i):
    return (r["θ_sp"][axis_i] - r["θ_pv"][axis_i]) * 3600


def steady_state_metrics(records, t_start=None, settle_skip_s=10.0):
    """RMS/max/mean position error per axis, skipping the first settle_skip_s
    seconds after t_start (defaults to the first record's timestamp)."""
    pid = _pid_records(records)
    if not pid:
        return {}
    t0 = t_start if t_start is not None else pid[0]["t"]
    steady = [r for r in pid if r["t"] - t0 > settle_skip_s]
    out = {}
    for i, axis in enumerate(AXES):
        errs = [error_signal_arcsec(r, i) for r in steady]
        if not errs:
            continue
        rms = (sum(e * e for e in errs) / len(errs)) ** 0.5
        out[axis] = {
            "n": len(errs),
            "rms_arcsec": rms,
            "max_abs_arcsec": max(abs(e) for e in errs),
            "mean_arcsec": st.mean(errs),
        }
    return out


def disturbance_metrics(records, event_times, threshold_arcsec=1.5, hold_s=3.0, window_after_s=25.0):
    """For each event time (wall-clock, matching telemetry's 't'), find the
    peak |error| in the window after it, and the settling time -- how long
    until the error is LAST outside +-threshold_arcsec (i.e. it never leaves
    the band again before the window ends, or the next event fires). If the
    error is still outside the band within hold_s of the window's end, the
    event is marked unsettled (None). Returns per-axis list of per-event
    dicts plus median/mean summaries."""
    pid = sorted(_pid_records(records), key=lambda r: r["t"])
    event_times = sorted(event_times)
    out = {}
    for i, axis in enumerate(AXES):
        events = []
        for idx, ev_t in enumerate(event_times):
            # Clip at the next event so one event's settling window can't bleed into
            # the next disturbance and get misread as "still unsettled."
            next_ev_t = event_times[idx + 1] if idx + 1 < len(event_times) else None
            window_end = min(ev_t + window_after_s, next_ev_t) if next_ev_t else ev_t + window_after_s
            window = [r for r in pid if ev_t <= r["t"] < window_end]
            if not window:
                continue
            errs = [(r["t"], error_signal_arcsec(r, i)) for r in window]
            overshoot = max(abs(e) for _, e in errs)
            # Settling time = how long until the error is LAST outside the threshold band
            # (i.e. it never leaves the band again within the window). Using "last exceedance"
            # rather than scanning forward for the first quiet hold_s window avoids locking
            # onto the pre-disturbance samples at the very start of the window, before the
            # sync's effect has even propagated into error_signal, which trivially look settled.
            exceed_times = [t for t, e in errs if abs(e) > threshold_arcsec]
            if not exceed_times:
                settle_t = 0.0
            else:
                last_exceed = max(exceed_times)
                window_end = errs[-1][0]
                if window_end - last_exceed < hold_s:
                    settle_t = None   # still (or again) outside the band near the end of the window
                else:
                    settle_t = last_exceed - ev_t
            events.append({
                "event_t": ev_t,
                "overshoot_arcsec": overshoot,
                "settling_time_s": settle_t,   # None = did not settle within window_after_s
            })
        settled = [e["settling_time_s"] for e in events if e["settling_time_s"] is not None]
        out[axis] = {
            "events": events,
            "median_settling_time_s": st.median(settled) if settled else None,
            "mean_overshoot_arcsec": st.mean([e["overshoot_arcsec"] for e in events]) if events else None,
            "n_unsettled": sum(1 for e in events if e["settling_time_s"] is None),
        }
    return out
