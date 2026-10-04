<template>
  <div ref="chart" style="height: 300px; width: 100%; position: relative;">
    <q-resize-observer @resize="onResize" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import { formatAngle } from 'src/utils/scale'
import { throttle } from 'quasar'
import { deg2fulldms } from 'src/utils/angles'
import { onFrame } from 'src/utils/animationClock'
import { MAX_RECORDS } from 'src/stores/stream'
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
// The lines are drawn on a canvas under the SVG (axes, gridlines, legend, statistics stay in the SVG on top). As
// SVG paths they made every redraw restyle each path and re-read all its points (a path's shape is a style
// property): 6 charts x 10 lines x 150 points, more expensive as the data buffers filled, until an N5105 slowed
// to a few redraws a second for good. Canvas drawing involves no styling at all.
let canvas: HTMLCanvasElement | null = null
let plotWidth = 0
let plotHeight = 0


// Live time charts scroll on a steady clock, not one step per record: records arrive about every 200 ms
// but irregularly (p5-p95 150-250 ms, and now and then a 300-950 ms gap or two at once), so stepping per
// record made the plot lurch. The visible window ends SCROLL_DELAY_MS behind the newest record and moves
// with real time on the shared redraw clock (animationClock, which adapts the rate to the PC); late or bunched
// records fill in off the right edge.
// The y range changes rarely and in one step (yRange): new y tick labels are the costliest thing a redraw can
// do on a small PC, and easing the range redrew them every frame for a second whenever the data's extent moved.
const SCROLL_DELAY_MS = 1000      // how far the right edge trails the newest record (covers the arrival jitter)
const LEFT_MARGIN_MS = 1000       // how far the left edge stays inside the oldest record (so it never shows a gap)
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
const MIN_SPAN_MS = 10000               // at least this wide: with the first records only, a zero-width window
                                        // would draw everything at the middle of the chart
