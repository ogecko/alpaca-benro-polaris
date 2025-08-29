<template>
  <svg :width="width" :height="height">
    <g v-if="isLinear" ref="linearGroup" :transform="`translate(10, ${height / 2})`" />
    <g v-else-if="isCircular" ref="circularGroup" :transform="`translate(${width / 2}, 40)`" />
  </svg>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, computed } from 'vue'
import { scaleLinear } from 'd3-scale'
import { axisBottom } from 'd3-axis'
import { select } from 'd3-selection'
import { transition } from 'd3-transition'
import { interpolate } from 'd3-interpolate'
// import { zoom } from 'd3-zoom'
import { easeCubicOut } from 'd3-ease'
import type { ScaleLinear } from 'd3-scale'

// import type { Axis } from 'd3-axis'
// import type { Selection } from 'd3-selection'
// import type { NumberValue } from 'd3-scale'

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

  const scale = scaleLinear()
    .domain([props.scaleStart, props.scaleStart + props.scaleRange])
    .range([0, width - 40])

  const axis = axisBottom(scale).ticks(10)
  const group = select(linearGroup.value)

  group.transition()
    .duration(600)
    .ease(easeCubicOut)
    .call(axis)
}

let prevScale: ScaleLinear<number, number> | undefined;
function renderCircularScale() {
  if (!circularGroup.value) return

  const radius = width / 2 - 60
  const newScale = scaleLinear()
    .domain([props.scaleStart, props.scaleStart + props.scaleRange])
    .range([-10, 190]);
  const oldScale = prevScale ?? newScale; // fallback on first render
  prevScale = newScale; // stash for next time

  const ticks: number[]  = newScale.ticks(10)
  const group = select(circularGroup.value)
  const t = transition().duration(600).ease(easeCubicOut)

  // Bind data to lines
  const lines: d3.Selection<SVGLineElement, number, SVGGElement, unknown> =
    group.selectAll<SVGLineElement, number>('line')
        .data(ticks, (d: number) => d);

// const tickAngleCache = new WeakMap<SVGLineElement, number>();

lines.join(
enter => enter.append('line')
  .attr('stroke', 'white')
  .attr('x1', d => radius * Math.cos(oldScale(d) * Math.PI / 180) * 0.9)
  .attr('y1', d => radius * Math.sin(oldScale(d) * Math.PI / 180) * 0.9)
  .attr('x2', d => radius * Math.cos(oldScale(d) * Math.PI / 180) * 1.1)
  .attr('y2', d => radius * Math.sin(oldScale(d) * Math.PI / 180) * 1.1)
  .attr('opacity', 0)
  .transition(t)
  .attr('opacity', 1)
  .tween('rotate', function(d) {
    const node = this as SVGLineElement;
    const interp = interpolate(oldScale(d), newScale(d));
    return function(t) {
      const angle = interp(t);
      const x1 = radius * Math.cos(angle * Math.PI / 180) * 0.9;
      const y1 = radius * Math.sin(angle * Math.PI / 180) * 0.9;
      const x2 = radius * Math.cos(angle * Math.PI / 180) * 1.1;
      const y2 = radius * Math.sin(angle * Math.PI / 180) * 1.1;
      select(node).attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2);
    };
  }),

  update => update.transition(t)
    .tween('rotate', function(d) {
      const node = this as SVGLineElement;
      const interp = interpolate(oldScale(d), newScale(d));
      return function(t) {
        const angle = interp(t);
        const x1 = radius * Math.cos(angle * Math.PI / 180) * 0.9;
        const y1 = radius * Math.sin(angle * Math.PI / 180) * 0.9;
        const x2 = radius * Math.cos(angle * Math.PI / 180) * 1.1;
        const y2 = radius * Math.sin(angle * Math.PI / 180) * 1.1;
        select(node)
          .attr('x1', x1)
          .attr('y1', y1)
          .attr('x2', x2)
          .attr('y2', y2);
      };
    }),

  exit => exit.transition(t).attr('opacity', 0).remove()
);

  // Bind data to text
  const labels: d3.Selection<SVGTextElement, number, SVGGElement, unknown> =
    group.selectAll<SVGTextElement, number>('text')
        .data(ticks, (d: number) => d);

  labels.join(
  enter => enter.append('text')
    .attr('fill', 'white')
    .attr('x', d => radius * Math.cos(oldScale(d) * Math.PI / 180)*1.1)
    .attr('y', d => radius * Math.sin(oldScale(d) * Math.PI / 180)*1.1)
    .text(d => d.toString())
    .attr('opacity', 0)
    .transition(t)
    .attr('opacity', 1)
    .tween('rotate', function(d) {
        const node = this as SVGTextElement;
        const interp = interpolate(oldScale(d), newScale(d));
        return function(t) {
        const angle = interp(t);
        const x = radius * Math.cos(angle * Math.PI / 180) * 1.1;
        const y = radius * Math.sin(angle * Math.PI / 180) * 1.1;
        select(node).attr('x', x).attr('y', y);
        };
    }),

  update => update.transition(t)
    .tween('rotate', function(d) {
      const node = this as SVGTextElement;
      const interp = interpolate(oldScale(d), newScale(d));
      return function(t) {
        const angle = interp(t);
        const x = radius * Math.cos(angle * Math.PI / 180)*1.1;
        const y = radius * Math.sin(angle * Math.PI / 180)*1.1;
        select(node)
          .attr('x', x)
          .attr('y', y);
      };
    })
);

}



function renderScale() {
  if (isLinear.value) {
    renderLinearScale()
  } else if (isCircular.value) {
    renderCircularScale()
  }
}

</script>
