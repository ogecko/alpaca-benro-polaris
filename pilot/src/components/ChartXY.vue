<template>
  <div ref="chart" style="height: 300px; width: 100%;">
    <q-resize-observer @resize="onResize" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import { formatAngle } from 'src/utils/scale'
import { throttle } from 'quasar'
import { deg2fulldms } from 'src/utils/angles'
import { onFrame } from 'src/utils/chartClock'
// import { deg2fulldms } from 'src/utils/angles'
export type DataPoint = Record<string, number | Date | undefined>

const props = withDefaults(defineProps<{ 
  data: DataPoint[]
  x1Type: 'number' | 'time'
  y1Type?: 'number' | 'dms' | 'hms'
  rmsScale?: number
}>(), {
  y1Type: 'number'
})

const chart = ref<HTMLDivElement | null>(null)

const height = 300
const margin = { top: 20, right: 30, bottom: 30, left: 80 }

const colors = {
  sp: 'hsl(132, 79%, 60%)',      // Green
  pv: 'hsl(0,   0%, 100%)',      // White
  op: 'hsl(195, 99%, 70%)',      // Cyan
  m1: 'hsl(218, 63%, 32%)',      // Dark Blue
  kp: 'hsl(320, 70%, 30%)',      // Dark Magenta
  ki: 'hsl(50,  70%, 30%)',      // Dark Yellow   
  kd: 'hsl(20,  60%, 30%)',      // Dark Red
  kf: 'hsl(132, 79%, 60%)',      // Dark Lime
}


// --- Define line configurations here ---
const lineDefs = [
  { key: 'M1', color: colors.m1 },
  { key: 'M2', color: colors.m1 },
  { key: 'M3', color: colors.m1 },
  { key: 'PV', color: colors.pv },
  { key: 'SP', color: colors.sp },
  { key: 'Kp', color: colors.kp },
  { key: 'Ki', color: colors.ki },
  { key: 'Kd', color: colors.kd },
  { key: 'FF', color: colors.kf },
  { key: 'OP', color: colors.op },
]

let svg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let xScale: d3.ScaleTime<number, number> | d3.ScaleLinear<number, number>
let yScale: d3.ScaleLinear<number, number>
let gX: d3.Selection<SVGGElement, unknown, null, undefined>
let gY: d3.Selection<SVGGElement, unknown, null, undefined>
let zoom: d3.ZoomBehavior<SVGSVGElement, unknown>
let currentTransform: d3.ZoomTransform | null = null
let gridX: d3.Selection<SVGGElement, unknown, null, undefined>
let gridY: d3.Selection<SVGGElement, unknown, null, undefined>
const paths: Record<string, d3.Selection<SVGPathElement, unknown, null, undefined>> = {}


// Live time charts scroll on a steady clock, not one step per record: records arrive about every 200 ms
// but irregularly (p5-p95 150-250 ms, and now and then a 300-950 ms gap or two at once), so stepping per
// record made the plot lurch. The visible window ends SCROLL_DELAY_MS behind the newest record and moves
// with real time on the shared redraw clock (chartClock, which adapts the rate to the PC); late or bunched
// records fill in off the right edge.
// The y range changes rarely and in one step (yRange): new y tick labels are the costliest thing a redraw can
// do on a small PC, and easing the range redrew them every frame for a second whenever the data's extent moved.
const SCROLL_DELAY_MS = 1000      // how far the right edge trails the newest record (covers the arrival jitter)
const Y_MARGIN = 0.05             // room above and below the data, as a share of its extent
const Y_SHRINK = 0.6              // shrink the range only once the data fills less than this share of it
let stopTicking: (() => void) | null = null   // leaves the shared redraw clock
// Each new or restyled SVG element costs a style recalculation, which is slow on a small PC (N5105: ~0.25 ms an
// element), so nothing is rebuilt or restyled unless it changed: the legend only when its lines change, the
// statistics text only when it changes, and the axis colour once, when the chart is built.
let legendKey = ''
let statsText = ''
let clockOffset: number | null = null   // data time (ms) minus performance.now() at the newest record
let spanMs = 0                          // width of the visible window (ms)
let yDomain: [number, number] | null = null    // the y range shown
// The chart's width, read only when it is built or resized: reading clientWidth while drawing forces the
// browser to lay the page out again right away (a forced reflow), once per chart per frame.
let chartWidth = 500
let yAxisKey = ''                       // the y domain and zoom the y axis was last drawn for

