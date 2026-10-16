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
* **`driver/control_plan.py`** (2026-10-17): the goto planning module (R3). `GotoTrajectory`, `MotorTrajectory` and
  `ramp_rates` moved out of `control.py` unchanged; `min_move_time` added. `kinematics.theta_solutions` lists every
  motor solution of a pose within the limits.
* **`tests/test_control_plan.py`**: the twin sweep as a test, with the acceptance criteria as xfail tests (see
  [the baseline](#the-sweep-as-a-test-todays-baseline-2026-10-17)).
* **`utility/analyse_span.ipynb`** eq sections: reachability, PA (upright and upside down), the tripod cone and
  latitude.

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
(Kc/20, BLC). Throughout: the [requirements](#requirements-2026-10-16) - no path into the tripod cone, gotos
interruptible from a moving state, new code in `control_plan.py` / `kinematics.py` reusing what exists, with
FAST speed calibration re-enabled, and planning that never blocks the 200 ms tick on a Pi Zero 2 W or N1505.

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
  Shin & McKay, 1985), which `GotoTrajectory` approximates. Constrain the path when what the camera sees during the
  move matters (a rotation on the same target, small corrections); slews between targets move freely.
* **A rotation must keep the pointing**, or the pose is lost: M3 turns the camera about camera-up (the M3 axis), so M3
  alone pans the boresight - a roll or PA change is never a single-motor move but M1, M2 and M3 together, and a
  straight motor-space move to the rotated pose swings the pointing far from the Az/Alt or RA/Dec on the way.
  Rotations (and the rotation part of a goto) follow the pointing-held path.
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

### The sweep as a test: today's baseline (2026-10-17)

`tests/test_control_plan.py` rebuilds the sweep (the 2026-10-15 harness was lost with its scratchpad): 10 seeded
gotos per case in the suite, 150 per case with `--runslow` (`-k report -s` prints the table, `GOTO_SWEEP_CSV=path`
saves every goto). The acceptance criteria are its tests, xfail until the redesign passes them. It differs from the
first sweep, so the numbers aren't directly comparable: start poses spread over M1's whole range (motor angle -60 to
420), any requested roll, T_best at full Kv (the planner runs at 0.8 Kv, so even a perfect plan of today's design
scores ≥ 1.25×), and *arrived* meaning within 2' when the driver reports the goto complete. The end solutions come
from `kinematics.theta_solutions`, the move times from `control_plan.min_move_time`; *kinematics/tick* counts the
control loop's and the planner's kinematics calls in one tick (R4: counted, not timed).

| | Arrived | Arrival / best (median, p90) | Chose > 2 s slower (room excuses) | LIMIT | Remapped mid-goto | Missed, at the 45 s timeout | Kinematics / tick (max) |
|---|---|---|---|---|---|---|---|
| level, idle | 102 / 150 | 2.10×, 3.02× | 6 (0) | 29 | 41 | 37 | 1379 |
| level, tracking | 138 / 150 | 2.59×, 4.74× | 0 | 2 | 29 | 12 | 376 |
| eq, idle | 91 / 150 | 2.33×, 7.72× | 29 (0) | 48 | 75 | 45 | 1393 |
| eq, tracking | 131 / 150 | 3.11×, 7.81× | 36 (32) | 13 | 86 | 17 | 394 |

* **Most misses end at the fixed 45 s goto timeout**, which marks the goto complete wherever the mount is (111 of
  138). Traced: UNWIND remaps send M1 a full turn the long way, or past its limit (`Remap t1 +415.4 to +775.4`, M1
  then heading for +775 against its +450), and the timeout ends it 9-160 deg off.
* **LIMIT**: the motors pass their raw limits in 92 gotos. The twin has no hard stops, so M2 can swing on past its
  stop (to 117-180 deg in 20 level gotos: the "rig tilt" there is M2 itself).
* **Tripod cone**: entered in 2 eq gotos. Rig tilt passed 100 deg in 92 eq idle and 69 eq tracking gotos.
* **Planning work**: the first tick of an idle goto does ~1,380 kinematics calls (the 201-sample plan plus the
  91-sample gimbal lock check, several calls each), a tracking goto's ~380; a normal tick does a handful. The
  provisional budget in the test is 40 per tick.
* Room excuses: in eq tracking 32 of the 36 slower choices leave the best end solution short of a night's M1 room,
  as the first sweep found; the rest of the slower choices aren't excused.

---

## Design

1. **Choose the end solution once, at the start of the goto, for both modes.** Make the target pose reachable
   (below), list its motor solutions (M1/M3 turns, and the second branch only when the target's |M2| ≤ 8), drop
   those outside the motor limits or (eq) past the rig tilt on the way; score the rest lexicographically: never a
   limit, then tracking room up to a night (8 h, both modes: project the target's sky motion), then the move time,
   with cable wrap (M1/M3 the same way) as a penalty. Fix the end angles for the goto; nothing re-decides mid-goto.
   This replaces UNWIND / EQ ROOM / LOCK / FLIP during a goto; `prevent_windup` stays as the guard while tracking.
2. **Plan every goto, tracking ones too**: a time-optimal trajectory with feed-forward to where the target will be on
   arrival, then hand over to tracking. Removes the PID chase (τ ≈ 2 s) and the sky-path lead on combined moves.
   The path depends on how far the pointing moves (agreed 2026-10-17):
   * **Pointing moves 15 deg or less** (`goto_controlled_path_deg`, the angle between the two pointings) **and every
     roll/PA-only change: a controlled pointing path.** The pointing travels the great circle from start to target
     (RA/Dec while tracking), and roll/PA changes in proportion to progress along it, so the rotation never swings
     the pointing off that natural path (a straight motor move would: M3 alone pans the pointing). As fast as the
     motors allow along that path (path following, `GotoTrajectory` today). If the twin sweep shows these moves much
     slower than straight ones, allow the pointing a small corridor around the great circle (e.g. 1 deg or a few % of
     the move) for the motors to cut corners.
   * **Pointing moves more than 15 deg: fast and straight in motor angles**, closed-form per motor from the current
     state; the path through the sky isn't controlled. Path checks (tripod cone, rig tilt) apply here; a controlled
     path of 15 deg or less between targets above the horizon stays within 15 deg of them and can't reach the cone.
   * **Fallback**: a controlled path that needs an IK branch change or passes the motor limits goes straight instead.
   * Redirects mid-goto (R2) can switch between the two, both starting from the current motor speeds.
3. **Compensate the dead time** (0.2-0.4 s): feedback against the plan delayed by the dead time, braking that much
   earlier. Removes the ~1-1.5 deg overshoot.
4. **Complete a goto only once the motors have stopped**, not on one tick within tolerance.
5. **Goto timeout from the planned time** plus a margin, not a fixed 45 s.
6. **Then tune the final settle**: Kc/20 while tracking and BLC pushes, once the overshoot is gone.

### Requirements (2026-10-16)

The design must also meet these three requirements.

**R1. Tripod collision prevention.** The tripod fills the cone around the nadir: altitude -81.5 to -90 deg, at any
azimuth. On a level mount the motors can't reach it: M2's 81.5 deg limit holds the boresight within -81.5 to +81.5
deg altitude, so this mode is unaffected. A wedge tilts that range: M2's limit is now measured from the M1 axis (the
pole), and the nadir comes within reach.

* **Which poses.** The clearest description is in sky terms, by two directions of the pose:
  * **boresight nadir distance**: the angle from the nadir to where the lens points (= 90 + boresight altitude). The
    tripod cone is nadir distance < 8.5 deg (`tripod_cone_deg`, new; 8.5 is the level mount's own margin, so alt/az
    poses never trip it; set it larger from the rig's measured clearance for long lenses).
  * **rig tilt**: the angle of camera-up (the M3 axis) from the zenith. This is `rig_tilt_deg` and
    `eq_rig_tilt_limit`, which already exist (the rig hanging under the Polaris).

  These are separate constraints. Every pose in the tripod cone has a rig tilt of 81.5-98 deg (camera-up is roughly
  horizontal when the lens points down), so `eq_rig_tilt_limit` ≤ 81.5 would exclude the cone too, but at a cost of
  much of the PA range near the poles. The tripod cone is the narrow constraint that must always apply.
* **In motor terms** (Sydney wedge, lat -33.9, computed from the driver's kinematics on a 5 deg grid): 0.46% of
  motor space points into the cone. Every such pose has |M2| ≥ ~25 deg and M1 + M3 within about ±40 deg of 180.
  Few end poses are lost, but a straight motor-angle move between two clear poses can pass through it.
* **What the planner must do.** Every planned path, braking and interrupted paths included (R2), is checked for
  boresight nadir distance (and rig tilt) along its length, not only at its end. If a path enters the cone, the
  planner tries the other end solutions (item 1). If none is clear, it adds a waypoint around the cone. If no route
  is clear, the goto is refused with a warning; the planner never clips mid-move. A target inside the cone goes to
  the nearest pose on the cone's edge, as reachability does for other targets out of reach.
* **Tracking** into the cone (a target setting below the tripod) stops at its edge, as at the motor limits.

**R2. Fully interruptible gotos.** A goto in progress can be redirected mid-flight: a new SlewTo/target, a sync, a
tracking change, AbortSlew, or an orbital's moving setpoint.

* **Replan from the current state, not from rest.** Each motor's position and velocity (the measured θ_pv and ω, and
  the commands still in flight during the dead time, i.e. the state predicted one dead time ahead) are the start of
  the new trajectory. A motor moving away from the new target first brakes within Ka, and that braking time and
  distance count in the plan.
* **The end solution is chosen again** for the new target, scored from that moving state. An interruption is a new
  goto: "choose once" applies per goto, never mid-goto for the same target. Reversing a fast-moving M1 can cost more
  than a slightly worse solution in its direction of travel, and the scoring has to see that.
* **No step in the commands.** The speed commands stay continuous across the replan (within Ka), and the dead-time
  compensation (item 3) carries over.
* Abort is the same planner with "stop" as the target: a planned stop within Ka, not a hard stop. Afterwards the
  goto completes only once stopped (item 4).
* `GotoTrajectory` already replans "from the current speed" on retarget (per path, not per motor); build on that
  rather than writing a new planner.

**R3. Architecture consistency.** Put new code where the existing modules say it belongs, reuse existing functions,
and minimise duplication:

| Concern | Module | Reuse / move |
|---|---|---|
| Goto planning: end-solution choice, scoring, trajectories, path checks (R1), replanning (R2), timeout | `control_plan.py` (new) | move `GotoTrajectory`, `MotorTrajectory`, `ramp_rates` out of `control.py`; `plan_goto` stays the PID's hook and calls it |
| Kinematics: IK solutions (both branches, M1/M3 turns), reachability, boresight nadir distance, rig tilt geometry | `kinematics.py` | extend `q_to_theta` / `LastPosition`, `reachable_azaltroll`, `altitude_to_maxroll`, `theta_to_jacobian`; move `rig_tilt_deg` here from `control_eq.py` |
| Eq mode policy: wedge alignment, tracking room, rig tilt limiting | `control_eq.py` | `wedge_alignQ_B2T`, `limit_rig_tilt`, `eq_theta1_with_room` (as a scoring input) |
| Motor speeds and accelerations (Kv, Ka, SLOW/FAST) | `speed_controller.py` | `RateUnits`, `_speeds_at`; the planner reads its limits from here, no second speed table |
| Backlash, PEC | `control_backlash.py`, `control_pec.py` / `control_worm.py` | unchanged |
| Twin and tests | `tests/sim_digital_twin.py`, `tests/test_control_plan.py` (new) | twin sweep as a test; existing `test_goto_trajectory.py` cases move with the trajectories |

* Before adding a function, search for an existing one (`wrap180`, `angular_difference`,
  `calculate_angular_velocity`, `theta_to_jacobian`, `quaternion_difference` ...). Any new module is reviewed for
  duplicates of existing code before it's committed.
* Config keys follow the existing names and comments in `config.toml` (`tripod_cone_deg` beside
  `eq_rig_tilt_limit`).
* **Speed calibration, FAST commands only.** `CalibrationManager` was marked deprecated when the coordinated speed
  controller came in, and `RateUnits` now uses only the baseline FAST points. The measurements show those
  underestimate the speed by 10-25% (M1 10-11 deg/s against 8.92), and a time-optimal plan is only as good as its Kv.
  Re-enable the SpeedTest calibration (`moveaxis_speed_test`, Pilot's Speed Calibration page) for the FAST speed
  units only (RAW 200-2500 per axis), and feed the approved points to `RateUnits` in place of the baseline. The SLOW
  levels keep the firmware table. The worm profile row stays as it is.

**R4. Platform performance.** The driver runs on Windows, macOS, Linux and Raspberry Pi OS. The minimum hardware is
a **Raspberry Pi Zero 2 W** (4 × Cortex-A53 at 1 GHz, 512 MB) and an **Intel N1505** mini PC. Goto planning must
have minimal impact on the 200 ms control loop and speed controller on that hardware.

* **The current planner as a baseline (2026-10-17)**: all of its work happens in the goto's first tick, inside the
  asyncio loop that also runs the speed controller, the Polaris socket and Alpaca. Measured in the twin on a Ryzen 9
  7950X (a fast desktop, so a lower bound):

  | | Idle goto | Goto while tracking |
  |---|---|---|
  | Normal tick (`control_step_calculate`) | 0.3 ms | 0.4 ms |
  | First tick of a goto | 40 ms | 10 ms |
  | Of which `plan_goto` (`GotoTrajectory.start`: 201 path samples, each a slerp + IK) | 30-41 ms | - (large moves not planned) |
  | Each later tick (`GotoTrajectory.step`) | 0.2 ms | 0.2 ms |

  The same path is sampled twice at the start of a goto: `prevent_windup`'s `_path_passes_gimbal_lock` (91
  samples) and the planner (201). A Pi Zero 2 W runs Python an estimated 10-20× slower than this desktop (to be
  measured), which puts the first tick of an idle goto at 0.4-0.8 s: two to four whole ticks.
* **The field logs show it already.** The Windows field PC (logs 2026-10-06 to 10-14) logs heartbeat lags (the
  100 ms pulse late) of 0.2-0.8 s right after gotos and rotates, with `plan_goto` / `prevent_windup` /
  `GotoTrajectory._interp` in the stack. This is the likely cause of the pause seen when a new goto is issued. The
  longest lags (2-15 s) come with "CPU: 100%" and position updates 1-3 s late: the whole machine saturated (imaging
  and plate solving on the same PC), not planning. Even so, planning must not add to that.
* **Requirements:**
  * **Budget**: a tick's planning work under 10% of the tick (20 ms) on the minimum hardware, with no single tick
    over 50 ms of planning. The control tick itself is unchanged.
  * **Never block the tick for a plan.** Plan in slices across ticks, or in a worker (`asyncio.to_thread`). Under
    the GIL a thread still competes for the CPU unless the work is in numpy, and a separate process costs memory a
    512 MB Pi can't spare. Until the new plan is ready the mount keeps following the current trajectory, or brakes
    within Ka. The new plan starts from the state predicted for its handover tick (R2), so a plan taking one or two
    ticks costs no pause.
  * **Do less work**: closed-form trapezoid/triangle profiles per motor for straight motor-angle moves (Design item
    2's slews: no path sampling at all). Path sampling only for the pointing-held paths (rotations, small
    corrections), with the samples shared by every check that needs them (gimbal lock, tripod cone R1, rig tilt,
    the trajectory), not one pass each.
  * **Vectorised kinematics**: IK/FK over an array of poses in one numpy call, in `kinematics.py` (R3), in place of
    one `Quaternion` per sample in Python.
  * **Cross-platform**: pure Python and numpy/scipy (already dependencies). No compiled extensions or OS-specific
    code in the planner (numba and the like don't install cleanly on a Pi Zero or every Windows Python).
  * **Measure it**: one log line per goto with the planning time and the number of ticks it spanned, so field logs
    show it alongside the heartbeat lags; a twin test that counts planning operations per goto, not wall time, so
    it is stable on any machine; a benchmark run on a Pi Zero 2 W and on the N1505 before release.

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

### Eq mode reachability, PA and upside-down frames (2026-10-17)

From `utility/analyse_span.ipynb` (eq sections; vector maths checked against the driver's `reachable_azaltroll`,
`theta_to_q` and `q_to_theta`). PA is the driver's: camera-up from the direction of the north celestial pole.

* **Motor reach on a wedge depends on Dec and PA only, not hour angle.** The rule is the level mount's (camera-up
  within 81.5 deg of the M1 axis) with the M1 axis on the pole; tracking turns M1 about the pole and leaves
  camera-up's angle to it unchanged. So a target that is reachable at some PA stays reachable at that PA all night,
  as far as the motors go (the rig tilt limit and the tripod cone depend on hour angle).
* **Upright, camera-up must lean toward the visible pole**: in the south, |PA| beyond about 98 deg at Dec 0.
  **Upside down** (PA + 180, the same footprint) covers the centre band, |PA| below about 82 deg. Neither works
  where camera-up would be within 8.5 deg of square to the pole (PA near ±90 at Dec 0); that gap widens toward the
  poles until nothing is left beyond |Dec| 81.5 (the polar caps):

  | Dec | Upright | Upside down only | Either |
  |---|---|---|---|
  | 0 | 45% | 45% | 91% |
  | -45 | 43% | 43% | 86% |
  | -75 | 31% | 31% | 62% |
  | -85 | 0% | 0% | 0% |

* **Allowing upside down exactly doubles the reachable PA**, at every latitude and every rig tilt limit (sky above
  the horizon: 43% -> 87% with motor reach alone). A PA and its upside-down twin are never both reachable (camera-up
  and camera-down can't both be within 81.5 deg of the M1 axis, nor both within a tilt limit of the zenith), so the
  flip only ever adds PAs. This is the "upside down is not a choice" rule above, seen in eq terms: for any requested
  framing at most one of the two is reachable, and reachability decides which.
* **What the driver does today**: `reachable_azaltroll` tries the upside-down frame first and clamps to the nearest
  reachable roll only if neither is reachable; eq mode applies it in the base frame (`_reachable_alpha`). With
  `eq_rig_tilt_limit` set, `limit_rig_tilt` then takes the smallest allowed PA turn, which can be a nearer edge
  than the flipped frame (see Open questions).
* **The rig tilt limit costs PA, most near the equator** (where the M1 axis is nearly horizontal). Mean share of
  PA reachable over the sky above the horizon, upright / either way up:

  | Latitude | Motor reach alone | Rig tilt ≤ 100 | Rig tilt ≤ 81.5 |
  |---|---|---|---|
  | 5 | 43 / 86% | 27 / 54% | 20 / 40% |
  | 35 | 43 / 87% | 35 / 70% | 28 / 56% |
  | 70 | 43 / 87% | 43 / 86% | 38 / 75% |

* **Tripod cone (R1)**: no end pose above the horizon is affected at any latitude. Straight motor-angle gotos
  between poses above 10 deg enter the cone in 0.9% of cases at Sydney, about 1.2% near the equator and none
  from about 50 deg latitude (the wedge nearly level). Every one first tips the rig past 81.5 deg, and those gotos
  swing M1 and M3 a long way (median 159 and 162 deg against 90 and 76 for all gotos). The rig tilt passes 100 deg
  partway through 43% of straight gotos, so with `eq_rig_tilt_limit` set the path check matters far more for the
  rig tilt than for the cone.

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

### Orbitals

Orbitals can be tracked (`advanced_orbitals`, tracking rates 1-3 in `orbital2delta`) but never stayed on target well
at longer focal lengths. That is more a tracking than a goto problem, but the two meet:

* **How it works now**: every tick the setpoint is the orbital's RA/Dec computed 2.5 s ahead. While the orbital is
  below 10 deg altitude the setpoint isn't updated and the mount tracks sidereal where it is; once it is above, the
  setpoint jumps to the orbital - an unplanned goto while tracking, chased by the PID (τ ≈ 2 s, overshoot on large
  moves), onto a target that keeps moving.
* **A moving target needs its velocity (and acceleration) in the feed-forward**: a PID that closes errors with
  τ ≈ 2 s lags a target moving at rate v by about v × τ unless the feed-forward carries the motion. The fixed 2.5 s
  lead should match the loop's real lag instead - the measured dead time is 0.2-0.4 s - and at 1 deg/s every 0.1 s
  of mismatch is 6'.
* PEC (worm feed-forward) and BLC have since addressed periodic error and backlash, two of the problems that made
  orbitals hard; what's left is the moving-target feed-forward, the dead time and planning the acquisition: a
  planned goto to where the orbital will be on arrival (design item 2), then tracking with its rate.
* An orbital response test like `goto_response.py` could measure this without the sky: follow a recorded or
  synthetic pass (in the twin, then on the mount in daylight) and compare θ_sp with θ_pv.

### Acceptance criteria

* Twin sweep (to become a test: a seeded subset in the suite, the full sweep marked slow): no LIMIT, no mid-goto
  remap, M2 never out of range, chosen end solution within 2 s of T_best except where tracking room decides, median
  arrival within 1.3× T_best.
* Hardware, `goto_response.py` idle and `--track`: median arrival - theoretical minimum under 3 s; overshoot under
  5' on moves ≤ 5 deg and under 15' on large ones; no completion while moving.
* Tripod cone (R1): in the twin sweep (eq mode, several latitudes) no sample of any planned path, braking included,
  has a boresight nadir distance under `tripod_cone_deg`.
* Interruption (R2): twin tests that redirect gotos at random times mid-flight show continuous speed commands (no
  step beyond Ka), no LIMIT, and arrival within 1.3× the T_best of a plan from the moving state.
* Platform performance (R4): in the twin, no tick does more than its planning budget of operations (none over 50 ms
  equivalent on a Pi Zero 2 W); on a Pi Zero 2 W and the N1505, no heartbeat lag over 0.15 s from planning across a
  `goto_response.py` run.
* The existing test suite passes, including the pano, reachability and zenith transit tests.

---

## Open questions

* Tracking room: 8 h in both modes? Alt/az tracking turns M1 and M3 at rates that vary with the pointing, so its room
  needs the projected motor path, not a rate.
* Battery: Kv from the baseline underestimates the speed at these charges. FAST calibration (R3) fixes the table;
  is it enough, or does it also need a live Kv (it shows in the measured speed of every FAST move) or a margin?
* Dead-time compensation: the delay is ~0.2 s of sample age plus the MCU's FAST lag; is it stable enough to
  compensate as a constant?
* BLC's share of the final settle while tracking: separate it with a run with BLC off.
* The twin's M3 speed: recalibrate it from these runs.
* Eq mode rig tilt and the tripod cone (R1): both are path constraints. How fine must the path sampling be, and
  is a waypoint around the cone enough or does it need a planned detour? What cone suits long lenses, and does the
  tripod's leg spread (not a full cone) matter?
* Interrupting a goto (R2): how far ahead to predict the state (one dead time?), and how much replanning every
  tick an orbital's moving setpoint needs.
* Eq mode with a single-point alignment: how much of the wedge's error it leaves, and the drift that follows.
* Orbitals: the 2.5 s lead against the measured lag; acquiring an orbital as it rises past 10 deg as a planned goto.
* A goto that also changes roll/PA over more than 15 deg: blended into the straight motor move (as now planned), or rotate along a controlled path at the end of the slew?
* Platform performance (R4): the Pi Zero 2 W's real slowdown against the desktop for this code; slices across ticks
  or a worker thread (and how much of the planning numpy can hold without the GIL); the exact N1505 model to
  benchmark; whether the field PC's 100% CPU episodes need the driver to lower its own load, or to warn.
* Out-of-reach PA with a rig tilt limit: `limit_rig_tilt` takes the smallest allowed PA turn, `reachable_azaltroll`
  the upside-down frame first. Should eq mode prefer the upside-down frame (the requested footprint exactly) over a
  nearer PA edge, as level mode does?
