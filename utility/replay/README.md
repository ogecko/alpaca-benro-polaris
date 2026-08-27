# Replay Test and Diagnostic Utility

## Purpose

`replay.py` is a command-line tool for replaying and testing the Alpaca Driver against a real,
running Benro Polaris device (either the actual setup, or a bench/desk setup). The tool replays ASCOM Alpaca Telescope, Rotator and DeviceAction commands against the driver's REST-API.

It has two jobs:

1. **Diagnostics** — replay a real `alpaca.log` file captured during an imaging session, sending the same
   commands back to a driver (typically a different mount, or the same mount at a later time) so a problem
   can be reproduced and investigated in detail.
2. **System testing** — run a repeatable test file that exercises the driver and checks that it behaves as
   expected, without needing PHD2, ASTAP, clear skies or a live imaging session.

Both jobs read the same kind of file: a text log file, in the same format the driver already writes to
`alpaca.log`. A diagnostic file is a real captured log. A test file is usually built the same way — trigger the
real command against a live driver once, copy the resulting log line(s) into a test file — with a few extra
line types (below) added by hand to control pacing and to simulate things that would otherwise need clear
skies.

## File Format

A replay file is a plain text file, one instruction per line. Two kinds of line are recognised:

**Real captured lines** — copied verbatim from a driver's `alpaca.log`, for example:

```
2026-08-27T09:03:06.687 INFO 127.0.0.1 -> PUT /api/v1/telescope/0/action {'Action': 'Polaris:ResetAxes', 'Parameters': ' ', 'ClientID': '8644', 'ClientTransactionID': '1006'}
```

`replay.py` reads the method, path and body from the line and sends the same request to the target driver. The
`ClientID`/`ClientTransactionID` in the line are not reused — a fresh ID is generated for the replay session,
since the original values aren't meaningful outside the session they were captured in.

**Replay keyword lines** — instructions to `replay.py` itself, not real driver traffic. These use a keyword in
place of the normal `IP -> ...`/`IP <- ...` text, for example:

```
INFO SLEEP {"seconds": 5}
```

The leading timestamp and level word (`INFO` above) are both optional, and neither is used by `replay.py` to
decide anything — it recognises a keyword line by the keyword itself (`SLEEP`, `SYNCGUIDE_PE`, ...) wherever it
appears. When hand-writing a test file, it's fine (and easier to read) to write `REPLAY` instead of `INFO` to
make it obvious at a glance which lines are replay directives rather than real captured traffic — `replay.py`
doesn't care either way:

```
REPLAY SLEEP {"seconds": 5}
```

When replaying a real captured log for diagnostics, real timestamps are used to reproduce the original timing
between requests. In a hand-written test file, timestamps are normally left out entirely — pacing is instead
controlled explicitly with `SLEEP`, and `replay.py` simply waits for each request's response before sending the
next line.

Any other line (startup banners, PECLOG/PIDLOG telemetry, Polaris status pushes, warnings, etc.) is ignored —
`replay.py` only acts on the two line shapes above.

## Keyword Reference

### `SLEEP`

Pause for a fixed number of seconds before continuing to the next line.

```
SLEEP {"seconds": 5}
```

### `WAIT_SETTLED`

Wait for a slew to finish, by polling `telescope/0/slewing` rather than guessing a fixed pause.
This matches how a real client (e.g. Nina) actually sequences a goto: fire it, then wait for
completion, rather than relying on a captured `SlewAbsolute` line's `isasync` value (which
blocks invisibly inside the request itself, and silently stops waiting at all if that value
ever gets edited to `true`).

```
WAIT_SETTLED {"timeout_s": 60}
```

`timeout_s` defaults to 60 if omitted; `poll_s` (default 1) controls how often it checks.
Raises an error if the mount is still slewing when the timeout is reached.

### `SYNCGUIDE_PE` and `PULSEGUIDE_PE`

Simulate a periodic error (PE) signal and the guide corrections an autoguider or plate-solver would send in response, without needing PHD2 or Nina/ASTAP. Both keywords describe the *same* synthetic PE waveform — they only differ in which real Alpaca command is used to feed it to the driver:

- `SYNCGUIDE_PE` sends the correction via `synctocoordinates` (the "sync guiding" path — real Nina/ASTAP
  plate-solve sync corrections). Both axes are corrected together in a single call, since that's how
  `synctocoordinates` works.
- `PULSEGUIDE_PE` sends the correction via `pulseguide` (the ASCOM PulseGuide path — what autoguiders like
  PHD2 actually use for guide pulses). Each cycle sends two separate commands, RA then Dec, matching how a real
  autoguider issues them.

The periodic error itself is defined directly in the same terms the driver's own PEC model reports it in
`PECLOG` — a constant drift plus however many harmonics, in arcmin/hour — rather than inventing a separate test
period. This matters because the driver's PEC model fits against its own configured worm period (`pec_T_sec`,
2040s/34min by default): a synthetic period picked independently of that falls outside what the model can
actually represent, and the fit never converges no matter how good the simulation is.

Fields:

