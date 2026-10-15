# Goto Response — Theory, Measurements & Design for Flips, Unwinds and Goto Paths

Branch: `feature/equatorial_mode` (Oct 2026). Started from eq mode struggling with simple gotos (a goto to the zenith
from Sydney turned M1 a full turn down and back up), it became a study of how gotos should move in both alt/az and eq
mode.

**Read [Status and findings (2026-10-15)](#status-and-findings-2026-10-15) first.** The sections after it hold the
theory, the digital twin sweep and the hardware measurements it rests on.

---

## Status and findings (2026-10-15)

### What is built

* **Zenith fix** (`control.py` `prevent_windup`): in eq mode the unwind check judges M1/M3 travel by the target's
  motor angles, not by the change in sky Az/Roll (on a wedge M1/M3 aren't the Az/Roll axes; near the zenith Az swings
  ~90 deg for a few deg of M1). Twin test `test_goto_to_the_zenith_does_not_unwind`.
* **`utility/goto_response.py`**: a fixed sequence of 10 motor-angle gotos (2/5/30/90 deg on M1, 5/25 on M2, 5/30 on
  M3, 5 and ~30 on all three), each out from a base pose and back, with `log_position` on and each leg marked in the
  log. `--track` runs them while tracking, `--plan` checks the moves without moving, `--twin` dry-runs in the twin.
  M2 is kept within 5-70 deg and every target well inside the motor limits; Ctrl+C aborts.
* **`utility/analyse_goto_response.ipynb`** (helpers in `analyse_helpers.py`): per run, leg and motor, the
  theoretical minimum time, arrival, commanded vs measured speed, response delay, overshoot, settling, and the Kd
  analysis below.

### What the measurements show

Four runs on hardware, 2026-10-15 (`logs/archive/alpaca.jdm_Beta8.0_10_15_Goto_Response_a1.log`), level mode,
coordinated speed control, default limits (planner at 0.8 Kv, Ka 5 deg/s², Kc 0.75'):

| Run | Mode, power | Arrival - theoretical minimum (median) | Overshoot (median) | Tracking tolerance reached after 1' |
|---|---|---|---|---|
| 1 | idle, plugged in (draining: charging bug) | 7.7 s | 74' | - |
| 2 | idle, battery | 7.3 s | 77' | - |
| 3 | tracking, battery | 8.9 s | 1' small moves, 115-150' large | +5.8 s |
| 4 | tracking, charging (59 -> 69%) | 10.1 s | 1' small moves, 115-190' large | +6.4 s |

Run 4's case 15 (`m3_5_back`) was stopped by hand and is left out.

1. **The motors follow their commands** (measured / commanded speed 0.96-1.07 on large moves, all runs), whether one
   motor moves or all three: **the independence assumption holds** in these runs, on battery as well as charging.
2. **No measurable battery effect** between runs, but the motors run faster than calibrated: M1 peaks at
   10-11 deg/s against 8.92, M2 at 8-10 against 7.66 (the calibration underestimates by 10-25% at 49-69%). The
   battery % is unreliable around plugging in and out (the charging logic), so no conclusion on charge level.
3. **Idle gotos are planned but always overshoot**: about 1-1.5 deg on every move, even 2 deg ones. The measured speed
   lags the command by **0.2-0.4 s** (dead time, including the ~0.2 s age of a position sample); the plan doesn't
   allow for it, the motor falls 1-3 deg behind the plan, the PID pushes to full Kv, and the motor brakes late.
4. **Gotos while tracking aren't planned**: the reference steps toward the target (up to 12 deg along the sky path,
   `alpha_limit_step`) and the PID chases it.
   * Small moves close as a first-order decay with **τ ≈ 2 s**: a 2 deg move that could take 1.3 s takes 12-13 s.
   * The **Kd term sets that τ**. With coordinated speed control `ω_kd = -Kd (ω_fb - ω_ff)` damps the PID's own
     feedback command back toward the feed-forward (the tracking rate), so `ω_fb = Kp e / (1 + Kd)`: effective gain
     1/(1 + Kd) (measured 0.65 and 0.57 on M1 and M3 against 0.67 and 0.56), time constant (1 + Kd)/Kp = 1.5 / 1.5 /
     1.8 s, lengthened to ~2 s by the dead time and `Ke` smoothing. 5 deg to 1' is ln(300) τ ≈ 11 s.
   * Large single-motor moves reach full speed (the 12 deg lead) but have no braking plan: 2-3 deg overshoot.
   * **Combined moves are slow because the lead is measured along the sky path**: `all_30` (M1 +30, M2 +25, M3 +30)
     is Az +84, Alt +12, Roll -47 in the sky; the 12 deg lead spread over three motors keeps each one's error, and so
     its speed, small (1-5 deg/s instead of ~8). 27 s for a move that could take 6 s.
   * Settling from 1' to the tracking tolerance (Kc/20 ≈ 2.3") takes another ~6 s, with BLC pushes in it.
5. **A goto can complete while still moving**: on `m1_2_back` (run 1) M1 passed through the target at ~0.5 deg/s,
   was within 0.75' for one tick, completed, went IDLE and coasted 11' past.

### Plan from here

See [Design](#design). In order of what they gain: plan gotos while tracking too; compensate the dead time;
complete only once stopped; choose the end solution once per goto for both modes; then tune the final settle
(Kc/20, BLC).

---

## Background

How a goto's motor path is decided today:

1. `q_to_theta` picks one of the two IK branches (normal, or flipped: M1 ±180, -M2, M3 ∓180), whichever is nearer
   `LastPosition`, with a gimbal lock fallback.
2. `plan_goto` (coordinated speed control) follows a trajectory in sky space (Az/Alt when idle, RA/Dec/PA while
   tracking), giving up to the PID where the path needs a branch change; large moves while tracking aren't planned.
3. `prevent_windup` runs, every tick and in this order, UNWIND (the implied raw angle past a limit: ±360), EQ ROOM (eq
   mode: M1 turned for tracking room), LOCK/FLIP (a path through gimbal lock: straight to the motor angles) and FLIP
   (the target > 30 deg away in M1 or M3: cache it).

Each heuristic estimates motor travel its own way, some from sky angles, and they can override one another mid-goto.

---

## Theory

**A pose has a small, finite set of motor solutions.** M1-M2-M3 is a three-axis wrist: for one camera orientation
there are two IK branches (normal, and flipped: M1 ±180, -M2, M3 ∓180), but with M2's range -8 to 81.5 deg both are
valid only where |M2| ≤ 8 (the flipped branch needs -M2 in range too): outside that 16 deg slice by gimbal lock a pose
has one branch. Each solution can also have M1 and M3 a whole turn either way. So the choice is almost always the
M1/M3 turns, and the branch only in the slice. It is the same on a wedge: the wedge only changes the base -> sky
rotation (`alignQ_B2T`), not the motors' geometry.

**With independent motors the fastest move to a chosen solution is known exactly.** If each motor has its own speed
and acceleration limit and doesn't constrain the others (confirmed in the measurements above), the minimum time is
the slowest single motor's rest-to-rest time (accelerate, cruise, decelerate). Nothing beats it, and a coordinated
straight line in motor angles achieves it.

**A straight motor-space move can't cross a motor limit**: the limits form a box and a straight line between two
points inside a box stays inside it. Gimbal lock is no obstacle to a motor-space move either; it's a singularity of
the sky -> motor conversion, not of the motors.

**So an ideal free move is a discrete choice of end solution, then a straight, time-optimal motor move to it.**

Where that needs more:

* **Constrained paths**: holding Az/Alt through a roll change, or RA/Dec through a PA change, can't be faster than a
  free move. Following a fixed path as fast as each motor's limits allow is time-optimal path following (Bobrow;
  Shin & McKay, 1985), which `GotoTrajectory` approximates. Constrain the path only when what the camera sees during
  the move matters (a rotation on the same target, small corrections); slews between targets move freely.
* **Constraints that aren't motor limits**: eq mode's rig tilt, the camera or cables against the tripod, the Sun.
  These can rule out straight lines.
* **What else matters than speed**: tracking room (below) and cable wrap (M1 and M3 turning the same way) decide
  between end solutions.
* **Dead time**: with a 0.2-0.4 s delay between command and measured response, a controller chasing the measured
  position overshoots. Compare against the plan delayed by the dead time (or predict the motor forward), and brake
  that much earlier.

**Tracking room**: after a goto, tracking keeps turning the motors for hours (M1 at ~15 deg/h in eq mode; M1 and M3 in
alt/az). The same pointing reached at M1 +200 or -160 tracks identically, but if tracking drives M1 upward the first
leaves 60 deg (~4 h) before a 360 deg unwind mid-session and the second 420 deg. Choosing by tracking room is what EQ
ROOM does for M1 in eq mode.

---

## Digital twin sweep (2026-10-15)

600 seeded random gotos (start pose × target, level and eq mode, idle and tracking) in `tests/sim_digital_twin.py`,
against the theoretical minimum (planner limits). *T_best*: the fastest valid end solution; *T_chosen*: the fastest
move to the end solution the driver chose; *T_arrived*: within 1' to stay.

| | T_arrived / T_best (median, p90) | Chose a slower end solution (> 2 s lost) | Hard failures |
|---|---|---|---|
| level, idle | 1.58×, 2.94× | 2 / 90 | 18 |
| level, tracking | 1.67×, 2.98× | 9 / 116 | 18 |
| eq, idle | 1.82×, 3.46× | 22 / 107 (up to 50 s) | 39 |
| eq, tracking | 1.76×, 2.74× | 23 / 131 (up to 50 s) | 19 |

Hard failures: LIMIT, finishing > 1' off after an UNWIND, or M2 driven out of its range (eq idle: 15 / 150, M2 ending
at 106-265 deg against its 81.5 deg stop). One UNWIND remapped M3 *further* past its soft limit
(`Remap t3 -66.9 to -426.9`): the implied raw angle came from the change in sky roll, in level mode too.

