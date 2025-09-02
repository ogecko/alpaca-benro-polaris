<template>
  <div class="overlay-container relative-position">

    <!-- Outer Boundary Content -->
    <div class="outer-content" :style="`width:${dProps.width}px; height: ${dProps.height}px`">
      <div class="row absolute-top-left q-pl-lg" > 
        <q-btn round color="secondary" dense flat icon="mdi-format-horizontal-align-center" />
      </div>
      <q-btn-group rounded  class="row absolute-top-right q-pr-lg" > 
        <div class="column">
          <q-btn @click="onScaleZoomInClick" dense flat color="secondary" icon="mdi-magnify-plus-outline" />
        </div>
        <div class="column" text-primary>
          <q-btn @click="onScaleAutoClick" dense flat color="secondary">{{ formatScaleRange() }}</q-btn>
          <q-btn @click="onScaleZoomOutClick" dense flat color="secondary" icon="mdi-magnify-minus-outline" />
        </div>
      </q-btn-group>
      <div class="row absolute-bottom-left q-pa-sm" > 
      </div>
      <div class="row absolute-bottom-right q-pa-sm" > 
      </div>
    </div>

    <!-- SVG Background -->
    <svg class="background-svg" @click="onSvgClick" ref="svgElement" :width="dProps.width" :height="dProps.height">
      <g v-if="isLinear" ref="linearGroup" />
      <g v-else-if="isCircular" ref="circularGroup" />
    </svg>

    <!-- Center Content -->
    <div class="center-content" :style="`left:${100*dProps.cx/dProps.width}%; top: ${100*dProps.cy/dProps.height}%`" >
      <div class="column items-center ">
        <div :class=" {'order-last': dProps.cy>dProps.height/2} " >
          <div class="row absolute text-positive text-caption ">
            Setpoint
          </div>
          <div class="row text-positive text-h6 items-center q-pt-md q-gutter-xs  no-wrap text-weight-light">
            <!-- <q-btn round size="md" color="positive" dense flat icon="mdi-arrow-left-circle" class=" " /> -->
            {{ spx.sign }}{{ spx.degrees }}°{{ spx.minutestr }}′{{ spx.secondstr }}"
            <!-- <q-btn round size="md" color="positive" dense flat icon="mdi-arrow-right-circle" class="" /> -->
          </div>
        </div>
        <div class="text-h4 text-grey-6 text-center">
          {{props.label}}
        </div>
        <div class="row items-center q-gutter-xs no-wrap">
          <div class="text-h4">{{ pvx.sign }}</div>
          <div class="text-h2 text-weight-bold">{{ pvx.degrees }}°</div>
          <div class="column">
            <div class="text-h5 text-grey-4">{{ pvx.minutestr }}′</div>
            <div class="text-subtitle2 text-grey-5">{{ pvx.secondstr }}"</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>


<script lang="ts" setup>
import { ref, onMounted, watch, computed } from 'vue'
import { throttle } from 'quasar'
import { scaleLinear } from 'd3-scale'
import { axisBottom } from 'd3-axis'
import { select } from 'd3-selection'
import { transition } from 'd3-transition'
import { interpolate } from 'd3-interpolate'
import { easeCubicOut } from 'd3-ease'
import { deg2dms, isAngleBetween, wrapTo360, wrapTo180, wrapTo90 } from 'src/utils/angles'
import type { ScaleLinear } from 'd3-scale'
import type { Selection } from 'd3-selection';
import type { Transition } from 'd3-transition';
import type { BaseType } from 'd3-selection';

export type DomainStyleType =
	| 'linear_360'
	| 'circular_360'
	| 'semihi_360'
	| 'semihi_180'
	| 'semilo_360'
	| 'semilo_180'
	| 'circular_180'
	| 'alt_90'
	| 'dec_90'
	| 'ra_hours'

