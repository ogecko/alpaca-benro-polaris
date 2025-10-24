<template>
  <div ref="chart" style="height: 300px; width: 100%;">
    <q-resize-observer @resize="onResize" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import { formatAngle } from 'src/utils/scale'
// import { deg2fulldms } from 'src/utils/angles'
export type DataPoint = Record<string, number | Date | undefined>

const props = defineProps<{ 
  data: DataPoint[] 
  x1Type: 'number' | 'time'
}>()

const chart = ref<HTMLDivElement | null>(null)

const height = 300
const margin = { top: 20, right: 30, bottom: 30, left: 80 }

const colors = {
  sp: 'hsl(132, 79%, 60%)',      // Green
  pv: 'hsl(0,   0%, 100%)',      // White
  op: 'hsl(195, 99%, 70%)',      // Cyan
  m1: 'hsl(218, 63%, 32%)',      // Dark Blue
  kp: 'hsl(70,  60%, 30%)',      // Dark Lime
  ki: 'hsl(50,  60%, 30%)',      // Dark Yellow   
  kd: 'hsl(20,  60%, 30%)',      // Dark Red
  kf: 'hsl(320, 70%, 30%)',    // Dark Magenta
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
      updateChart()
    })

  svg.call(zoom)
  drawLegend(svg, width)
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
  xScale.domain(xDomain)

  const yDomain: [number, number] = [d3.min(allYValues) ?? 0, d3.max(allYValues) ?? 100]
  yScale.domain(yDomain)

  const tX = gX.transition().duration(180).ease(d3.easeLinear)
  const tY = gY.transition().duration(180).ease(d3.easeLinear)
  const zx = currentTransform ? currentTransform.rescaleX(xScale) : xScale
  const zy = currentTransform ? currentTransform.rescaleY(yScale) : yScale

  tX.call(d3.axisBottom(zx)).style('color', '#aaa')
  tY.call(d3.axisLeft(zy)).style('color', '#aaa')


  drawGridlines(zx, zy, width)
  drawLines(zx, zy)

  // const stdevY1 = d3.deviation(props.data, d => d.y1 as number) ?? 0
  // svg.select('.stdev-label')
  //   .text(`σ(y₁): ${formatAngle(stdevY1, 'deg', 2)}`)
  drawStatistics(svg)

  drawLegend(svg, width)
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

    const rms = Math.sqrt(d3.mean(errors.map(e => e * e)) ?? 0)
    label = `RMS Error: ${formatAngle(rms, 'deg', 2)}`
  } else if (hasOP) {
    const opValues = props.data
      .map(d => d.OP)
      .filter((v): v is number => typeof v === 'number')

    const stdevOP = d3.deviation(opValues) ?? 0
    label = `σ(OP): ${formatAngle(stdevOP, 'deg', 2)}`
  }

  svg.select('.stdev-label').text(label)
}



function drawLegend(svg: d3.Selection<SVGSVGElement, unknown, null, undefined>, width: number) {
  // Remove any existing legend
  svg.select('.legend').remove()

  const legendData = lineDefs.filter(def =>
    props.data.some(d => typeof d[def.key] === 'number')
  )

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
    zx = xScale, 
    zy = yScale,
) {
  lineDefs.forEach(def => {
  const line = d3.line<DataPoint>()
    .defined(d => typeof d[def.key] === 'number')
    .x(d => zx(props.x1Type === 'time' ? d.x1 as Date : d.x1 as number))
    .y(d => zy(d[def.key] as number))

  paths[def.key]?.attr('d', line(props.data))
    .attr('transform', null) // reset any previous transform
  })
  const dx = zx(props.x1Type === 'time'
    ? props.data[1]?.x1 as Date
    : props.data[1]?.x1 as number
  ) - zx(props.x1Type === 'time'
    ? props.data[0]?.x1 as Date
    : props.data[0]?.x1 as number
  )

  lineDefs.forEach(def => {
    paths[def.key]?.attr('transform', `translate(${dx},0)`) // start offset
      .transition()
      .duration(170)
      .ease(d3.easeLinear)
      .attr('transform', `translate(0,0)`) // animate back to origin
  })
}


function drawGridlines(
  zx: d3.ScaleLinear<number, number> | d3.ScaleTime<number, number>, 
  zy: d3.ScaleLinear<number, number>,
  width: number,
) {
gridX.transition().duration(180).ease(d3.easeLinear).call(
  d3.axisBottom(zx)
    .tickSize(-(height - margin.top - margin.bottom))
    .tickFormat(() => '')
)

gridY.transition().duration(180).ease(d3.easeLinear).call(
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
    color: #ccc;
  }


}


.stdev-label {
  font-family: sans-serif;
  pointer-events: none;
}


</style>
