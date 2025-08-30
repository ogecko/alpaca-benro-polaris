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
import { isAngleBetween } from 'src/utils/angles'
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


function formatDegrees(v: number): string {
  return `${Math.round(v)}°`;
}

function formatArcMinutes(v: number): string {
  const arcmin = Math.round((v % 1) * 60);
  const deg = Math.floor(v);
  return arcmin === 0 ? formatDegrees(deg) : `${arcmin}′`;
}

function formatArcSeconds(v: number): string {
  const arcsec = Math.round((v * 3600) % 60);
  const arcmin = Math.floor((v * 60) % 60);
  const deg = Math.floor(v);
  if (arcsec !== 0) return `${arcsec}″`;
  if (arcmin !== 0) return `${arcmin}′`;
  return formatDegrees(deg);
}


function generateTicks(scaleStart: number, scaleRange: number): MarkDatum[] {
  const ticks: MarkDatum[] = [];

  const pathLg = 'M0,0 L15,0';
  const pathMd = 'M0,0 L10,0';
  const pathSm = 'M0,0 L5,0';

const steps = [
  { step: 90, unit: '°', format: formatDegrees },
  { step: 30, unit: '°', format: formatDegrees },
  { step: 10, unit: '°', format: formatDegrees },
  { step: 2, unit: '°', format: formatDegrees },
  { step: 30 / 60, unit: `'`, format: formatArcMinutes },
  { step: 10 / 60, unit: `'`, format: formatArcMinutes },
  { step: 2 / 60, unit: `'`, format: formatArcMinutes },
  { step: 30 / 3600, unit: `"`, format: formatArcSeconds },
  { step: 10 / 3600, unit: `"`, format: formatArcSeconds },
  { step: 2 / 3600, unit: `"`, format: formatArcSeconds },
];

  // finds the first step that satisfies the spacing constraint. 
  const minLabelSpacingDeg = 20; // minimum spacing between md labels in degrees
  const screenAngleRange = 200;
  const maxLabels = screenAngleRange/minLabelSpacingDeg; // around 20

  // Find the finest step that still keeps label count ≤ maxLabels
  const mdIndex = steps.findIndex(s => (scaleRange / s.step) > maxLabels);
  const safeMdIndex = mdIndex >= 0 ? mdIndex : steps.length - 1;

  const md = steps[safeMdIndex];
  console.log('initial md',md)
  const lg = steps[Math.max(0, safeMdIndex - 1)];
  const sm = steps[Math.min(steps.length - 1, safeMdIndex + 1)];

  if (!md || !lg || !sm) return [];
  console.log('lg',lg,'md',md,'sm',sm)

  const start = Math.floor(scaleStart / sm.step) * sm.step;
  const end = scaleStart + scaleRange;
  const count = Math.floor((end - start) / sm.step);
  const lgMultiple = Math.round(lg.step / sm.step);
  const mdMultiple = Math.round(md.step / sm.step);

  for (let i = 0; i <= count; i++) {
    const v = +(start + i * sm.step).toFixed(6); 
    const isLarge = i % lgMultiple === 0;
    const isMedium = i % mdMultiple === 0;


    if (isLarge) {
      ticks.push({
        key: `label-lg-${v.toFixed(6)}`,
        angle: v,
        label: lg.format(v),
        level: 'label-lg',
        offset: 1.28
      });
      ticks.push({
        key: `tick-lg-${v.toFixed(6)}`,
        angle: v,
        path: pathLg,
        level: 'tick-lg'
      });
    } else if (isMedium) {
      ticks.push({
        key: `label-md-${v.toFixed(6)}`,
        angle: v,
        label: md.format(v),
        level: 'label-md',
        offset: 1.18
      });
      ticks.push({
        key: `tick-md-${v.toFixed(6)}`,
        angle: v,
        path: pathMd,
        level: 'tick-md'
      });
    } else {
      ticks.push({
        key: `tick-sm-${v.toFixed(6)}`,
        angle: v,
        path: pathSm,
        level: 'tick-sm'
      });
    }
  }

  return ticks;
}



// Computes an interpolator between old and new scale values for smooth transitions
function angleInterp(oldScale: ScaleLinear<number, number>, newScale: ScaleLinear<number, number>) {
  return (d: number) => interpolate(oldScale(d), newScale(d));
}



type MarkDatum = {
  key?: string;       // element key used by D3 to match existing elements
  angle: number;      // domain angle in degrees
  offset?: number;    // radial offset from the radius 1=no offset, 0.9=inside, 1.1=outside
  label?: string;     // text string to render at radial position
  path?: string;      // SVG path string to render at radial position
  level?: string;     // optional class name added to element
};

