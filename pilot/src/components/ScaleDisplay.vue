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
import { isAngleBetween, wrapTo360 } from 'src/utils/angles'
import type { ScaleLinear } from 'd3-scale'
import type { Selection } from 'd3-selection';
import type { Transition } from 'd3-transition';
import type { BaseType } from 'd3-selection';

export type DomainStyleType =
	| 'linear_360'
	| 'circular_360'
	| 'semihi_360'
	| 'semilo_360'
	| 'circular_180'
	| 'alt_90'
	| 'dec_90'
	| 'ra_hours'

const domainStyle = {
  'linear_360': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'circular_360': { centerVw: 0.5, centerVh: 0.1, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'semihi_360': { centerVw: 0.5, centerVh: 0.7, sAngleLow: 170, sAngleHigh: 370, dAngleFn: wrapTo360 },
	'semilo_360': { centerVw: 0.5, centerVh: 0.35, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'circular_180': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'alt_90': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'dec_90': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'ra_hours': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
}

const props = defineProps<{
	scaleStart: number
	scaleRange: number
	pv: number
	domain: DomainStyleType
}>()

const width = 400
const height = 300

const linearGroup = ref<SVGGElement | null>(null)
const circularGroup = ref<SVGGElement | null>(null)

const isLinear = computed(() => props.domain === 'linear_360')
const isCircular = computed(() => ['circular_360', 'semihi_360', 'semilo_360', 'circular_180'].includes(props.domain))
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

interface Step {
  stepSize: number;
  unit: string;
  format: (v: number) => string;
  label: string;
}

// Adds a tick and its label to the ticks array, promoting to higher label levels if appropriate and ensuring only the highest-priority tick at each angle.
function pushTick(
  ticks: MarkDatum[],
  level: 'lg' | 'md' | 'sm',
  v: number,
  format: (v: number) => string
) {
  const keyBase = v.toFixed(6);
  const angle = v;
  let labelText = format(v);

  // Promote md ticks that look like whole degrees
  if (['md','sm'].includes(level) && /^\d+°$/.test(labelText)) {
    level = 'lg'
  } 
  // Promote sm ticks that look like whole minutes
  if ('sm' === level  && /^\d+′$/.test(labelText)) {
    level = 'md'
  } 
  // Promote sm ticks that look like 60" to whole minutes
  if ('sm' === level  && /^60″$/.test(labelText)) {
    level = 'md'
    labelText = formatArcMinutes(v)
  } 

  // Remove any lower-priority duplicate labels
  const labelPriority = { lg: 3, md: 2, sm: 1 };
  const existingIndex = ticks.findIndex(t => t.angle === angle);
  const existing = ticks[existingIndex];
  const existingLevel = existing?.level?.slice(6) as 'lg' | 'md' | 'sm' | undefined;
  if (existingLevel) {
    if (labelPriority[level] <= labelPriority[existingLevel]) {
      return;                         // dont push a lower-priority or duplicate level tick
    } else {
      ticks.splice(existingIndex, 1); // remove lower-priority level, existing tick
    }
  }

  // push the label and tickmark onto the ticks array  
  const pathMap = { lg: 'M-3,0 L15,0', md: 'M-3,0 L10,0', sm: 'M-3,0 L8,0' };
  const offsetMap = { lg: 1.28, md: 1.18, sm: 1.13 }

  ticks.push({
    key: `label-${level}-${keyBase}`,
    angle,
    label: labelText,
    level: `label-${level}`,
    offset: offsetMap[level],
  });

  ticks.push({
    key: `tick-${level}-${keyBase}`,
    angle,
    path: pathMap[level],
    level: `tick-${level}`,
  });
}



// pick the most suitable step size for the scale range
function selectStep (scaleRange: number, minLabels: number, maxLabels: number): Step {
  const steps: Step[] = [
    { stepSize: 90, unit: '°', format: formatDegrees, label: 'lg' },
    { stepSize: 30, unit: '°', format: formatDegrees, label: 'lg' },
    { stepSize: 15, unit: '°', format: formatDegrees, label: 'lg' },
    { stepSize: 10, unit: '°', format: formatDegrees, label: 'lg' },
    { stepSize: 5, unit: '°', format: formatDegrees, label: 'lg' },
    { stepSize: 2, unit: '°', format: formatDegrees, label: 'lg' },
    { stepSize: 1, unit: '°', format: formatDegrees, label: 'lg' },
    { stepSize: 30 / 60, unit: `'`, format: formatArcMinutes, label: 'md' },
    { stepSize: 20 / 60, unit: `'`, format: formatArcMinutes, label: 'md' },
    { stepSize: 15 / 60, unit: `'`, format: formatArcMinutes, label: 'md' },
    { stepSize: 10 / 60, unit: `'`, format: formatArcMinutes, label: 'md' },
    { stepSize: 5 / 60, unit: `'`, format: formatArcMinutes, label: 'md' },
    { stepSize: 2 / 60, unit: `'`, format: formatArcMinutes, label: 'md' },
    { stepSize: 1 / 60, unit: `'`, format: formatArcMinutes, label: 'md' },
    { stepSize: 30 / 3600, unit: `"`, format: formatArcSeconds, label: 'sm' },
    { stepSize: 20 / 3600, unit: `"`, format: formatArcSeconds, label: 'sm' },
    { stepSize: 15 / 3600, unit: `"`, format: formatArcSeconds, label: 'sm' },
    { stepSize: 10 / 3600, unit: `"`, format: formatArcSeconds, label: 'sm' },
    { stepSize: 5 / 3600, unit: `"`, format: formatArcSeconds, label: 'sm' },
    { stepSize: 2 / 3600, unit: `"`, format: formatArcSeconds, label: 'sm' },
  ];

  // Filter steps by zoom eligibility
  const eligible = steps.filter(s => {
    if (s.label === 'sm' && scaleRange >= 8 / 60) return false;
    if (s.label === 'md' && scaleRange >= 8) return false;
    // if (s.label === 'lg' && scaleRange < 1) return false;
    return true;
  });

  // Prefer steps within label count bounds
  const preferred = eligible.find(s => {
    const count = Math.floor(scaleRange / s.stepSize);
    return count >= minLabels && count <= maxLabels;
  });

  // Fallback: pick coarsest eligible step that gives ≥ 1 label
  const fallback = eligible.find(s => Math.floor(scaleRange / s.stepSize) >= 1);

  return preferred ?? fallback ?? steps.find(s => s.label === 'lg')!;
}


// Generates an array of tick mark and label data for the given scale range and label count constraints.
function generateTicks(scaleStart: number, scaleRange: number, 
                      minLabels:number = 6, maxLabels:number = 30): { stepSize: number, ticks: MarkDatum[] }
{

  // array of tick marks selected, then select best step size
  const ticks: MarkDatum[] = [];
  const { stepSize, format, label } = selectStep(scaleRange, minLabels, maxLabels);

  const start = Math.ceil(scaleStart / stepSize) * stepSize;
  const end = scaleStart + scaleRange;
  const count = Math.floor((end - start) / stepSize);
  for (let i = 0; i <= count && i < maxLabels; i++) {
    const v = +(start + i * stepSize).toFixed(6);
    pushTick(ticks, label as 'lg' | 'md' | 'sm', v, format);
  }

  // diagnostics
  // console.log(`scaleStart: ${scaleStart}; scaleRange: ${scaleRange};  stepSize ${stepSize}; labels: [`,ticks.map(t=>t.key),`]`, )

  return { stepSize, ticks };
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
  zorder?: 'high' | 'low' | ''  // optional zorder requirement for mark
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
        .each(function (d) { zOrder<MarkDatum>(this, d) })
        .each(function (d) { addPathOrText(this, d) })
        .attr('opacity', 0)
        .transition(t)
        .attr('opacity', 1)
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const flip = (d.label) ? (Math.cos(angle * Math.PI / 180) < 0) : false;
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

function strokeDashArray(radius:number, newScale:ScaleLinear<number, number>, stepSize:number|undefined, stepDiv:number|undefined, ) {
  if (stepSize && stepDiv) {
    const s0 = newScale(0 + stepSize) - newScale(0); 
    const dashLength = radius * (s0 / stepDiv) * (Math.PI / 180);
    return `${dashLength*0.1} ${dashLength*0.9}`
  } else {
    return 'none'
  }
}

function zOrder<T extends { zorder?: string }>(el: SVGElement, d: T): void {
  const sel = select(el);
  if      (d.zorder === 'high') sel.raise();
  else if (d.zorder === 'low')  sel.lower();
}

function addPathOrText(el: SVGElement, d: MarkDatum): void {
  const sel = select(el);
  if      (d.path)  sel.attr('d', d.path)
  else if (d.label) sel.text(d.label).attr('text-anchor', 'middle').attr('dominant-baseline', 'middle');
}


interface ArcDatum {
  key?: string;       // element key used by D3 to match existing elements
  beginAngle: number; // where the arc starts in domain angle degrees 
  endAngle: number;   // where the arc ends in domain angle degrees 
  offset?: number;    // radial offset from the radius 1=no offset, 0.9=inside, 1.1=outside
  stepSize?: number;  // size between tick labels 
  stepDiv?: number;   // number of dashes between each step
  level?: string;     // optional class name added to element
  zorder?: 'high' | 'low' | '';    // optional z-order for arc
}

function joinArcs(
  group: Selection<SVGGElement, unknown, null, undefined>,
  arcs: ArcDatum[],
  oldScale: ScaleLinear<number, number>,
  newScale: ScaleLinear<number, number>,
  radius: number,
  tRaw: Transition<BaseType, ArcDatum, SVGGElement, unknown>,
  cname: string = 'arc'   // must be unique per joinArcs call
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tRaw as Transition<BaseType, any, any, any>;
  const [min, max] = newScale.domain() as [number, number];
  const visibleArcs = arcs.filter(m => isAngleBetween(m.beginAngle, min, max) || isAngleBetween(m.endAngle, min, max)) ;
  const interp = angleInterp(oldScale, newScale);

  group.selectAll<SVGPathElement, ArcDatum>(`.${cname}`)
    .data(visibleArcs, d => `${d.key}`)
    .join(
      enter => enter.append('path')
        .attr('class', d => `${cname} ${d.level}`.trim())
        .each(function (d) { zOrder<ArcDatum>(this, d) })
        .style('stroke-dasharray', d => strokeDashArray(radius, newScale, d.stepSize, d.stepDiv))
        .attr('opacity', 0)
        .transition(t)
        .attr('opacity', 1)
        .attrTween('d', d => t => {
          const a0 = interp(d.beginAngle)(t);
          const a1 = interp(d.endAngle)(t);
          return arcPath(a0, a1, radius * (d.offset ?? 1));
        }),

      update => update.transition(t)
        .attr('opacity', 1)
        .style('stroke-dasharray', d => strokeDashArray(radius, newScale, d.stepSize, d.stepDiv))
        .attrTween('d', d => t => {
          const a0 = interp(d.beginAngle)(t);
          const a1 = interp(d.endAngle)(t);
          return arcPath(a0, a1, radius * (d.offset ?? 1));
        }),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .remove()
    );
}

function arcPath(startAngle: number, endAngle: number, radius: number): string {
  const a0 = (startAngle * Math.PI) / 180;
  const a1 = (endAngle * Math.PI) / 180;
  const x0 = radius * Math.cos(a0);
  const y0 = radius * Math.sin(a0);
  const x1 = radius * Math.cos(a1);
  const y1 = radius * Math.sin(a1);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;

  return `M${x0},${y0} A${radius},${radius} 0 ${largeArc} 1 ${x1},${y1}`;
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

// global used to remember previous scale for tweening circular scales
let prevScale: ScaleLinear<number, number> | undefined;

// Renders a circular scale with major/minor ticks and labels
function renderCircularScale() {
  if (!circularGroup.value) return;


  const dProps = domainStyle[props.domain]
  const low = props.pv - props.scaleRange / 2
  const high = props.pv + props.scaleRange / 2
  const { stepSize, ticks } = generateTicks(low,props.scaleRange)


  const cx = width * dProps.centerVw
  const cy = height * dProps.centerVh
  const radius = width / 2 - 60;
  const newScale = scaleLinear().domain([low, high]).range([dProps.sAngleLow, dProps.sAngleHigh]);
  const oldScale = prevScale ?? newScale;
  prevScale = newScale;

  const group = select(circularGroup.value).attr('transform', `translate(${cx},${cy})`);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = transition().duration(200).ease(easeCubicOut) as Transition<BaseType, any, any, any>;

  joinMarks(group, [{angle:90.2, path:'M-10,0 L60,0', zorder: 'low'}], oldScale, newScale, radius, t, 'spLine' );    // example Scale boundary line
  joinMarks(group, ticks, oldScale, newScale, radius, t, 'tickMarks' );
  joinMarks(group, [{angle:props.pv, path:'M0,0 L-20,10 L-20,-10 Z', offset: 1, zorder: 'high'}], newScale, newScale, radius, t, 'pvMark');
  joinMarks(group, [{angle:180.4, path:'M0,0 L-10,5 L-10,-5 L-10,-10 L-10,10 L2,10 L2,-10 L-10,-10 L-10,-5 Z', offset:0.85}], oldScale, newScale, radius, t, 'spMark');
  joinMarks(group, [{angle:180.1, label:'test', offset:0.5}], oldScale, newScale, radius, t, 'textMark');

  // add an arc dashed-line for the small ticks
  const stepDiv = 5
  const fractionalStep = stepSize / stepDiv
  const beginAngle = (Math.ceil(low / fractionalStep)) * fractionalStep;
  const endAngle = beginAngle + high - low;
  joinArcs(group, [{beginAngle, endAngle, stepSize, stepDiv, offset:1}], oldScale, newScale, radius, t, 'arcDashes');
  joinArcs(group, [{beginAngle:low, endAngle:high, offset:1}], oldScale, newScale, radius, t, 'arcLine');
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
	stroke-width: 1;
	stroke: lightskyblue; 
}

g .label-lg {
	fill: white; 
  font-size: 20px;
}

g .label-md {
	fill: lightblue; 
  font-size: 16px;
}

g .label-sm {
	fill: lightblue; 
  font-size: 12px;
}

g .pvMark {
	fill: lightcoral; 
}

g .spMark {
	fill: rgb(105, 219, 117); 
}

g .spLine {
	stroke: green; 
	stroke-width: 5;
 stroke-linecap: round;

}

.arcDashes {
  fill: none;
  stroke: lightskyblue;
  stroke-width: 5;
}

.arcLine {
  fill: none;
  stroke: lightskyblue;
  opacity: 0.2;
  stroke-width: 5;

}

// g {
// 	stroke: red; 
// 	stroke-width: 1;
// }

</style>
