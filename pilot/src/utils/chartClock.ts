// One redraw clock shared by every live chart (ChartXY.vue). All charts redraw in the same animation frame, so the
// browser does one style/layout/paint pass for them all, and the clock times the charts' code AND the browser's
// style and layout work on them -- which on a small PC (N5105) is most of the cost -- to space the redraws so they
// take about BUSY_SHARE of the browser's time: 20 a second on a fast PC, fewer on a slow one. A steady pace looks
// better than one that follows every change in cost (on an N5105 a redraw of 6 charts costs 20-120 ms, as tick
// labels appear and y ranges change), so the pace is set from the 75th percentile of the last COST_SAMPLES redraws
// and only changes when that moves by more than PACE_CHANGE.

type Tick = (t: number, dt: number) => void

const BUSY_SHARE = 0.3            // share of the browser's time the live charts together aim to use
const FRAME_MS_MIN = 50           // at most 20 redraws a second (a live chart moves ~17 px/s: under 1 px a frame)
const FRAME_MS_MAX = 500          // at least 2 a second
const COST_SAMPLES = 60           // recent redraw costs (charts + the browser's style/layout) the pace is set from
const PACE_CHANGE = 0.25          // change the pace only when the new one differs by more than this share

const subscribers = new Set<Tick>()
const costs: number[] = []
let rafId = 0
let lastFrame = 0
let frameMs = FRAME_MS_MIN        // current time between redraws

function frame(t: number) {
  rafId = subscribers.size ? requestAnimationFrame(frame) : 0
  const dt = t - lastFrame
  if (dt < frameMs) return
  lastFrame = t
  const started = performance.now()
  subscribers.forEach(fn => fn(t, dt))
  // Make the browser do this frame's style and layout now (reading a layout value forces it), so the time
  // covers the charts' code AND the browser's work on them -- which it would otherwise do just after this
  // callback anyway, so it costs nothing extra. Timing up to a task queued afterwards instead also counted
  // whatever ran first (the live data handling, ~30 ms a message on an N5105) and slowed the charts for nothing.
  void document.body.offsetHeight
  const cost = performance.now() - started
  costs.push(cost)
  if (costs.length > COST_SAMPLES) costs.shift()
  const sorted = [...costs].sort((a, b) => a - b)
  const p75 = sorted[Math.floor(sorted.length * 0.75)] ?? cost
  const next = Math.min(FRAME_MS_MAX, Math.max(FRAME_MS_MIN, p75 / BUSY_SHARE))
  if (Math.abs(next - frameMs) <= PACE_CHANGE * frameMs) return
  if (import.meta.env.DEV) {
    console.debug(`[charts] redraw every ${next.toFixed(0)} ms (75% of frames cost up to ${p75.toFixed(0)} ms, ` +
      `last ${cost.toFixed(0)} ms, ${subscribers.size} charts)`)
  }
  frameMs = next
}

/** Redraw with fn(t, dt) on the shared clock (dt: ms since the last redraw); returns a function that stops it. */
export function onFrame(fn: Tick): () => void {
  subscribers.add(fn)
  if (!rafId) rafId = requestAnimationFrame(frame)
  return () => { subscribers.delete(fn) }
}
