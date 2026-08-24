"""
Metrics for the two standard PID test scenarios:

- "steady": undisturbed sidereal tracking -- the priority case. Just
  RMS/max/mean of position error once past the initial settle.
- "disturbance": a train of known sync-offset events -- measures
  disturbance rejection. Per event: true overshoot (the peak error *after* the
  response first crosses back through zero -- excludes the initial step itself,
  which for a 'step'-kind disturbance would otherwise dominate and isn't
  overshoot, it's the disturbance) and settling time (last moment error is
  outside the threshold band), correlated to each event by wall-clock time.
  `peak_error_arcsec` is kept alongside as a diagnostic -- roughly the raw
  event magnitude, useful as a sanity check but not the scoring metric.

Two coordinate frames are reported, from two different telemetry field pairs:

- Motor/base-frame (theta1-3, θ_sp/θ_pv) -- AXES/MOTOR_FIELDS. Useful for
  per-axis mechanical diagnosis (which motor is doing the work), but doesn't
  map 1:1 onto sky-tracking accuracy.
- Equatorial (RA/Dec/PA, Δ_sp/Δ_pv) -- EQ_AXES/EQ_FIELDS. This is what
  actually matters for tracking quality -- RA/Dec error is what shows up as
  star trailing; Position Angle error (field rotation) matters less. Prefer
  this frame when judging whether a gain change is actually an improvement.
"""
import statistics as st

AXES = ["M1_az", "M2_alt", "M3_roll"]
MOTOR_FIELDS = ("θ_sp", "θ_pv")

EQ_AXES = ["RA", "Dec", "PA"]
EQ_FIELDS = ("Δ_sp", "Δ_pv")


def _pid_records(records):
    return [r for r in records if r.get("topic") == "pid"]


def error_arcsec(r, axis_i, fields=MOTOR_FIELDS):
    sp_key, pv_key = fields
    return (r[sp_key][axis_i] - r[pv_key][axis_i]) * 3600


def _axis_stats(records, axes, fields, t_start, settle_skip_s):
    pid = _pid_records(records)
    if not pid:
        return {}
    t0 = t_start if t_start is not None else pid[0]["t"]
    steady = [r for r in pid if r["t"] - t0 > settle_skip_s]
    out = {}
    for i, axis in enumerate(axes):
        errs = [error_arcsec(r, i, fields) for r in steady]
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


def steady_state_metrics(records, t_start=None, settle_skip_s=10.0):
    """RMS/max/mean position error per axis, skipping the first settle_skip_s
    seconds after t_start (defaults to the first record's timestamp). Returns
    both frames: motor-space (M1_az/M2_alt/M3_roll keys) and equatorial
    (RA/Dec/PA keys) -- the latter is the one that reflects actual sky-tracking
    quality; treat the former as mechanical diagnosis, not the scoring metric."""
    out = _axis_stats(records, AXES, MOTOR_FIELDS, t_start, settle_skip_s)
    out.update(_axis_stats(records, EQ_AXES, EQ_FIELDS, t_start, settle_skip_s))
    return out


def _disturbance_axis_stats(records, axes, fields, event_times, threshold_arcsec, hold_s, window_after_s):
    pid = sorted(_pid_records(records), key=lambda r: r["t"])
    event_times = sorted(event_times)
    out = {}
    for i, axis in enumerate(axes):
        events = []
        for idx, ev_t in enumerate(event_times):
            # Clip at the next event so one event's settling window can't bleed into
            # the next disturbance and get misread as "still unsettled."
            next_ev_t = event_times[idx + 1] if idx + 1 < len(event_times) else None
            window_end = min(ev_t + window_after_s, next_ev_t) if next_ev_t else ev_t + window_after_s
            window = [r for r in pid if ev_t <= r["t"] < window_end]
            if not window:
                continue
            errs = [(r["t"], error_arcsec(r, i, fields)) for r in window]
            peak_error = max(abs(e) for _, e in errs)
            # True overshoot excludes the initial step itself (dominant for a 'step'-kind
            # disturbance -- the raw setpoint jump appears as a huge instantaneous error
            # before the loop has had any chance to react, which isn't overshoot, it's the
            # disturbance). Only count the peak error *after* the response first crosses back
            # through zero -- that's the genuine control-induced swing past the target.
            initial_sign = 1 if errs[0][1] >= 0 else -1
            crossing_idx = next((j for j, (_, e) in enumerate(errs) if (1 if e >= 0 else -1) != initial_sign), None)
            overshoot = max((abs(e) for _, e in errs[crossing_idx:]), default=0.0) if crossing_idx is not None else 0.0
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
                w_end = errs[-1][0]
                if w_end - last_exceed < hold_s:
                    settle_t = None   # still (or again) outside the band near the end of the window
                else:
                    settle_t = last_exceed - ev_t
            events.append({
                "event_t": ev_t,
                "overshoot_arcsec": overshoot,
                "peak_error_arcsec": peak_error,  # diagnostic: includes the step itself, ~= event magnitude
                "settling_time_s": settle_t,   # None = did not settle within window_after_s
            })
        settled = [e["settling_time_s"] for e in events if e["settling_time_s"] is not None]
        out[axis] = {
            "events": events,
            "median_settling_time_s": st.median(settled) if settled else None,
            "mean_overshoot_arcsec": st.mean([e["overshoot_arcsec"] for e in events]) if events else None,
            "mean_peak_error_arcsec": st.mean([e["peak_error_arcsec"] for e in events]) if events else None,
            "n_unsettled": sum(1 for e in events if e["settling_time_s"] is None),
        }
    return out


def disturbance_metrics(records, event_times, threshold_arcsec=3.0, hold_s=3.0, window_after_s=25.0):
    """Per-event peak overshoot and settling time, both frames (see module
    docstring) -- motor-space (M1_az/M2_alt/M3_roll) and equatorial (RA/Dec/PA,
    the one that reflects actual sky-tracking quality)."""
    out = _disturbance_axis_stats(records, AXES, MOTOR_FIELDS, event_times, threshold_arcsec, hold_s, window_after_s)
    out.update(_disturbance_axis_stats(records, EQ_AXES, EQ_FIELDS, event_times, threshold_arcsec, hold_s, window_after_s))
    return out
