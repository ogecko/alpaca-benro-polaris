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
	if (!circularGroup.value) return

	const radius = width / 2 - 60
	const newScale = scaleLinear()
		.domain([props.pv - props.scaleRange / 2, props.pv + props.scaleRange / 2])
		.range([-10, 190]);
	const oldScale = prevScale ?? newScale; // fallback on first render
	prevScale = newScale; // stash for next time

	const ticks: number[] = newScale.ticks(10)
	const group = select(circularGroup.value)
	const t = transition().duration(200).ease(easeCubicOut)

	// Bind data to lines
	const lines: d3.Selection<SVGLineElement, number, SVGGElement, unknown> =
		group.selectAll<SVGLineElement, number>('line')
			.data(ticks, (d: number) => d);

	// const tickAngleCache = new WeakMap<SVGLineElement, number>();

	lines.join(
		enter => enter.append('line')
			.attr('stroke', 'white')
			.attr('x1', radius * 0.9)
			.attr('x2', radius * 1.0)
			.attr('y1', 0)
			.attr('y2', 0)
			.attr('opacity', 0)
			.attr('transform', d => `rotate(${oldScale(d)})`)
			.transition(t)
			.attr('opacity', 1)
			.attrTween('transform', function (d) {
				const interp = interpolate(oldScale(d), newScale(d));
				return t => `rotate(${interp(t)})`;
			}),

		update => update.transition(t)
			.attr('stroke', 'white')
			.attr('opacity', 1)
			.attrTween('transform', function (d) {
				const interp = interpolate(oldScale(d), newScale(d));
				return t => `rotate(${interp(t)})`;
			}),

		exit => exit.transition(t)
			.remove()
			.attr('opacity', 0)
			.attrTween('transform', function (d) {
				const interp = interpolate(oldScale(d), newScale(d));
				return t => `rotate(${interp(t)})`;
			})
	)
	// Bind data to text
	const labels: d3.Selection<SVGTextElement, number, SVGGElement, unknown> =
		group.selectAll<SVGTextElement, number>('text')
			.data(ticks, (d: number) => d);

	labels.join(
		enter => enter.append('text')
			.attr('fill', 'white')
			.attr('text-anchor', 'middle')
			.attr('dominant-baseline', 'middle')
			.attr('x', radius * 1.1)
			.attr('y', 0)
			.text(d => d.toString())
			.attr('opacity', 0)
			.attr('transform', d => `rotate(${oldScale(d)})`)
			.transition(t)
			.attr('opacity', 1)
			.attrTween('transform', function (d) {
				const interp = interpolate(oldScale(d), newScale(d));
				return function (t) {
					const angle = interp(t);
					const x = radius * Math.cos(angle * Math.PI / 180) * 1.1;
					const y = radius * Math.sin(angle * Math.PI / 180) * 1.1;
					return `rotate(${-angle}, ${x}, ${y}) rotate(${angle})`;
				};
			}),

		update => update.transition(t)
			.attrTween('transform', function (d) {
				const interp = interpolate(oldScale(d), newScale(d));
				return function (t) {
					const angle = interp(t);
					const x = radius * Math.cos(angle * Math.PI / 180) * 1.1;
					const y = radius * Math.sin(angle * Math.PI / 180) * 1.1;
					return `rotate(${-angle}, ${x}, ${y}) rotate(${angle})`;
				};
			}),

		exit => exit.transition(t)
			.remove()
			.attr('opacity', 0)
			.attrTween('transform', function (d) {
				const interp = interpolate(oldScale(d), newScale(d));
				return function (t) {
					const angle = interp(t);
					const x = radius * Math.cos(angle * Math.PI / 180) * 1.1;
					const y = radius * Math.sin(angle * Math.PI / 180) * 1.1;
					return `rotate(${-angle}, ${x}, ${y}) rotate(${angle})`;
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