const isLive = () => props.x1Type === 'time'

function initChart() {
  // never narrower than the margins: a chart built while its box is still collapsed (page load, a closed
  // panel) would otherwise get a negative plot width (<rect> width "-15"); it is rebuilt when it resizes
  chartWidth = Math.max(chart.value?.clientWidth ?? 500, margin.left + margin.right + 10)
  yAxisKey = ''
  const width = chartWidth
  const clipId = `plot-clip-${Math.random().toString(36).slice(2, 9)}`
  
  xScale = props.x1Type === 'time'
    ? d3.scaleTime().range([0, width - margin.left - margin.right])
    : d3.scaleLinear().range([0, width - margin.left - margin.right])
  yScale = d3.scaleLinear().range([height - margin.top - margin.bottom, 0])

  d3.select(chart.value).select('svg').remove()
  svg = d3.select(chart.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  // lines are clipped to the plot area (a live chart's newest second lies just past the right edge)
  g.append('defs').append('clipPath').attr('id', clipId)
    .append('rect')
    .attr('width', width - margin.left - margin.right)
    .attr('height', height - margin.top - margin.bottom)

  g.append('rect')
    .attr('width', width - margin.left - margin.right)
    .attr('height', height - margin.top - margin.bottom)
    .attr('fill', '#1e1e1e')
    .lower()

  gridX = g.append('g').attr('color', '#444')
    .attr('transform', `translate(0,${height - margin.top - margin.bottom})`)
  gridY = g.append('g').attr('color', '#444')

  gX = g.append('g').attr('transform', `translate(0,${height - margin.top - margin.bottom})`).style('color', '#aaa')
  gY = g.append('g').style('color', '#aaa')
  legendKey = ''
  statsText = ''

  // Create paths dynamically for each line definition
  lineDefs.forEach(def => {
    paths[def.key] = g.append('path')
      .attr('class', `line ${def.key}`)
      .attr('fill', 'none')
      .attr('stroke', def.color)
      .attr('stroke-width', 2)
      .attr('clip-path', `url(#${clipId})`)
  })

  svg.append('text')
    .attr('class', 'stdev-label')
    .attr('text-anchor', 'end')
    .attr('x', width - 40)
    .attr('y', height - 70)
    .attr('fill', '#ccc')
    .style('font-size', '18px')
    .text('')

  zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([1, 10])
    .translateExtent([[0, 0], [width, height]])
    .on('zoom', (event) => {
      currentTransform = event.transform
      if (!currentTransform) return
      if (isLive()) render()
      else updateChart()
    })

  svg.call(zoom)
  drawLegend(svg, width)
}

function shortTickMarks(fullFormat: (d: number) => string) {
  let prevLabel: string | null = null

  return (d: d3.NumberValue) => {
    const full = fullFormat(+d)
    if (prevLabel === null) {
      prevLabel = full
      return full
    }

    const splitUnits = (s: string) => s.match(/[^°′ʰᵐ]*[°′ʰᵐ]|[^°′ʰᵐ]+$/g) ?? [s]
    const fullParts = splitUnits(full)
    const prevParts = splitUnits(prevLabel)

    let i = 0
    const maxCompare = Math.min(fullParts.length, prevParts.length) - 1
    while (i < maxCompare && fullParts[i] === prevParts[i]) i++

    prevLabel = full
    let truncated = fullParts.slice(i).join('')
    // Re-attach the -ve sign for clarity.
    if (full.startsWith('-') && !truncated.startsWith('-')) {
      truncated = '-' + truncated
    }

    return truncated
  }
}

function updateChart() {
  // Called when the data changes (and on mount/resize): recompute ranges, legend and statistics.
  if (!props.data?.length || !svg) return
  const width = chartWidth

  const allYValues = lineDefs.flatMap(def =>
    props.data.map(d => d[def.key]).filter((v): v is number => typeof v === 'number')
  )
  yDomain = yRange(d3.min(allYValues) ?? 0, d3.max(allYValues) ?? 100, yDomain)
  yScale.domain(yDomain)

  if (isLive()) {
    const times = props.data.map(d => (d.x1 as Date).getTime())
    const newest = times[times.length - 1] ?? 0
    const now = performance.now()
    const offset = newest - now
    // follow the data clock; jump only when far off (first data, a pause, a reconnect)
    if (clockOffset === null || Math.abs(offset - clockOffset) > 3000) clockOffset = offset
    else clockOffset += 0.05 * (offset - clockOffset)
    const full = Math.max(0, newest - (times[0] ?? newest) - SCROLL_DELAY_MS)
    spanMs = spanMs === 0 ? full : spanMs + 0.05 * (full - spanMs)
    ensureAnimating()
  } else {
    const x1 = props.data.map(d => d.x1 as number)
    xScale.domain([d3.min(x1) ?? 0, d3.max(x1) ?? 100])
    render()
  }

  drawStatistics(svg)
  drawLegend(svg, width)
}

function render() {
  // Draw axes, gridlines and lines for the current xScale/yScale domains (no transitions).
  // The time axis moves every frame; the y axis is redrawn only when its range (or the zoom) changes.
  if (!props.data?.length || !svg) return
  const zx = currentTransform ? currentTransform.rescaleX(xScale) : xScale
  const zy = currentTransform ? currentTransform.rescaleY(yScale) : yScale

  gX.call(d3.axisBottom(zx))
  gridX.call(
    d3.axisBottom(zx)
      .tickSize(-(height - margin.top - margin.bottom))
      .tickFormat(() => '')
  )

  const [y0, y1] = zy.domain() as [number, number]
  const tol = Math.abs(y1 - y0) * 1e-3                  // well under a pixel
  const key = `${Math.round(y0 / (tol || 1))},${Math.round(y1 / (tol || 1))}`
  if (key !== yAxisKey) {
    yAxisKey = key
    const yAxis = d3.axisLeft(zy)
    if (props.y1Type === 'dms') {
      yAxis.tickFormat(shortTickMarks((d: d3.NumberValue) => deg2fulldms(+d, 1, 'deg')))
    }
    else if (props.y1Type === 'hms') {
      yAxis.tickFormat(shortTickMarks((d: d3.NumberValue) => deg2fulldms(+d/15, 1, 'hr')))
    }
    gY.call(yAxis)
    drawGridY(zy, chartWidth)
  }

  drawLines(zx, zy)
}

function yRange(lo: number, hi: number, current: [number, number] | null): [number, number] {
  // Keep the current range while the data fits it and fills a fair share of it; otherwise a new range with
  // a margin around the data, rounded to tick-friendly ("nice") limits.
  if (current) {
    const [c0, c1] = current
    if (lo >= c0 && hi <= c1 && hi - lo >= Y_SHRINK * (c1 - c0)) return current
  }
  const extent = Math.max(hi - lo, Math.abs(hi) * 1e-6, 1e-9)
  const pad = Y_MARGIN * extent
  const padded: [number, number] = [lo - pad, hi + pad]
  const nice = d3.scaleLinear().domain(padded).nice().domain() as [number, number]
  // rounding can widen the range; keep it only if the data still fills it comfortably (else the next update
  // would shrink it straight away)
  return extent >= (Y_SHRINK + 0.1) * (nice[1] - nice[0]) ? nice : padded
}

function frame(t: number) {
  if (!svg || !isLive() || clockOffset === null) return
  const end = t + clockOffset - SCROLL_DELAY_MS
  xScale.domain([new Date(end - spanMs), new Date(end)])
  render()
}

function ensureAnimating() {
  if (!stopTicking) stopTicking = onFrame(frame)
}


function drawStatistics(svg: d3.Selection<SVGSVGElement, unknown, null, undefined>) {
  const hasPV = props.data.some(d => typeof d.PV === 'number')
  const hasSP = props.data.some(d => typeof d.SP === 'number')
  const hasOP = props.data.some(d => typeof d.OP === 'number')
  const hasMx = props.data.some(d => typeof d.M1 === 'number' || typeof d.M2 === 'number' || typeof d.M3 === 'number')

  let label = ''

  if (hasMx && hasPV) {
    const mxValues = props.data.flatMap(d =>
      ['M1', 'M2', 'M3']
        .map(k => typeof d[k] === 'number' ? d[k] : null)
        .filter((v): v is number => v !== null)
    )
    const pvValues = props.data
      .map(d => d.PV)
      .filter((v): v is number => typeof v === 'number')

    const stdevMx = d3.deviation(mxValues) ?? 0
    const stdevPV = d3.deviation(pvValues) ?? 0

    label = `σ(Mx): ${formatAngle(stdevMx, 'deg', 2)} vs σ(PV): ${formatAngle(stdevPV, 'deg', 2)}`
  } else if (hasPV && hasSP) {
    const errors = props.data
      .map(d => (typeof d.PV === 'number' && typeof d.SP === 'number') ? d.SP - d.PV : null)
      .filter((v): v is number => v !== null)
    const scaledErrors = errors.map(e => (props.rmsScale ?? 1) * e)
    const rms = Math.sqrt(d3.mean(scaledErrors.map(e => e * e)) ?? 0)
    label = `RMS Error: ${formatAngle(rms, 'deg', 2)}`
  } else if (hasOP) {
    const opValues = props.data
      .map(d => d.OP)
      .filter((v): v is number => typeof v === 'number')

    const stdevOP = d3.deviation(opValues) ?? 0
    label = `σ(OP): ${formatAngle(stdevOP, 'deg', 2)}`
  }

  if (label !== statsText) {
    statsText = label
    svg.select('.stdev-label').text(label)
  }
}



function drawLegend(svg: d3.Selection<SVGSVGElement, unknown, null, undefined>, width: number) {
  const legendData = lineDefs.filter(def =>
    props.data.some(d => typeof d[def.key] === 'number')
  )
  const key = legendData.map(def => def.key).join(',')
  if (key === legendKey) return                 // same lines as last time: keep the legend as it is
  legendKey = key
  svg.select('.legend').remove()

  const legend = svg.append('g')
    .attr('class', 'legend')
    .attr('transform', `translate(${width - margin.right - 60}, ${margin.top + 10})`)

  legendData.forEach((def, i) => {
    const legendRow = legend.append('g')
      .attr('transform', `translate(0, ${i * 18})`)

    legendRow.append('line')
      .attr('x1', 0)
      .attr('x2', 30)
      .attr('y1', 8)
      .attr('y2', 8)
      .attr('stroke', def.color)
      .attr('stroke-width', 2)

    legendRow.append('text')
      .attr('x', 35)
      .attr('y', 12)
      .attr('fill', '#ccc')
      .style('font-size', '12px')
      .text(def.key)
  })
}



function drawLines(
    zx: d3.ScaleLinear<number, number> | d3.ScaleTime<number, number> = xScale,
    zy = yScale,
) {
  lineDefs.forEach(def => {
    const line = d3.line<DataPoint>()
      .defined(d => typeof d[def.key] === 'number')
      .x(d => zx(props.x1Type === 'time' ? d.x1 as Date : d.x1 as number))
      .y(d => zy(d[def.key] as number))
    paths[def.key]?.attr('d', line(props.data))
  })
}



function drawGridY(
  zy: d3.ScaleLinear<number, number>,
  width: number,
) {
  gridY.call(
    d3.axisLeft(zy)
      .tickSize(-(width - margin.left - margin.right))
      .tickFormat(() => '')
  )

  // Highlight the horizontal gridline at y = 0.000
  gridY.selectAll<SVGGElement, number>(".tick")
    .each(function (d) {
      if (Math.abs(d) < 1e-6) {
        d3.select(this).select("line")
          .attr("stroke", "#555")
          .attr("stroke-width", 3);
      }
    });
}

function onResize() {
  d3.select(chart.value).select('svg').remove()
  initChart()
  updateChart()
}

onMounted(async () => {
  await nextTick()
  initChart()
  updateChart()
})

const throttledUpdateChart = throttle(() => { updateChart()}, 100)
watch(() => props.data, throttledUpdateChart, { deep: true })

onBeforeUnmount(() => {
  stopTicking?.()
  stopTicking = null
  d3.select(chart.value).select('svg').remove()
})
</script>


<style scoped lang="scss">
svg {
  background-color: #1e1e1e;

  // Intentionally no `transition: d` here -- the chart redraws every ~170ms (see the
  // throttled watch below), faster than a d-attribute transition could ever complete,
  // so it would perpetually restart and keep these paths pinned to their own GPU
  // compositor layer indefinitely. That's a real, session-duration-scaling GPU/compositor
  // leak (was previously bad enough to freeze mouse/keyboard input system-wide on long
  // sessions). The intended scroll animation is already handled correctly in JS via
  // drawLines()'s explicit transform transition below -- this CSS rule was redundant.

  // Axis lines
  .x-axis path,
  .y-axis path,
  .x-axis line,
  .y-axis line {
    stroke: #888;
  }

  // Axis labels
  .x-axis text,
  .y-axis text {
    color: #ccc;
  }


}


.stdev-label {
  font-family: sans-serif;
  pointer-events: none;
}


</style>
