<template>
  <div ref="chart" class="q-pa-md" style="height: 400px; width: 100%;"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as d3 from 'd3'

export type DataPoint = {
  time: number
  value: number
}

const props = defineProps<{ data: DataPoint[] }>();


const chart = ref(null)


const width = 800
const height = 400
const margin = { top: 20, right: 30, bottom: 30, left: 40 }
const clipId = 'plot-clip';


let svg: d3.Selection<SVGSVGElement, unknown, null, undefined>
let xScale: d3.ScaleLinear<number, number>
let yScale: d3.ScaleLinear<number, number>
let xAxis: d3.Selection<SVGGElement, unknown, null, undefined>
let yAxis: d3.Selection<SVGGElement, unknown, null, undefined>
let line: d3.Line<DataPoint>
let gX: d3.Selection<SVGGElement, unknown, null, undefined>
let gY: d3.Selection<SVGGElement, unknown, null, undefined>
let path: d3.Selection<SVGPathElement, unknown, null, undefined>
let zoom: d3.ZoomBehavior<SVGSVGElement, unknown>
let currentTransform: d3.ZoomTransform | null = null
let gridX: d3.Selection<SVGGElement, unknown, null, undefined>
let gridY: d3.Selection<SVGGElement, unknown, null, undefined>


function drawGridlines(zx: d3.ScaleLinear<number, number>, zy: d3.ScaleLinear<number, number>) {
  gridX.call(
    d3.axisBottom(zx)
      .tickSize(-height + margin.top + margin.bottom)
      .tickFormat(() => '')
  )
  gridY.call(
    d3.axisLeft(zy)
      .tickSize(-width + margin.left + margin.right)
      .tickFormat(() => '')
  )
}

function initChart() {
  xScale = d3.scaleLinear().range([0, width - margin.left - margin.right])
  yScale = d3.scaleLinear().range([height - margin.top - margin.bottom, 0])
  svg = d3.select(chart.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
  
  svg.append('defs')
    .append('clipPath')
    .attr('id', clipId)
    .append('rect')
    .attr('width', width - margin.left - margin.right)
    .attr('height', height - margin.top - margin.bottom);

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

    g.append('rect')
    .attr('width', width - margin.left - margin.right)
    .attr('height', height - margin.top - margin.bottom)
    .attr('fill', '#1e1e1e') // dark surface
    .lower() // ensure it sits behind everything

    gridX = g.append('g')
    .attr('class', 'grid-x')
    .attr('color', '#444')
    .attr('transform', `translate(0,${height - margin.top - margin.bottom})`)

    gridY = g.append('g')
    .attr('class', 'grid-y')
    .attr('color', '#444')


  xAxis = g.append('g')
    .attr('class', 'x-axis')
    .attr('color', '#999')
    .attr('transform', `translate(0,${height - margin.top - margin.bottom})`)

  yAxis = g.append('g')
    .attr('class', 'y-axis')
    .attr('color', '#999')

  line = d3.line<DataPoint>()
    .x(d => xScale(d.time))
    .y(d => yScale(d.value))

  path = g.append('path')
    .attr('class', 'line plot')
    .attr('fill', 'none')
    .attr('stroke', '#42b983')
    .attr('stroke-width', 2)
    .attr('clip-path', `url(#${clipId})`);

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
        path.attr('d', line.x(d => zx(d.time)).y(d => zy(d.value))(props.data))
        drawGridlines(zx, zy)

    })

  svg.call(zoom)
  gX = xAxis
  gY = yAxis
}

function updateChart() {
  if (!props.data || props.data.length === 0) return

  const times = props.data.map(d => d.time)
  const values = props.data.map(d => d.value)

  xScale.domain([d3.min(times) ?? 0, d3.max(times) ?? 100])
  yScale.domain([d3.min(values) ?? 0, d3.max(values) ?? 100])

  const zx = currentTransform ? currentTransform.rescaleX(xScale) : xScale
  const zy = currentTransform ? currentTransform.rescaleY(yScale) : yScale

  drawGridlines(zx, zy)
  gX.call(d3.axisBottom(zx))
  gY.call(d3.axisLeft(zy))

  path.datum(props.data).attr('d', line.x(d => zx(d.time)).y(d => zy(d.value)))
}

onMounted(() => {
  initChart()
  updateChart()
})

watch(() => props.data, updateChart, { deep: true })

onBeforeUnmount(() => {
  d3.select(chart.value).selectAll('*').remove()
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

</style>