const domainStyle = {
  'linear_360':   { width:400, height: 400, cx: 200, cy: 200, radius: 150, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'circular_360': { width:400, height: 400, cx: 200, cy: 200, radius: 150, sAngleLow: 10, sAngleHigh: 340, dAngleFn: wrapTo360 },
	'semihi_360':   { width:400, height: 270, cx: 200, cy: 190, radius: 150, sAngleLow: 170, sAngleHigh: 370, dAngleFn: wrapTo360 },
	'semihi_180':   { width:400, height: 270, cx: 200, cy: 190, radius: 150, sAngleLow: 170, sAngleHigh: 370, dAngleFn: wrapTo180 },
	'semilo_360':   { width:400, height: 270, cx: 200, cy: 80,  radius: 150, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'semilo_180':   { width:400, height: 270, cx: 200, cy: 80,  radius: 150, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo180 },
	'circular_180': { width:400, height: 400, cx: 200, cy: 200, radius: 150, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo180 },
	'alt_90':       { width:400, height: 400, cx: 200, cy: 200, radius: 150, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo90 },
	'dec_90':       { width:400, height: 400, cx: 200, cy: 200, radius: 150, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo90 },
	'ra_hours':     { width:400, height: 400, cx: 200, cy: 200, radius: 150, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo90 },
}

const steps: Step[] = [
  { stepSize: 180, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 90, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 30, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 15, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 10, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 5, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 2, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 1, dFormatFn: formatDegrees, level: 'lg' },
  { stepSize: 30 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 20 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 15 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 10 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 5 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 2 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 1 / 60, dFormatFn: formatArcMinutes, level: 'md' },
  { stepSize: 30 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 20 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 15 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 10 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 5 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
  { stepSize: 2 / 3600, dFormatFn: formatArcSeconds, level: 'sm' },
];


const props = defineProps<{
	scaleRange: number
	pv: number
	sp: number
  label: string
  domain: DomainStyleType
}>()

const pathMap = { lg: 'M-8,0 L18,0', md: 'M-8,0 L14,0', sm: 'M-8,0 L11,0' };
const offsetMap = { lg: 1.20, md: 1.165, sm: 1.13 }
const opacityMap = { lg: 1, md: 1, sm: 0.5 }

const throttledRenderScale = throttle(renderScale, 20)
const linearGroup = ref<SVGGElement | null>(null)
const circularGroup = ref<SVGGElement | null>(null)
const svgElement = ref<SVGSVGElement | null>(null);
const _scaleRange = ref<number>(props.scaleRange)

// computed properties
const isLinear = computed(() => props.domain === 'linear_360')
const isCircular = computed(() => ['circular_360', 'semihi_360', 'semilo_360', 'circular_180'].includes(props.domain))
const renderKey = computed(() => `${props.domain}-${_scaleRange.value}-${props.pv}-${props.sp}`)
const pvx = computed(() => deg2dms(props.pv, 1))
const spx = computed(() => deg2dms(props.sp, 1))
const dProps = computed(() => domainStyle[props.domain])

const emit = defineEmits<{
  (e: 'clickScale', payload: { angle: number }): void;
}>();

onMounted(throttledRenderScale)
watch(renderKey, throttledRenderScale)


// ------------------- Event handlers ---------------------

function onSvgClick(e: MouseEvent) {
  const svg = svgElement.value;
  if (!svg) return;

  // determine the svg co-ordinates
  const pt = svg.createSVGPoint();
  pt.x = e.clientX; pt.y = e.clientY;
  const svgCoords = pt.matrixTransform(svg.getScreenCTM()?.inverse());

  // determine screen angle from cx,cy, and reject clicks outside scale angle
  const screen_angleRad = Math.atan2(svgCoords.y - dProps.value.cy, svgCoords.x - dProps.value.cx)
  const screen_angleDeg = wrapTo360(screen_angleRad * (180 / Math.PI))
  if (screen_angleDeg<dProps.value.sAngleLow || screen_angleDeg>dProps.value.sAngleHigh) return

  // calculate inverse scaleLinear and wrap the domain angle value
  const low = props.pv - _scaleRange.value / 2
  const high = props.pv + _scaleRange.value / 2
  const inverseScale = scaleLinear().domain([dProps.value.sAngleLow, dProps.value.sAngleHigh]).range([low, high]);
  const domainValue = dProps.value.dAngleFn(inverseScale(screen_angleDeg));

  emit('clickScale', { angle: domainValue });
}


function onScaleZoomInClick() {
  const closest = getClosestSteps(_scaleRange.value)
  if (closest.nextDown && closest.nextDown >= 2/60) _scaleRange.value = closest.nextDown
}

function onScaleZoomOutClick() {
  const closest = getClosestSteps(_scaleRange.value)
  if (closest.nextUp) _scaleRange.value = closest.nextUp
}

function onScaleAutoClick() {
  _scaleRange.value = 200
}

// ------------------- Tick generation and Helper functions ---------------------


function formatScaleRange(): string {
  if (_scaleRange.value >= 1) return formatDegrees(_scaleRange.value)
  if (_scaleRange.value >= 1/60) return formatArcMinutes(_scaleRange.value)
  return formatArcSeconds(_scaleRange.value)
}

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
  dFormatFn: (v: number) => string;
  level: string;
}

// Adds a tick and its label to the ticks array, promoting to higher label levels if appropriate and ensuring only the highest-priority tick at each angle.
function pushTick(
  ticks: MarkDatum[],
  level: 'lg' | 'md' | 'sm',
  v: number,
  dWrapFn: (v: number) => number,
  dFormatFn: (v: number) => string,
  stepSize: number,
) {
  const keyBase = v.toFixed(6);
  const angle = v;  // dont wrap the angle so comparisons still work
  let labelText = dFormatFn(dWrapFn(v));

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
  // Demote if we have too many degree labels
  if (stepSize==1 && v%5!=0) level='sm'
  if (stepSize==2 && v%10!=0) level='sm'
  if (stepSize==5 && v%30!=0) level='sm'
  if (stepSize==10 && v%30!=0) level='sm'
  if (stepSize==15 && v%90!=0) level='sm'
  if (stepSize==30 && v%90!=0) level='sm'

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
  ticks.push({
    key: `tkLabel-${level}-${keyBase}`,
    angle,
    label: labelText,
    level: `tkLabel tk-${level}`,
    opacity: opacityMap[level],
    offset: offsetMap[level],
  });

  ticks.push({
    key: `tkDash-${level}-${keyBase}`,
    angle,
    path: pathMap[level],
    level: `tkDash tk-${level}`,
  });
}



function getClosestSteps(current: number): {
  nextUp?: number;
  nextDown?: number;
} {
  const step_numbers = steps.map(s => s.stepSize)
  let nextUp: number | undefined;
  let nextDown: number | undefined;

  for (const step of step_numbers) {
    if (step > current && (!nextUp || step - current < nextUp - current)) {
      nextUp = step;
    } else if (step < current && (!nextDown || current - step < current - nextDown)) {
      nextDown = step;
    }
  }

  const result: { nextUp?: number; nextDown?: number } = {};
  if (nextUp !== undefined) result.nextUp = nextUp;
  if (nextDown !== undefined) result.nextDown = nextDown;

  return result;
}






// pick the most suitable step size for the scale range
function selectStep (scaleRange: number, minLabels: number, maxLabels: number): Step {

  // Filter steps by zoom eligibility
  const eligible = steps.filter(s => {
    if (s.level === 'sm' && scaleRange >= 8 / 60) return false;
    if (s.level === 'md' && scaleRange >= 8) return false;
    // if (s.level === 'lg' && scaleRange < 1) return false;
    return true;
  });

  // Prefer steps within label count bounds
  const preferred = eligible.find(s => {
    const count = Math.floor(scaleRange / s.stepSize);
    return count >= minLabels && count <= maxLabels;
  });

  // Fallback: pick coarsest eligible step that gives ≥ 1 label
  const fallback = eligible.find(s => Math.floor(scaleRange / s.stepSize) >= 1);

  return preferred ?? fallback ?? steps.find(s => s.level === 'lg')!;
}


// Generates an array of tick MarkDatum for the given scale range and label count constraints.
function generateTicks(scaleStart: number, scaleRange: number, dWrapFn:(v:number)=>number,
                      minLabels:number = 6, maxLabels:number = 30): { stepSize: number, ticks: MarkDatum[] }
{

  // array of tick marks selected, then select best step size
  const ticks: MarkDatum[] = [];
  const { stepSize, dFormatFn, level } = selectStep(scaleRange, minLabels, maxLabels);

  const start = Math.ceil(scaleStart / stepSize) * stepSize;
  const end = scaleStart + scaleRange;
  const count = Math.floor((end - start) / stepSize);
  for (let i = 0; i <= count && i < maxLabels; i++) {
    const v = +(start + i * stepSize).toFixed(6);
    pushTick(ticks, level as 'lg' | 'md' | 'sm', v, dWrapFn, dFormatFn, stepSize);
  }

  // diagnostics
  // console.log(`scaleStart: ${scaleStart}; scaleRange: ${scaleRange};  stepSize ${stepSize}; labels: [`,ticks.map(t=>t.key),`]`, )

  return { stepSize, ticks };
}



// Generates an array of ArcDatum for the given scale range, label stepSize, and number of divisions between.
function generateArcs(low: number, high: number, stepSize: number, stepDiv: number): ArcDatum[] {
  const fractionalStep = stepSize / stepDiv
  const beginAngle = (Math.ceil(low / fractionalStep)) * fractionalStep;
  const endAngle = beginAngle + high - low;
  return [
    { key: `tkArcS-${stepSize}-${stepDiv}`, level:'tk-solid', beginAngle:low, endAngle:high, offset:1, opacity: 0.2, zorder: 'low' },
    { key: `tkArcD-${stepSize}-${stepDiv}`, level:'tk-dashed', beginAngle, endAngle, stepSize, stepDiv, offset:1, zorder: 'low' },
  ]
}


// ------------------- D3 Helper functions ---------------------

// Computes an interpolator between old and new scale values for smooth transitions
function angleInterp(oldScale: ScaleLinear<number, number>, newScale: ScaleLinear<number, number>) {
  return (d: number) => interpolate(oldScale(d), newScale(d));
}


// computes the x,y translate based on angle, and spins the mark around its 0,0 point
function radialTransform(angle: number, radius: number, radialOffset: number = 1.0, spin: number): string {
  const x = radius * Math.cos(angle * Math.PI / 180) * radialOffset;
  const y = radius * Math.sin(angle * Math.PI / 180) * radialOffset;
  return `translate(${x}, ${y}) rotate(${spin+angle})`;
}

// computes the dash length for achieve stepDiv marks between each stepSize
function strokeDashArray(radius:number, newScale:ScaleLinear<number, number>, stepSize:number|undefined, stepDiv:number|undefined, ) {
  if (stepSize && stepDiv) {
    const s0 = newScale(0 + stepSize) - newScale(0); 
    const dashLength = radius * (s0 / stepDiv) * (Math.PI / 180);
    return `${dashLength*0.1} ${dashLength*0.9}`
  } else {
    return 'none'
  }
}

function determineOpacity<T extends { angle: number, opacity?: number }>(d: T, min:number, max:number): number {
  return (d.angle>=min && d.angle<=max)? d.opacity ?? 1 : 0
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

// ------------------- D3 Join Functions ---------------------

type MarkDatum = {
  key?: string;       // element key used by D3 to match existing elements
  angle: number;      // domain angle in degrees
  offset?: number;    // radial offset from the radius 1=no offset, 0.9=inside, 1.1=outside
  opacity?: number;   // opacity of the mark
  label?: string;     // text string to render at radial position
  path?: string;      // SVG path string to render at radial position
  level?: string;     // optional class name added to element
  zorder?: 'high' | 'low' | ''  // optional zorder requirement for mark
};

// ****** D3 ****** Keyed data joins/animation for Marks of text and path elements, positioned radially
function joinMarks(
  cname: string = 'mark',    // identifies elements for this call of joinMarks
  group: Selection<SVGGElement, unknown, null, undefined>,
  marks: MarkDatum[],
  oldScale: ScaleLinear<number, number>,
  newScale: ScaleLinear<number, number>,
  radius: number,
  tRaw: Transition<BaseType, MarkDatum, SVGGElement, unknown>,
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tRaw as Transition<BaseType, any, any, any>;
  const [min, max] = newScale.domain() as [number, number];
  const [smin, smax] = newScale.range() as [number, number];
  const smid = (smin+smax)/2
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
        .attr('opacity', d => determineOpacity(d, min, max))
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const spin = (!d.label) ? 0 : (Math.sin(smid * Math.PI / 180) > 0) ? -90 : +90;
          return radialTransform(angle, radius, d.offset ?? 1.0, spin);
        }),

      update => update.transition(t)
        // .attr('opacity', d => d.opacity ?? 1)
        .attr('opacity', d => determineOpacity(d, min, max))
        .each(function (d) { zOrder<MarkDatum>(this, d) })
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const spin = (!d.label) ? 0 : (Math.sin(smid * Math.PI / 180) > 0) ? -90 : +90;
          return radialTransform(angle, radius, d.offset ?? 1.0, spin);
        }),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const spin = (!d.label) ? 0 : (Math.sin(angle * Math.PI / 180) > 0) ? -90 : +90;
          return radialTransform(angle, radius, d.offset ?? 1.0, spin);
        })
        .remove()
    );
}