* From unwound starts (M1/M3 within ±120 deg) 20-26% of level gotos and 40-48% of eq gotos struggled.
* Every goto lost ~10-12 s against the theory whatever its size: the slow arrival measured on hardware above (the
  twin's 0.35 s FAST lag matches the measured 0.4 s).
* **Speed and tracking room conflict**: in eq tracking the fastest end solution would leave < 8 h of tracking in
  24 / 131 gotos; the driver favours room (1 / 131 under 8 h). The scoring order is a decision, not a detail.
* The twin's M3 is slower than the mount's (30 deg: 19 s against 11-12 s).

---

## Design

1. **Choose the end solution once, at the start of the goto, for both modes.** Make the target pose reachable
   (below), list its motor solutions (M1/M3 turns, and the second branch only when the target's |M2| ≤ 8), drop
   those outside the motor limits or (eq) past the rig tilt on the way; score the rest lexicographically: never a
   limit, then tracking room up to a night (8 h, both modes: project the target's sky motion), then the move time,
   with cable wrap (M1/M3 the same way) as a penalty. Fix the end angles for the goto; nothing re-decides mid-goto.
   This replaces UNWIND / EQ ROOM / LOCK / FLIP during a goto; `prevent_windup` stays as the guard while tracking.
2. **Plan every goto, tracking ones too**: a time-optimal motor-space trajectory with feed-forward to where the target
   will be on arrival, then hand over to tracking. Free moves straight in motor angles; constrained paths only for
   roll/PA moves and small corrections. Removes the PID chase (τ ≈ 2 s) and the sky-path lead on combined moves.
3. **Compensate the dead time** (0.2-0.4 s): feedback against the plan delayed by the dead time, braking that much
   earlier. Removes the ~1-1.5 deg overshoot.
4. **Complete a goto only once the motors have stopped**, not on one tick within tolerance.
5. **Goto timeout from the planned time** plus a margin, not a fixed 45 s.
6. **Then tune the final settle**: Kc/20 while tracking and BLC pushes, once the overshoot is gone.

### Poses, reachability and what is left to choose

Az/Alt/Roll is only how a pose is written, and it writes some poses twice and is singular at the zenith - hence
the wrap and flip rules in `reachable_azaltroll` (`kinematics.py`). In the design a target becomes a camera
orientation (quaternion) once, and the rules separate into:

* **Altitude over the top** (vertoramas, poles): alt 120 at az is alt 60 at az + 180 with roll + 180 - the *same*
  orientation written differently. Nothing to choose: its motor solutions are the same.
* **Upside down** (roll ± 180, the same footprint): *not a choice*. Camera-up is the M3 axis and M2 keeps it within
  81.5 deg of the M1 axis (the zenith on a level base, the pole on a wedge); up and its opposite are 180 deg apart,
  so they can't both be inside that cone. Hence `altitude_to_maxroll` ≤ 81.5 deg and roll and roll ± 180 are never
  both reachable: reachability decides which one the frame gets, though M3 itself can turn fully.
* **Reachability** (M2 and M3): the reachable poses are those with a motor solution inside the limits;
  `altitude_to_maxroll`'s `cos(roll) = cos(θ2max)/cos(alt)` is that boundary written in sky angles. A target outside
  it goes to the nearest reachable pose with today's priority - pointing first, then roll (the zenith zone: directly
  below on the same azimuth) - in motor space, which also covers eq mode, where `_reachable_alpha` now goes through
  the base frame and back.
* **Continuity**: a target tracked through the zenith zone keeps its side (`test_zenith_transit.py`) - choosing once
  and holding the solution, not re-choosing as the target moves.

So per goto the choices are the M1/M3 turns, the branch in the |M2| ≤ 8 slice, and the nearest reachable pose when
the target is out of reach. Panorama panels are gotos like any other (the driver doesn't control their timing); the
existing pano, reachability and zenith transit tests (`test_pano_wrap.py`, `test_reachable_azaltroll.py`,
`test_zenith_transit.py`) define the behaviour to keep.

### Tracking in eq mode

With QUEST's alignment matching the real wedge, tracking turns the pose about the true pole and the IK spreads it
over all three motors: M1 at the sidereal rate, M2 and M3 correcting in proportion to the wedge's error (computed
from the driver's kinematics, 4 h from reachable eq poses):

| Wedge error | M1 over 4 h | M2 over 4 h | M3 over 4 h | Peak M2/M3 rate |
|---|---|---|---|---|
| none | 60.16 deg (sidereal) | 0 | 0 | 0 |
| 0.5 deg | 59.9-60.8 deg | 4-25' | 4-45' | 4-14'/h |
| 2 deg | 59.0-62.6 deg | 17-100' | 16-182' | 16-55'/h |

* M3 takes out the field rotation a misaligned wedge leaves, which a two-axis equatorial mount can't.
* M2/M3 creep at ~0.1"/s, far below the slowest SLOW speed (~21"/s): start-stop pulses (the speed controller's PWM),
  reversing direction during a night, where backlash takes up (BLC).
* Tracking room in eq mode is M1's: M2/M3 use a few degrees a night at most.
* QUEST needs syncs spread over the sky to see the pole axis error (its test uses four); with fewer, tracking drifts
  at about the error × the sidereal rate.

### Acceptance criteria

* Twin sweep (to become a test: a seeded subset in the suite, the full sweep marked slow): no LIMIT, no mid-goto
  remap, M2 never out of range, chosen end solution within 2 s of T_best except where tracking room decides, median
  arrival within 1.3× T_best.
* Hardware, `goto_response.py` idle and `--track`: median arrival - theoretical minimum under 3 s; overshoot under
  5' on moves ≤ 5 deg and under 15' on large ones; no completion while moving.
* The existing test suite passes, including the pano, reachability and zenith transit tests.

---

## Open questions

* Tracking room: 8 h in both modes? Alt/az tracking turns M1 and M3 at rates that vary with the pointing, so its room
  needs the projected motor path, not a rate.
* Battery: Kv from calibration underestimates the speed at these charges. Measure Kv live (it shows in the measured
  speed of every FAST move) or plan with a margin?
* Dead-time compensation: the delay is ~0.2 s of sample age plus the MCU's FAST lag; is it stable enough to
  compensate as a constant?
* BLC's share of the final settle while tracking: separate it with a run with BLC off.
* The twin's M3 speed: recalibrate it from these runs.
* Eq mode rig tilt: a constraint on the path, not just the end pose, once moves go straight in motor angles.
* Eq mode with a single-point alignment: how much of the wedge's error it leaves, and the drift that follows.
