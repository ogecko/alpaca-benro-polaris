# -----------------------------------------------------------------------------
# tracking_restore.py - carry tracking on through a driver restart
# -----------------------------------------------------------------------------
#
# The driver never stops the motors when it exits or restarts (a long session should carry on through a comms loss,
# and another driver may be controlling the mount). While it is down the Polaris keeps running the last SLOW command
# it was sent -- not tracking: the coordinated speed controller tracks by switching between SLOW levels, so the
# frozen command can be off the needed rate by up to a level (L1 0.0059 dps = 21"/s per motor).
#
# So the driver keeps its tracking state in data/tracking_state.json (target, time, Polaris session fingerprint)
# and, with restore_tracking_on_restart on, picks it up again when it restarts: it sets the saved target and TRACK,
# and the PID pulls the mount back onto it (on the twin a 3.5 deg catch-up settles in ~12 s, as fast as a goto).
#
# It restores only when it is safe to assume the mount and the sky still match the saved state:
#   - the driver was tracking when last saved, less than MAX_AGE_S ago,
#   - the Polaris is in the same session: theta_raw (518) - zeta (517) per motor unchanged (the firmware's box
#     attitude -- tilt at power-on and the compass / SPA heading -- is re-set by a power cycle or calibration),
#   - the mount is not parked / at a limit / in PRESETUP, advanced control and tracking are on,
#   - the target is above MIN_ALT_DEG now.
# Otherwise it does not restore and, if the mount is moving (the last SLOW command still running), stops it -- a
# driver that is actually in control will just command it again.
# -----------------------------------------------------------------------------

import datetime
import json
import os
import time

from config import DATA_DIR

TRACKING_STATE_PATH = DATA_DIR / 'tracking_state.json'
MAX_AGE_S = 600.0                 # restore only a state saved less than this long ago (10 min)
SESSION_TOL_DEG = 0.1             # 518 - 517 offset change (any motor) that means a new Polaris session
MIN_ALT_DEG = 0.0                 # don't restore a target below this altitude
SAVE_EVERY_S = 10.0               # while tracking, save at least this often (and at once on any change)
MOVING_DEG = 0.005                # a motor angle change over MOTION_WINDOW_S above this = the mount is moving
MOTION_WINDOW_S = 3.0             # (the slowest SLOW level, L1 0.0059 dps, turns 0.018 deg in 3 s)


def capture(tracking, pid, trackingrate, zeta_raw_offset, now=None):
    """The state to save: whether the driver is tracking, the target (RA/Dec/PA setpoint and the jog / pano offsets
    the PID adds to it, or an orbital target), the time and the Polaris session fingerprint."""
    state = {'tracking': bool(tracking), 'saved_at': time.time() if now is None else now,
             'saved': datetime.datetime.now().isoformat(timespec='seconds'),
             'zeta_raw_offset': None if zeta_raw_offset is None else [round(float(x), 5) for x in zeta_raw_offset]}
    if tracking:
        state.update({'delta_sp': [round(float(x), 7) for x in pid.delta_sp],
                      'delta_offst': [round(float(x), 7) for x in pid.delta_offst],
                      'alpha_offst': [round(float(x), 7) for x in pid.alpha_offst],
                      'gamma_offst': [round(float(x), 7) for x in pid.gamma_offst],
                      'trackingrate': int(trackingrate), 'orbital': getattr(pid, 'orbital_sp_name', None)})
    return state


def change_key(state):
    """What makes a state worth saving at once: tracking on/off and the target (not the time)."""
    return json.dumps({k: v for k, v in state.items() if k not in ('saved_at', 'saved', 'zeta_raw_offset')},
                      sort_keys=True)


def save(state, path=None):
    """Write atomically: a restart part-way through a write must not leave a broken file."""
    path = str(path or TRACKING_STATE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def load(path=None):
    """The saved state, or None if there is none or it can't be read."""
    try:
        with open(str(path or TRACKING_STATE_PATH)) as f:
            state = json.load(f)
        return state if isinstance(state, dict) else None
    except (OSError, ValueError):
        return None


def refuse_reason(state, now, zeta_raw_offset, pid_mode, atpark, advanced, target_alt=None):
    """Why the saved state must not be restored, or None to restore it. now: time.time()."""
    if state is None:
        return 'no saved tracking state'
    if not state.get('tracking'):
        return 'the driver was not tracking when it stopped'
    if not advanced:
        return 'advanced control / tracking is off'
    age = now - float(state.get('saved_at', 0))
    if age > MAX_AGE_S or age < -60:
        return f'the saved state is {age / 60:.0f} min old (restore within {MAX_AGE_S / 60:.0f} min)'
    saved, current = state.get('zeta_raw_offset'), zeta_raw_offset
    if saved is None or current is None:
        return 'no Polaris session fingerprint (518 - 517 offset) to compare'
    moved = max(abs((s - c + 180.0) % 360.0 - 180.0) for s, c in zip(saved, current))
    if moved > SESSION_TOL_DEG:
        return f'the Polaris was restarted or re-calibrated since (518 - 517 offset changed {moved:.2f} deg)'
    if atpark or pid_mode in ('PARK', 'PARKING', 'LIMIT', 'PRESETUP', 'HOMING'):
        return f'the mount is {"parked" if atpark else pid_mode}'
    if target_alt is not None and target_alt < MIN_ALT_DEG:
        return f'the target is below the horizon now (alt {target_alt:.1f} deg)'
    return None


def is_moving(zeta_before, zeta_after):
    """True if any motor angle (517, deg) changed by more than MOVING_DEG between the two samples."""
    if zeta_before is None or zeta_after is None:
        return False
    return any(abs((a - b + 180.0) % 360.0 - 180.0) > MOVING_DEG for a, b in zip(zeta_after, zeta_before))