interface ArcDatum {
  key?: string;       // element key used by D3 to match existing elements
  beginAngle: number; // where the arc starts in domain angle degrees 
  endAngle: number;   // where the arc ends in domain angle degrees 
  offset?: number;    // radial offset from the radius 1=no offset, 0.9=inside, 1.1=outside
  opacity?: number;   // opacity of the arc
  stepSize?: number;  // size between tick labels 
  stepDiv?: number;   // number of dashes between each step
  level?: string;     // optional class name added to element
  zorder?: 'high' | 'low' | '';    // optional z-order for arc
}

// ****** D3 ****** Keyed data joins/animation for ARCs of path elements, dashed or solid, positioned radially
function joinArcs(
  cname: string = 'arc',   // must be unique per joinArcs call
  group: Selection<SVGGElement, unknown, null, undefined>,
  arcs: ArcDatum[],
  oldScale: ScaleLinear<number, number>,
  newScale: ScaleLinear<number, number>,
  radius: number,
  tRaw: Transition<BaseType, ArcDatum, SVGGElement, unknown>,
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = tRaw as Transition<BaseType, any, any, any>;
  const [min, max] = newScale.domain() as [number, number];
  const visibleArcs = arcs.filter(m => {
    const x = m.beginAngle
    const y = m.endAngle
    if (x > y) { m.beginAngle=y; m.endAngle=x; }               // swap them
    if ((m.beginAngle>max) || (m.endAngle<min)) return false   // not within range
    if ((m.beginAngle>=min) && (m.endAngle<=max)) return true  // within range
    if (m.beginAngle<min) m.beginAngle=min                     // clip to min
    if (m.endAngle>max) m.endAngle=max                         // clip to max
    return true
  }) ;
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
        .attr('opacity', d => d.opacity ?? 1)
        .attrTween('d', d => t => {
          const a0 = interp(d.beginAngle)(t);
          const a1 = interp(d.endAngle)(t);
          return arcPath(a0, a1, radius * (d.offset ?? 1));
        }),

      update => update.transition(t)
        .each(function (d) { zOrder<ArcDatum>(this, d) })
        .attr('opacity', d => d.opacity ?? 1)
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


// ------------------- Rendering ---------------------

// Renders a linear scale with animated axis ticks
function renderLinearScale() {
	if (!linearGroup.value) return

	const scale = scaleLinear()
		.domain([props.pv - _scaleRange.value / 2, props.pv + _scaleRange.value / 2])
		.range([0, dProps.value.width - 40])

	const axis = axisBottom(scale).ticks(10)
	const group = select(linearGroup.value)

	group.transition().duration(200).ease(easeCubicOut).call(axis)
}

// global used to remember previous scale for tweening circular scales
let prevScale: ScaleLinear<number, number> | undefined;

// Renders a circular scale with major/minor ticks and labels
function renderCircularScale() {
  if (!circularGroup.value) return;


  const low = props.pv - _scaleRange.value / 2
  const high = props.pv + _scaleRange.value / 2
  const { stepSize, ticks } = generateTicks(low, _scaleRange.value, dProps.value.dAngleFn)
  const arcs = generateArcs(low, high, stepSize, 5)


  const radius = dProps.value.radius;
  const newScale = scaleLinear().domain([low, high]).range([dProps.value.sAngleLow, dProps.value.sAngleHigh]);
  const oldScale = prevScale ?? newScale;
  prevScale = newScale;

  const group = select(circularGroup.value).attr('transform', `translate(${dProps.value.cx},${dProps.value.cy})`);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = transition().duration(200).ease(easeCubicOut) as Transition<BaseType, any, any, any>;



  // arcs, arc ticks, and annotations for SP and HighWarning
  joinArcs('tkArc', group, arcs, oldScale, newScale, radius, t);
  joinArcs('tkArcPVtoSP', group, [{ beginAngle:props.pv, endAngle:props.sp, offset:1, opacity: 0.9, zorder: 'low' }], oldScale, newScale, radius, t);
  joinArcs('tkArcHighWarning', group, [{ beginAngle:92, endAngle:120, offset:1, opacity: 0.7, zorder: 'low' }], oldScale, newScale, radius, t);

  // scale ticks and labels
  joinMarks('tkMarks', group, ticks, oldScale, newScale, radius, t);

  // pv and sp marks and tests
  joinMarks('spLine', group, [{angle:props.sp, path:'M-35,0  L8,0 L12,-5, L12,5 L8,0', zorder: 'high'}], oldScale, newScale, radius, t); 
  joinMarks('pvMark', group, [{angle:props.pv, path:'M-8,0 L-30,15 L-30,-15 Z', offset: 1, zorder: 'high'}], newScale, newScale, radius, t);

  // joinMarks('spMark', group, [{angle:180.4, path:'M0,0 L-10,5 L-10,-5 L-10,-10 L-10,10 L2,10 L2,-10 L-10,-10 L-10,-5 Z', offset:0.85}], oldScale, newScale, radius, t);
  // joinMarks('textMark', group, [{angle:180.1, label:'test', offset:0.5}], oldScale, newScale, radius, t);
  // joinArcs('arcDashes', group, [{beginAngle, endAngle, stepSize, stepDiv, offset:1, zorder: 'low'}], oldScale, newScale, radius, t);
  // joinArcs('arcLine', group, [{beginAngle:low, endAngle:high, offset:1, zorder: 'low'}], oldScale, newScale, radius, t);


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
<style lang="scss" scoped>
.tkMagnifyBtn .text-primary {
  color: lightskyblue;
}

:deep(g) {
  .tkDash {
    stroke: lightskyblue;
    &.tk-lg { stroke-width: 5; }
    &.tk-md { stroke-width: 3; }
    &.tk-sm { stroke-width: 2; }
  }

  .tkLabel {
    fill: lightskyblue;
    &.tk-lg { font-size: 16px; }
    &.tk-md { font-size: 14px; }
    &.tk-sm { font-size: 12px; }
  }

  .tkArc {
    fill: none;
    stroke-width: 16;
    &.tk-dashed { stroke: lightskyblue; }
    &.tk-solid { stroke: lightskyblue; }
  }

  .tkArcHighWarning {
    fill: none;
    stroke-width: 12;
    stroke: var(--q-warning); 
  }

  .tkArcPVtoSP {
    fill: none;
    stroke-width: 12;
    stroke: var(--q-positive); 
  }

  .pvMark { fill: lightcoral; }
  .spMark { fill: var(--q-positive); }

  .spLine {
    stroke: var(--q-positive);
    stroke-width: 5;
    stroke-linecap: round;
  }



}


.overlay-container {
  position: relative;
  width: 100%;
  height: 100%;
    pointer-events: auto;

}

.background-svg {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 0;
}

.outer-content {
  position: relative;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 1;
}

.center-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  pointer-events: auto;
}

.overlay-container .q-field {
  pointer-events: auto;
}
.overlay-container .q-btn {
  pointer-events: auto;
}
.overlay-container .q-btn-group {
  pointer-events: auto;
}
</style>