// The time axis and its gridlines: ticks laid out once against a fixed reference (an "epoch" value at x = 0)
// inside an inner group, and each redraw only moves that group. Moving every tick each redraw made the browser
// restyle them all (the charts' whole style cost on an N5105); now a tick is only touched when it scrolls in or
// out, and all of them only when the scale itself changes (zoom, or the window width settling at startup).
type AxisLayout = { epoch: number, pxPerUnit: number }
let gXTicks: d3.Selection<SVGGElement, unknown, null, undefined>
let gridXTicks: d3.Selection<SVGGElement, unknown, null, undefined>
let xAxisLayout: AxisLayout = { epoch: 0, pxPerUnit: 0 }
let xGridLayout: AxisLayout = { epoch: 0, pxPerUnit: 0 }
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
  xScale = props.x1Type === 'time'
    ? d3.scaleTime().range([0, width - margin.left - margin.right])
    : d3.scaleLinear().range([0, width - margin.left - margin.right])
  yScale = d3.scaleLinear().range([height - margin.top - margin.bottom, 0])

  d3.select(chart.value).select('svg').remove()
  d3.select(chart.value).select('canvas').remove()
  plotWidth = width - margin.left - margin.right
  plotHeight = height - margin.top - margin.bottom
  const dpr = window.devicePixelRatio || 1
  canvas = d3.select(chart.value)
    .append('canvas')
    .attr('width', Math.round(plotWidth * dpr))
    .attr('height', Math.round(plotHeight * dpr))
    .style('position', 'absolute')
    .style('left', `${margin.left}px`)
    .style('top', `${margin.top}px`)
    .style('width', `${plotWidth}px`)
    .style('height', `${plotHeight}px`)
    .style('pointer-events', 'none')
    .style('background-color', '#1e1e1e')        // the plot area's background (the margins show the card)
    .node()
  svg = d3.select(chart.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .style('position', 'absolute')
    .style('left', '0')
    .style('top', '0')

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  const plotW = width - margin.left - margin.right
  const plotH = height - margin.top - margin.bottom
  // The time axis and its gridlines move every redraw, so they are drawn by drawXAxis (below), not d3.axis:
  // d3.axis re-sets the group's font attributes on every call, which makes the browser restyle -- and re-resolve
  // the font of -- every tick label each redraw (on an N5105 that was 2/3 of all the browser's time). Their
  // fonts, colours and baseline are set once, here.
  gridX = g.append('g').attr('color', '#444').attr('transform', `translate(0,${plotH})`)
  gridX.append('path').attr('class', 'domain').attr('fill', 'none').attr('stroke', 'currentColor')
    .attr('d', `M0.5,${-plotH}V0.5H${plotW + 0.5}V${-plotH}`)
  gridXTicks = gridX.append('g')
  gridY = g.append('g').attr('color', '#444')

  gX = g.append('g').attr('transform', `translate(0,${plotH})`).style('color', '#aaa')
    .attr('fill', 'none').attr('font-size', 10).attr('font-family', 'sans-serif').attr('text-anchor', 'middle')
  gX.append('path').attr('class', 'domain').attr('stroke', 'currentColor').attr('d', `M0.5,6V0.5H${plotW + 0.5}V6`)
  gXTicks = gX.append('g')
  xAxisLayout = { epoch: 0, pxPerUnit: 0 }
  xGridLayout = { epoch: 0, pxPerUnit: 0 }
  gY = g.append('g').style('color', '#aaa')
  legendKey = ''
  statsText = ''

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
    // follow the data clock; jump only when far off (first data, a pause, a reconnect). Averaged evenly: tracking
    // the least-delayed messages instead put the right edge so close to the newest data that ordinary delays showed
    // a gap there (measured at 6x CPU throttle)
    if (clockOffset === null || Math.abs(offset - clockOffset) > 3000) clockOffset = offset
    else clockOffset += 0.05 * (offset - clockOffset)
    // While the topic's buffer is still filling (after a driver restart its backlog is empty) the window is sized for
    // a full buffer, from the records' typical spacing, so the data enters from the right: sized to the data instead,
    // it widened every couple of records and each widening squeezed the plot back to the right of where the steady
    // scroll had taken it (a left-right jitter for the first ~30 s)
    const n = times.length
    let dataSpan = newest - (times[0] ?? newest)
    if (n >= 3 && n < MAX_RECORDS) {
      const gaps = times.slice(1).map((t, i) => t - times[i]!).sort((a, b) => a - b)
      dataSpan = Math.max(dataSpan, gaps[Math.floor(gaps.length / 2)]! * (MAX_RECORDS - 1))
    }
    const full = Math.max(0, dataSpan - SCROLL_DELAY_MS - LEFT_MARGIN_MS)
    // the window's width follows the data's span, but only when that has moved by more than 2%: it jitters with
    // every record, and each change of width re-lays out the time axis
    const target = Math.max(full, MIN_SPAN_MS)
    if (spanMs === 0 || Math.abs(target - spanMs) > 0.02 * spanMs) spanMs = target
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

  drawXAxis(gXTicks, xAxisLayout, zx, 6, true)
  drawXAxis(gridXTicks, xGridLayout, zx, -(height - margin.top - margin.bottom), false)

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

function drawXAxis(
  inner: d3.Selection<SVGGElement, unknown, null, undefined>,
  layout: AxisLayout,
  zx: d3.ScaleLinear<number, number> | d3.ScaleTime<number, number>,
  tickLength: number,
  labels: boolean,
) {
  const asValue = (d: number) => props.x1Type === 'time' ? new Date(d) : d
  const x = (d: number) => (zx as (v: number | Date) => number)(asValue(d))
  const [d0, d1] = (zx.domain() as (number | Date)[]).map(d => +d) as [number, number]
  const pxPerUnit = (x(d1) - x(d0)) / ((d1 - d0) || 1)
  // re-lay out every tick only when the scale changes (or the group has moved very far)
  const relayout = Math.abs(pxPerUnit - layout.pxPerUnit) > 1e-3 * Math.abs(pxPerUnit)
                   || Math.abs((d0 - layout.epoch) * pxPerUnit) > 1e6
  if (relayout) {
    layout.epoch = d0
    layout.pxPerUnit = pxPerUnit
  }
  const place = (d: number) => `translate(${(d - layout.epoch) * layout.pxPerUnit + 0.5},0)`

  // Ticks keyed by value: created (with its label) when it scrolls into view, removed when it leaves.
  const ticks = (zx.ticks() as (number | Date)[]).map(d => +d)
  const format = zx.tickFormat() as (d: number | Date) => string
  const tick = inner.selectAll<SVGGElement, number>('g.tick').data(ticks, d => d)
  tick.exit().remove()
  const added = tick.enter().append('g').attr('class', 'tick').attr('transform', place)
  added.append('line').attr('stroke', 'currentColor').attr('y2', tickLength)
  if (labels) {
    added.append('text').attr('fill', 'currentColor').attr('y', 9).attr('dy', '0.71em')
      .text(d => format(asValue(d)))
  }
  if (relayout) tick.attr('transform', place)
  inner.attr('transform', `translate(${x(layout.epoch)},0)`)          // the one change on every redraw
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
  // On the canvas, in plot coordinates; it covers only the plot area, so lines past the edges are cut off.
  const ctx = canvas?.getContext('2d')
  if (!ctx || !canvas) return
  const dpr = canvas.width / Math.max(1, plotWidth)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, plotWidth, plotHeight)
  ctx.lineWidth = 2
  ctx.lineJoin = 'round'
  const x = (d: DataPoint) => (zx as (v: number | Date) => number)(d.x1 as number | Date)
  lineDefs.forEach(def => {
    let drawing = false
    ctx.beginPath()
    for (const d of props.data) {
      const v = d[def.key]
      if (typeof v !== 'number') { drawing = false; continue }
      const px = x(d)
      const py = zy(v)
      if (drawing) ctx.lineTo(px, py)
      else ctx.moveTo(px, py)
      drawing = true
    }
    ctx.strokeStyle = def.color
    ctx.stroke()
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
  // no background here: the lines are drawn on a canvas under this SVG, which must show through it (the canvas
  // also paints the plot area's background)

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
