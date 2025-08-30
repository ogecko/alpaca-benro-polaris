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
import { easeCubicOut } from 'd3-ease'
import type { ScaleLinear } from 'd3-scale'
import type { Selection } from 'd3-selection';
import type { Transition } from 'd3-transition';
import type { BaseType } from 'd3-selection';

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
	pv: number
	domain: ScaleDomainType
}>()

const width = 400
const height = 300

const linearGroup = ref<SVGGElement | null>(null)
const circularGroup = ref<SVGGElement | null>(null)

const isLinear = computed(() => props.domain === 'linear_360')
const isCircular = computed(() => props.domain === 'circular_360' || props.domain === 'circular_180')
const renderKey = computed(() => `${props.domain}-${props.scaleStart}-${props.scaleRange}-${props.pv}`)

onMounted(renderScale)
watch(renderKey, renderScale)

// Computes an interpolator between old and new scale values for smooth transitions
function angleInterp(oldScale: ScaleLinear<number, number>, newScale: ScaleLinear<number, number>) {
  return (d: number) => interpolate(oldScale(d), newScale(d));
}


// Generates a transform string that rotates text around its own origin along a circular path
function labelTransformTween(interpFn: (t: number) => number, radius: number, radialOffset: number = 1.1) {
  return function (t: number) {
    const angle = interpFn(t);
    const x = radius * Math.cos(angle * Math.PI / 180) * radialOffset;
    const y = radius * Math.sin(angle * Math.PI / 180) * radialOffset;
	const rot = (angle > 90) ? 180 : 0 
    return `rotate(${rot}, ${x}, ${y}) rotate(${angle})`;
  };
}

// Renders and animates tick lines (major or minor) along a circular scale
function joinLines(group: Selection<SVGGElement, unknown, null, undefined>, 
	ticks: number[], oldScale: ScaleLinear<number, number>, 
	newScale: ScaleLinear<number, number>, 
	radius: number,
    tRaw: Transition<BaseType, number, SVGGElement, unknown>,
	{
		key = 'line',
		x1 = 0.9,
		x2 = 0.98,
	}: {
		key?: string,
		x1?: number;
		x2?: number;
	} = {} // default to empty object
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tRaw as Transition<BaseType, any, any, any>
  const interp = angleInterp(oldScale, newScale);

  group.selectAll<SVGLineElement, number>(`.${key}`)
    .data(ticks, d => d)
    .join(
      enter => enter.append('line')
	    .attr('class', key)
        .attr('x1', radius * x1)
        .attr('x2', radius * x2)
        .attr('y1', 0)
        .attr('y2', 0)
        .attr('opacity', 0)
        .attr('transform', d => `rotate(${oldScale(d)})`)
        .transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => `rotate(${interp(d)(t)})`),

      update => update.transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => `rotate(${interp(d)(t)})`),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .remove()
        .attrTween('transform', d => t => `rotate(${interp(d)(t)})`)
    );
}

// Renders and animates tick labels along a circular scale
function joinLabels(group: Selection<SVGGElement, unknown, null, undefined>, 
	ticks: number[], oldScale: ScaleLinear<number, number>, 
	newScale: ScaleLinear<number, number>, 
	radius: number, 
    tRaw: Transition<BaseType, number, SVGGElement, unknown>,
		{
		key = 'text',
		radialOffset = 1.1,
	}: {
		key?: string,
		radialOffset?: number,
	} = {} // default to empty object
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tRaw as Transition<BaseType, any, any, any>
  const interp = angleInterp(oldScale, newScale);

  group.selectAll<SVGTextElement, number>(`.${key}`)
    .data(ticks, d => d)
    .join(
      enter => enter.append('text')
 	    .attr('class', key)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('x', radius * radialOffset)
        .attr('y', 0)
        .text(d => d.toString())
        .attr('opacity', 0)
        .transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => labelTransformTween(interp(d), radius, radialOffset)(t)),

      update => update.transition(t)
        .attrTween('transform', d => t => labelTransformTween(interp(d), radius, radialOffset)(t)),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .remove()
        .attrTween('transform', d => t => labelTransformTween(interp(d), radius, radialOffset)(t))
    );
}


// Adds a marker (default: triangle) at a specified angle with smooth rotation transition
function joinMarker(
  group: Selection<SVGGElement, unknown, null, undefined>,
  angle: number,
  oldScale: ScaleLinear<number, number>,
  newScale: ScaleLinear<number, number>,
  radius: number,
  tRaw: Transition<BaseType, number, SVGGElement, unknown>,
	{
		key = 'marker',
		pathD = 'M0,-6 L6,6 L-6,6 Z',
		radialOffset = 1,
	}: {
		key?: string,
		pathD?: string,
		radialOffset?: number,
	} = {} // default to empty object

) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tRaw as Transition<BaseType, any, any, any>
  const interp = angleInterp(oldScale, newScale);

  group.selectAll<SVGPathElement, number>(`.${key}`)
    .data([angle])
    .join(
      enter => enter.append('path')
 	    .attr('class', key)
        .attr('d', pathD)
        .attr('transform', `rotate(${oldScale(angle)}) translate(${radius*radialOffset},0)`)
        .attr('opacity', 0)
        .transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => {
          const a = interp(d)(t);
          return `rotate(${a}) translate(${radius*radialOffset},0)`;
        }),

      update => update.transition(t)
        .attrTween('transform', d => t => {
          const a = interp(d)(t);
          return `rotate(${a}) translate(${radius*radialOffset},0)`;
        }),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .remove()
    );
}


// Renders a linear scale with animated axis ticks
function renderLinearScale() {
	if (!linearGroup.value) return

	const scale = scaleLinear()
		.domain([props.pv - props.scaleRange / 2, props.pv + props.scaleRange / 2])
		.range([0, width - 40])

	const axis = axisBottom(scale).ticks(10)
	const group = select(linearGroup.value)

	group.transition().duration(200).ease(easeCubicOut).call(axis)
}

let prevScale: ScaleLinear<number, number> | undefined;
// Renders a circular scale with major/minor ticks and labels
function renderCircularScale() {
  if (!circularGroup.value) return;

  const radius = width / 2 - 60;
  const newScale = scaleLinear()
    .domain([props.pv - props.scaleRange / 2, props.pv + props.scaleRange / 2])
    .range([-10, 190]);
  const oldScale = prevScale ?? newScale;
  prevScale = newScale;

  const bticks = newScale.ticks(10);
  const sticks = newScale.ticks(50);
  const group = select(circularGroup.value);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = transition().duration(200).ease(easeCubicOut) as Transition<BaseType, any, any, any>;

  joinLines(group, bticks, oldScale, newScale, radius, t, { key: 'majortick' });
  joinLines(group, sticks, oldScale, newScale, radius, t, { key: 'minortick', x1: 0.9, x2: 0.94});
  joinLabels(group, bticks, oldScale, newScale, radius, t, { key: 'minorlabel' });
  joinMarker(group, props.pv, oldScale, newScale, radius, t, { key: 'pvMarker', radialOffset: 0.85 });
}


// Dispatches rendering based on scale type (linear or circular)
function renderScale() {
	if (isLinear.value) {
		renderLinearScale()
	} else if (isCircular.value) {
		renderCircularScale()
	}
}

</script>
<style lang="scss">
g .majortick {
	stroke-width: 3;
	stroke: lightskyblue; 
}

g .minortick {
	stroke-width: 1;
	stroke: lightskyblue; 
}

g .minorlabel {
	fill: lightCyan; 
}

g .pvMarker {
	fill: lightcoral; 
}
</style>
