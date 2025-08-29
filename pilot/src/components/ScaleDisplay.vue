<template>
  <svg :width="width" :height="height">
    <g v-if="isLinear" ref="linearGroup" :transform="`translate(10, ${height / 2})`" />
    <g v-else-if="isCircular" ref="circularGroup" :transform="`translate(${width / 2}, 40)`" />
  </svg>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, computed } from 'vue'
import * as d3 from 'd3'
import type { Axis } from 'd3-axis'
import type { Selection } from 'd3-selection'
import type { NumberValue } from 'd3-scale'

export type ScaleDomainType =
  | 'linear_360'
  | 'circular_360'
  | 'circular_180'
  | 'alt_90'
  | 'dec_90'
  | 'ra_hours'

const props = defineProps<{
  scaleStart: number
  scaleRange: number
  domain: ScaleDomainType
}>()

const width = 400
const height = 300

const linearGroup = ref<SVGGElement | null>(null)
const circularGroup = ref<SVGGElement | null>(null)

const isLinear = computed(() => props.domain === 'linear_360')
const isCircular = computed(() => props.domain === 'circular_360' || props.domain === 'circular_180')
const renderKey = computed(() => `${props.domain}-${props.scaleStart}-${props.scaleRange}`)

onMounted(renderScale)

watch(renderKey, renderScale)

function renderLinearScale() {
  if (!linearGroup.value) return

  const scale = d3.scaleLinear()
    .domain([props.scaleStart, props.scaleStart + props.scaleRange])
    .range([0, width-40])

const axis: Axis<NumberValue> = d3.axisBottom(scale).ticks(10)

  const selection: Selection<SVGGElement, unknown, null, undefined> = d3.select(linearGroup.value)
  selection.call(axis)
}

function renderCircularScale() {
  if (!circularGroup.value) return

  const radius = width/2-60
  const scale = d3.scaleLinear()
    .domain([props.scaleStart, props.scaleStart + props.scaleRange])
    .range([-10, 190])

  const ticks = scale.ticks(10)
  const group = d3.select(circularGroup.value)

  group.selectAll('*').remove()

  ticks.forEach(tick => {
    const angle = scale(tick) * (Math.PI / 180)
    const x = radius * Math.cos(angle)
    const y = radius * Math.sin(angle)

    group.append('line')
      .attr('x1', x)
      .attr('y1', y)
      .attr('x2', x * 1.1)
      .attr('y2', y * 1.1)
      .attr('stroke', 'white')

    group.append('text')
      .attr('x', x * 1.25)
      .attr('y', y * 1.25)
      .attr('text-anchor', 'middle')
      .attr('alignment-baseline', 'middle')
      .attr('font-size', '12px')
      .attr('fill', 'white')
      .text(tick.toFixed(1))
  })
}

function renderScale() {
  if (isLinear.value) {
    renderLinearScale()
  } else if (isCircular.value) {
    renderCircularScale()
  }
}

</script>
