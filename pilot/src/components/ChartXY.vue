<template>
  <div ref="chart" style="height: 300px; width: 100%;"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as d3 from 'd3'
import { formatAngle } from 'src/utils/scale'

export type DataPoint = {
  x1: number | Date
  y1: number
  y2: number
  y3?: number
}

const props = defineProps<{ 
  data: DataPoint[] 
  x1Type: 'number' | 'time'
}>();

const chart = ref(null)


const width = 500
const height = 300
const margin = { top: 20, right: 30, bottom: 30, left: 80 }
const clipId = 'plot-clip';

let svg: d3.Selection<SVGSVGElement, unknown, null, undefined>
let xScale: d3.ScaleTime<number, number> | d3.ScaleLinear<number, number> 
let yScale: d3.ScaleLinear<number, number>
let xAxis: d3.Selection<SVGGElement, unknown, null, undefined>
let yAxis: d3.Selection<SVGGElement, unknown, null, undefined>
let liney1: d3.Line<DataPoint>
let liney2: d3.Line<DataPoint>
let liney3: d3.Line<DataPoint>
let gX: d3.Selection<SVGGElement, unknown, null, undefined>
let gY: d3.Selection<SVGGElement, unknown, null, undefined>
let pathy1: d3.Selection<SVGPathElement, unknown, null, undefined>
let pathy2: d3.Selection<SVGPathElement, unknown, null, undefined>
let pathy3: d3.Selection<SVGPathElement, unknown, null, undefined>
let zoom: d3.ZoomBehavior<SVGSVGElement, unknown>
let currentTransform: d3.ZoomTransform | null = null
let gridX: d3.Selection<SVGGElement, unknown, null, undefined>
let gridY: d3.Selection<SVGGElement, unknown, null, undefined>


function drawGridlines(
  zx: d3.ScaleLinear<number, number> | d3.ScaleTime<number, number>, 
  zy: d3.ScaleLinear<number, number>
) {
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
    xScale = props.x1Type === 'time'
      ? d3.scaleTime().range([0, width - margin.left - margin.right])
      : d3.scaleLinear().range([0, width - margin.left - margin.right])    
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

    liney1 = d3.line<DataPoint>()
        .x(d => xScale(d.x1))
        .y(d => yScale(d.y1))

    liney2 = d3.line<DataPoint>()
        .x(d => xScale(d.x1))
        .y(d => yScale(d.y2))

    liney3 = d3.line<DataPoint>()
        .defined(d => typeof d.y3 === 'number')
        .x(d => xScale(d.x1))
        .y(d => yScale(d.y3!))

    pathy1 = g.append('path')
        .attr('class', 'line ploty1')
        .attr('fill', 'none')
        .attr('stroke', '#00695c ')
        .attr('stroke-width', 2)
        .attr('clip-path', `url(#${clipId})`);

    pathy2 = g.append('path')
        .attr('class', 'line ploty2')
        .attr('fill', 'none')
        .attr('stroke', '#cddc39')
        .attr('stroke-width', 2)
        .attr('clip-path', `url(#${clipId})`);

    pathy3 = g.append('path')
        .attr('class', 'line ploty3')
        .attr('fill', 'none')
        .attr('stroke', '#d84315')
        .attr('stroke-width', 2)
        .attr('clip-path', `url(#${clipId})`);

    svg.append('text')
      .attr('class', 'stdev-label')
      .attr('text-anchor', 'end')
      .attr('x', width - 40)
      .attr('y', height - 40)
      .attr('fill', '#ccc')
      .style('font-size', '12px')
      .text('');

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

            const getZX = (d: DataPoint) => props.x1Type === 'time' ? zx(d.x1 as Date) : zx(d.x1 as number)
            pathy1.attr('d', liney1.x(getZX).y(d => zy(d.y1))(props.data))
            pathy2.attr('d', liney2.x(getZX).y(d => zy(d.y2))(props.data))
            pathy3.attr('d', liney3.x(getZX).y(d => zy(d.y3 ?? 0))(props.data))

            drawGridlines(zx, zy)

        })

    svg.call(zoom)
    gX = xAxis
    gY = yAxis
}

function updateChart() {
  if (!props.data || props.data.length === 0) return

  const x1 = props.data.map(d => d.x1)
  const y1s = props.data.map(d => d.y1)
  const y2s = props.data.map(d => d.y2);
  const y3s = props.data.map(d => d.y3).filter((v): v is number => typeof v === 'number');
  const allys = [...y1s, ...y2s, ...y3s]

  const xDomain = props.x1Type === 'time'
  ? [d3.min(x1.map(t => t as Date))!, d3.max(x1.map(t => t as Date))!]
  : [d3.min(x1 as number[]) ?? 0, d3.max(x1 as number[]) ?? 100]
  xScale.domain(xDomain)
  yScale.domain([d3.min(allys) ?? 0, d3.max(allys) ?? 100])

  const zx = currentTransform ? currentTransform.rescaleX(xScale) : xScale
  const zy = currentTransform ? currentTransform.rescaleY(yScale) : yScale

  drawGridlines(zx, zy)
  gX.call(d3.axisBottom(zx))
  gY.call(d3.axisLeft(zy))

  const getX = (d: DataPoint) => props.x1Type === 'time' ? xScale(d.x1 as Date) : xScale(d.x1 as number)
  liney1 = d3.line<DataPoint>().x(getX).y(d => yScale(d.y1))
  liney2 = d3.line<DataPoint>().x(getX).y(d => yScale(d.y2))
  liney3 = d3.line<DataPoint>()
    .defined(d => typeof d.y3 === 'number')
    .x(getX)
    .y(d => yScale(d.y3!))

  const getZX = (d: DataPoint) => props.x1Type === 'time' ? zx(d.x1 as Date) : zx(d.x1 as number)
  pathy1.attr('d', liney1.x(getZX).y(d => zy(d.y1))(props.data))
  pathy2.attr('d', liney2.x(getZX).y(d => zy(d.y2))(props.data))
  pathy3.attr('d', liney3.x(getZX).y(d => zy(d.y3 ?? 0))(props.data))

  const stdevY1 = d3.deviation(props.data, d => d.y1) ?? 0;
  svg.select('.stdev-label')
    .text(`σ(y₁): ${formatAngle(stdevY1,'deg',2)}`);


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


.stdev-label {
  font-family: sans-serif;
  pointer-events: none;
}


</style>
