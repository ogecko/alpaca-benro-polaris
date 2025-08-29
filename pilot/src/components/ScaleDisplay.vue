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

function angleInterp(oldScale: ScaleLinear<number, number>, newScale: ScaleLinear<number, number>) {
  return (d: number) => interpolate(oldScale(d), newScale(d));
}

function labelTransformTween(interpFn: (t: number) => number, radius: number) {
  return function (t: number) {
    const angle = interpFn(t);
    const x = radius * Math.cos(angle * Math.PI / 180) * 1.1;
    const y = radius * Math.sin(angle * Math.PI / 180) * 1.1;
    return `rotate(${-angle}, ${x}, ${y}) rotate(${angle})`;
  };
}

function joinLines(group: Selection<SVGGElement, unknown, null, undefined>, 
	ticks: number[], oldScale: ScaleLinear<number, number>, 
	newScale: ScaleLinear<number, number>, 
	radius: number,
    tRaw: Transition<BaseType, number, SVGGElement, unknown>,
	{
		key = 'line',
		x1 = 0.9,
		x2 = 0.98,
		thickness = 1.0,
		color = 'white'
	}: {
		key?: string,
		x1?: number;
		x2?: number;
		thickness?: number;
		color?: string;
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
        .attr('stroke', color)
		.attr('stroke-width', thickness)
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

function joinLabels(group: Selection<SVGGElement, unknown, null, undefined>, 
	ticks: number[], oldScale: ScaleLinear<number, number>, 
	newScale: ScaleLinear<number, number>, 
	radius: number, 
    tRaw: Transition<BaseType, number, SVGGElement, unknown>,
		{
		key = 'text',
		color = 'white'
	}: {
		key?: string,
		color?: string;
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
        .attr('fill', color)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('x', radius * 1.1)
        .attr('y', 0)
        .text(d => d.toString())
        .attr('opacity', 0)
        .attr('transform', d => `rotate(${oldScale(d)})`)
        .transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => labelTransformTween(interp(d), radius)(t)),

      update => update.transition(t)
        .attrTween('transform', d => t => labelTransformTween(interp(d), radius)(t)),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .remove()
        .attrTween('transform', d => t => labelTransformTween(interp(d), radius)(t))
    );
}

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

  joinLines(group, bticks, oldScale, newScale, radius, t, { key: 'major', thickness: 3, color: 'lightskyblue' });
  joinLines(group, sticks, oldScale, newScale, radius, t, { key: 'minor', x1: 0.9, x2: 0.94,  color: 'cornflowerblue'});
  joinLabels(group, bticks, oldScale, newScale, radius, t, { color: 'lightCyan' });
}



function renderScale() {
	if (isLinear.value) {
		renderLinearScale()
	} else if (isCircular.value) {
		renderCircularScale()
	}
}

</script>