function joinMarks(
  group: Selection<SVGGElement, unknown, null, undefined>,
  marks: MarkDatum[],
  oldScale: ScaleLinear<number, number>,
  newScale: ScaleLinear<number, number>,
  radius: number,
  tRaw: Transition<BaseType, MarkDatum, SVGGElement, unknown>,
  cname: string = 'mark'    // identifies elements for this call of joinMarks
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tRaw as Transition<BaseType, any, any, any>;
  const [min, max] = newScale.domain() as [number, number];
  const visibleMarks = marks.filter(m => isAngleBetween(m.angle, min, max));
  const interp = angleInterp(oldScale, newScale);

  group.selectAll<SVGTextElement | SVGPathElement, MarkDatum>(`.${cname}`)
    .data(visibleMarks, d => `${d.key}`)
    .join(
      enter => enter.append(d => document.createElementNS('http://www.w3.org/2000/svg', d.path ? 'path' : 'text'))
        .attr('class', d => `${cname} ${d.level}`.trim())
        .each(function (d) {
            const sel = select(this);
            if (d.path) {
              sel.attr('d', d.path)
            } else if (d.label) {
              sel.text(d.label)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle');
            }
        })
        .attr('opacity', 0)
        .transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const flip = (d.label) ? angle > 90 : false;
          return radialTransform(angle, radius, d.offset ?? 1.0, flip);
        }),

      update => update.transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const flip = (d.label) ? angle > 90 : false;
          return radialTransform(angle, radius, d.offset ?? 1, flip);
        }),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const flip = (d.label) ? angle > 90 : false;
          return radialTransform(angle, radius, d.offset ?? 1, flip);
        })
        .remove()
    );
}



function radialTransform(angle: number, radius: number, radialOffset: number = 1.0, flip: boolean = false): string {
  const x = radius * Math.cos(angle * Math.PI / 180) * radialOffset;
  const y = radius * Math.sin(angle * Math.PI / 180) * radialOffset;
  const rot = flip ? 180 : 0;
  return `translate(${x}, ${y}) rotate(${rot+angle})`;
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

  const low = props.pv - props.scaleRange / 2
  const high = props.pv + props.scaleRange / 2
  const ticks = generateTicks(low,props.scaleRange)
console.log(ticks)
  const radius = width / 2 - 60;
  const newScale = scaleLinear().domain([low, high]).range([-10, 190]);
  const oldScale = prevScale ?? newScale;
  prevScale = newScale;

  const group = select(circularGroup.value);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = transition().duration(200).ease(easeCubicOut) as Transition<BaseType, any, any, any>;

  // joinLines(group, bticks, oldScale, newScale, radius, t, { key: 'majortick' });
  // joinLines(group, sticks, oldScale, newScale, radius, t, { key: 'minortick', x1: 0.9, x2: 0.94});
  // joinLabels(group, bticks, oldScale, newScale, radius, t, { key: 'minorlabel' });
  // joinMarker(group, props.pv, oldScale, newScale, radius, t, { key: 'pvMarker', radialOffset: 0.85 });
  joinMarks(group, ticks, oldScale, newScale, radius, t, 'tickMarks' );
  joinMarks(group, [{angle:90.2, path:'M0,0 L60,0'}], oldScale, newScale, radius, t, 'lineMark' );
  joinMarks(group, [{angle:180.2, path:'M0,0 L-20,10 L-20,-10 Z', offset:1}], oldScale, newScale, radius, t, 'pvMark');
  joinMarks(group, [{angle:180.4, path:'M0,0 L-10,5 L-10,-5 L-10,-10 L-10,10 L2,10 L2,-10 L-10,-10 L-10,-5 Z', offset:0.85}], oldScale, newScale, radius, t, 'spMark');
  joinMarks(group, [{angle:180.1, label:'test', offset:0.5}], oldScale, newScale, radius, t, 'textMark');
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
g .tick-lg {
	stroke-width: 5;
	stroke: lightskyblue; 
}

g .tick-md {
	stroke-width: 2;
	stroke: lightskyblue; 
}

g .tick-sm {
	stroke-width: 0.8;
	stroke: lightskyblue; 
}

g .label-lg {
	fill: white; 
  font-size: 20px;
}

g .label-md {
	fill: lightblue; 
  font-size: 12px;
}

g .pvMarker {
	fill: lightcoral; 
}

g .pvMark {
	fill: lightcoral; 
}

g .spMark {
	fill: rgb(105, 219, 117); 
}

g .lineMark {
	stroke: red; 
	stroke-width: 5;

}

// g {
// 	stroke: red; 
// 	stroke-width: 1;
// }

</style>