| Field         | Meaning |
|---------------|---------|
| `ra_model`    | `[dc, h1, h2, ...]` — RA drift rate (`dc`) plus each harmonic's amplitude, in arcmin/hour. Same convention as `PECLOG`'s `ra_model` field. |
| `dec_model`   | Same as `ra_model`, for Dec. |
| `pec_T_sec`   | The worm period `replay.py` assumes when generating the simulated periodic error, in seconds. Defaults to whatever the driver's own live `pec_T_sec` is (read via `Polaris:ConfigFetch` at the start of the test) — leave it unset for a normal, matched test. Setting it to something different from the driver's actual configured value doesn't change what the driver is doing, only what `replay.py` simulates — it's there to deliberately test how badly PEC's fit degrades under a period mismatch, the same failure mode found while validating this design (see below). |
| `exposure_s`  | Seconds between corrections — an autoguider's exposure/guide interval. |
| `session_min` | How long to keep running this phase, in minutes. |

A real sync-guiding session isn't one continuous phase — it starts with a fast burst of corrections to get PEC
bootstrapped, then settles into the much slower cadence of real imaging. That's expressed as two consecutive
`SYNCGUIDE_PE` lines, not a special "autotune" keyword — the first covering the bootstrap burst (short, `dc`
only), the second the real steady-state session (full harmonics, real exposure cadence):

```
REPLAY SYNCGUIDE_PE {"ra_model": [8.0, 0, 0], "dec_model": [0, 0, 0], "exposure_s": 10, "session_min": 4}
REPLAY SYNCGUIDE_PE {"ra_model": [8.0, 12.5, 3.0], "dec_model": [0, 3.0, 1.0], "exposure_s": 110, "session_min": 120}
```

`replay.py` uses this definition to compute, at each `exposure_s` tick, what the mount's simulated position
error should be and sends the corresponding correction command — continuing smoothly from wherever the previous
`SYNCGUIDE_PE` phase left off, so there's no artificial jump in simulated position at the boundary between the
bootstrap and steady-state phases. It also writes a `Polaris:ReplayMark` marker (see below) into the driver's
own log recording these same parameters, so the result can later be compared against what the driver's PEC
model actually fit.

**Deliberately mismatching `pec_T_sec`**: an early hand-run of this idea against a real driver used a made-up
60-second test period instead of the driver's real ~2040s worm period. The result was a `PECLOG` that never
settled — the fitted `dc` term swung between roughly 118 and 190 arcmin/hour instead of converging, and `rmse`
got worse over the run instead of better, because a fit built around a 2040s basis has no way to represent a
60s wobble. That's a real, useful failure mode to be able to reproduce on demand — hence `pec_T_sec` being an
explicit, overridable field rather than something `replay.py` just quietly gets right by default.

## Marking Replay Activity in the Log

Whenever `replay.py` starts a simulated activity like `SYNCGUIDE_PE`/`PULSEGUIDE_PE`, it also tells the driver
to record the same parameters into its own log, via a `Polaris:ReplayMark` device action. This means the
driver's log ends up with both the synthetic input (what we told it to expect) and its own PECLOG output (what
it actually fitted), on the same timeline, in the same file — so they can be compared directly without needing
to line up two separate files by clock time.

Unlike most log categories in this driver, these marker lines aren't gated behind a `log_xxx` config flag —
they always log when `Polaris:ReplayMark` is invoked, the same as `PECLOG`/`PIDLOG`, so a test run doesn't
silently lose its ground truth because of an unrelated logging setting.

## Setting Up the Driver Before a Test

Most tests need the driver in a known state before the interesting part starts. This is done the normal way —
with real captured lines at the start of the test file, the same as any other captured command. For a
sync-guiding PEC test, that means the same steps a real session goes through:

1. **Clear the alignment model** — `Polaris:ConfigUpdate` toggling `advanced_alignment` off then on, for a
   clean, reproducible starting point. This wipes any existing real alignment model, so only do this against a
   mount you're happy to have re-aligned afterwards.
2. **Slew to the test target** — a real captured `Polaris:SlewAbsolute` line (az/alt/roll).
3. **Turn on what the test needs** — `Polaris:ConfigUpdate` for `advanced_pec`, `advanced_sync_guiding` (for
   `SYNCGUIDE_PE`) or `advanced_pulse_pec_tuning` (for `PULSEGUIDE_PE`), plus `log_position` for extra
   telemetry during system tests.
4. **Tracking on** — `telescope/0/tracking`, off then on, to clear any old guide-correction/PEC-model state and
   start from a clean baseline.

Then the `SYNCGUIDE_PE`/`PULSEGUIDE_PE` line(s) themselves (see above).

## Diagnosing Results

A test run against a live driver produces a normal `alpaca.log` for that driver, containing the usual `PECLOG`
lines plus the `Polaris:ReplayMark` lines described above. Comparing the two tells you whether the driver's PEC
model correctly recovered the periodic error you told it to expect.

A dedicated analysis notebook for this comparison (building on the existing `analyse_pec.ipynb`) is planned but
not yet built.

## Current Status

This document describes the design; `replay.py` itself has not been written yet. Still to be worked out:

- `ASSERT` lines, to automatically check driver state against expected values during a test (deferred until
  after the PE test case above is working).
- Which real Alpaca PUT commands are safe/expected to appear in a test file (a whitelist or blacklist) versus
  ones that shouldn't be replayed.
- The analysis notebook for comparing `Polaris:ReplayMark` parameters against the resulting `PECLOG` fit.

The first test case being built is `SYNCGUIDE_PE` — simulating a periodic error and confirming the driver's PEC
model fits it correctly via sync guiding.
