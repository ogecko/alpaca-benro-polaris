<template>
  <div ref="chart" style="height: 300px; width: 100%;">
    <q-resize-observer @resize="onResize" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import { formatAngle, colors } from 'src/utils/scale'
export type DataPoint = Record<string, number | Date | undefined>

const props = defineProps<{ 
  data: DataPoint[] 
  x1Type: 'number' | 'time'
}>()

const chart = ref<HTMLDivElement | null>(null)

const height = 300
const margin = { top: 20, right: 30, bottom: 30, left: 80 }

// --- Define line configurations here ---
const lineDefs = [
  { key: 'm1', color: colors.m1 },
  { key: 'pv', color: colors.pv },
  { key: 'sp', color: colors.sp },
  { key: 'kp', color: colors.kp },
  { key: 'ki', color: colors.ki },
  { key: 'kd', color: colors.kd },
  { key: 'kf', color: colors.kf },
  { key: 'op', color: colors.op },
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


function initChart() {
  const width = chart.value?.clientWidth ?? 500
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

  g.append('rect')
    .attr('width', width - margin.left - margin.right)
    .attr('height', height - margin.top - margin.bottom)
    .attr('fill', '#1e1e1e')
    .lower()

  gridX = g.append('g').attr('color', '#444')
    .attr('transform', `translate(0,${height - margin.top - margin.bottom})`)
  gridY = g.append('g').attr('color', '#444')

  gX = g.append('g').attr('transform', `translate(0,${height - margin.top - margin.bottom})`)
  gY = g.append('g')

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
    .attr('y', height - 40)
    .attr('fill', '#ccc')
    .style('font-size', '12px')
    .text('')

  zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([1, 10])
    .translateExtent([[0, 0], [width, height]])
    .on('zoom', (event) => {
      currentTransform = event.transform
      if (!currentTransform) return
      const zx = currentTransform.rescaleX(xScale)
      const zy = currentTransform.rescaleY(yScale)
      gX.call(d3.axisBottom(zx))
      gY.call(d3.axisLeft(zy))
      drawLines(zx, zy)
      drawGridlines(zx, zy, width)
    })

  svg.call(zoom)
}

function drawLines(zx = xScale, zy = yScale) {
  const getX = (d: DataPoint) => props.x1Type === 'time' ? zx(d.x1 as Date) : zx(d.x1 as number)
  lineDefs.forEach(def => {
    const line = d3.line<DataPoint>()
      .defined(d => typeof d[def.key] === 'number')
      .x(getX)
      .y(d => zy(d[def.key] as number))
    paths[def.key]?.attr('d', line(props.data))
  })
}

function updateChart() {
  if (!props.data?.length || !svg) return
  const width = chart.value?.clientWidth ?? 500

  const allYValues = lineDefs.flatMap(def =>
    props.data.map(d => d[def.key]).filter((v): v is number => typeof v === 'number')
  )
  const x1 = props.data.map(d => d.x1)

  const xDomain = props.x1Type === 'time'
    ? [d3.min(x1 as Date[])!, d3.max(x1 as Date[])!]
    : [d3.min(x1 as number[]) ?? 0, d3.max(x1 as number[]) ?? 100]
  const yDomain: [number, number] = [d3.min(allYValues) ?? 0, d3.max(allYValues) ?? 100]
  xScale.domain(xDomain)
  yScale.domain(yDomain)

  const zx = currentTransform ? currentTransform.rescaleX(xScale) : xScale
  const zy = currentTransform ? currentTransform.rescaleY(yScale) : yScale

  drawGridlines(zx, zy, width)
  gX.call(d3.axisBottom(zx))
  gY.call(d3.axisLeft(zy))
  drawLines(zx, zy)

  const stdevY1 = d3.deviation(props.data, d => d.y1 as number) ?? 0
  svg.select('.stdev-label')
    .text(`σ(y₁): ${formatAngle(stdevY1, 'deg', 2)}`)
}


function drawGridlines(
  zx: d3.ScaleLinear<number, number> | d3.ScaleTime<number, number>, 
  zy: d3.ScaleLinear<number, number>,
  width: number
) {
  gridX.call(
    d3.axisBottom(zx)
      .tickSize(-(height - margin.top - margin.bottom))
      .tickFormat(() => '')
  )
  gridY.call(
    d3.axisLeft(zy)
      .tickSize(-(width - margin.left - margin.right))
      .tickFormat(() => '')
  )
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
watch(() => props.data, updateChart, { deep: true })
onBeforeUnmount(() => {
  d3.select(chart.value).select('svg').remove()
})
</script>


<style scoped lang="scss">
svg {
  background-color: #1e1e1e;

  .line {
    transition: d 0.2s ease-in-out;
  }


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
    fill: #ccc;
  }


}


.stdev-label {
  font-family: sans-serif;
  pointer-events: none;
}


</style>
