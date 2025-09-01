<template>
  <div class="overlay-container relative-position">
    <!-- SVG Background -->
    <svg @click="onSvgClick" class="background-svg" :width="width" :height="height">
      <g v-if="isLinear" ref="linearGroup" :transform="`translate(10, ${height / 2})`" />
      <g v-else-if="isCircular" ref="circularGroup" />
    </svg>

    <!-- Foreground Content Centered -->
    <div class="foreground-content absolute-center">
      <div class="column items-center text-center">
        <div class="row items-center justify-center">
          <!-- <div class="text-h5 text-grey-6 q-mt-sm">sp</div> -->
          <q-space/>
          <div class="col-9 sp-input text-h5 text-grey-6">
            <q-input rounded filled label="Setpoint" color="positive" class="text-subtitle1" v-model=spi  type="text" mask='###°##′##.#"'>
              <template v-slot:prepend>
                <q-btn round size="lg" color="positive" dense flat icon="mdi-arrow-left-circle" class=" " />
                <!-- <q-icon name="mdi-crosshairs-gps" /> -->
              </template>
              <template v-slot:append>
                <q-btn round size="lg" color="positive" dense flat icon="mdi-arrow-right-circle" class="" />
                <!-- <q-icon name="mdi-crosshairs-gps" /> -->
              </template>
            </q-input>
            <!-- {{spx.sign}}{{ spx.degrees }}°{{ spx.minutestr }}′{{ spx.secondstr }}" -->
          </div>
          <q-space/>
        </div>
        <div class="text-h4 text-grey-6 q-mt-sm">
          Right Ascention
        </div>
        <div class="row items-center q-gutter-xs">
          <div class="text-h4">{{ pvx.sign }}</div>
          <div class="text-h2 text-weight-bold">{{ pvx.degrees }}°</div>
          <div class="column">
            <div class="text-h5 text-grey-4">{{ pvx.minutestr }}′</div>
            <div class="text-subtitle2 text-grey-5">{{ pvx.secondstr }}"</div>
          </div>
        </div>
      </div>
      <div class="row absolute-bottom-left" > 
        LeftBottom
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
	| 'semilo_360'
	| 'circular_180'
	| 'alt_90'
	| 'dec_90'
	| 'ra_hours'

const domainStyle = {
  'linear_360': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'circular_360': { centerVw: 0.5, centerVh: 0.5, sAngleLow: 170, sAngleHigh: 270, dAngleFn: wrapTo360 },
	'semihi_360': { centerVw: 0.5, centerVh: 0.7, sAngleLow: 170, sAngleHigh: 370, dAngleFn: wrapTo360 },
	'semilo_360': { centerVw: 0.5, centerVh: 0.28, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo360 },
	'circular_180': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo180 },
	'alt_90': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo90 },
	'dec_90': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo90 },
	'ra_hours': { centerVw: 0.5, centerVh: 0.9, sAngleLow: -10, sAngleHigh: 190, dAngleFn: wrapTo90 },
}

const props = defineProps<{
	scaleStart: number
	scaleRange: number
	pv: number
	sp: number
  domain: DomainStyleType
}>()

const width = 400
const height = 300
const pathMap = { lg: 'M-7,0 L16,0', md: 'M-7,0 L12,0', sm: 'M-7,0 L10,0' };
const offsetMap = { lg: 1.28, md: 1.18, sm: 1.13 }
const opacityMap = { lg: 1, md: 1, sm: 0.5 }

const throttledRenderScale = throttle(renderScale, 100)
const linearGroup = ref<SVGGElement | null>(null)
const circularGroup = ref<SVGGElement | null>(null)
const spi = ref<string>(`${props.sp}`)

// computed properties
const isLinear = computed(() => props.domain === 'linear_360')
const isCircular = computed(() => ['circular_360', 'semihi_360', 'semilo_360', 'circular_180'].includes(props.domain))
const renderKey = computed(() => `${props.domain}-${props.scaleStart}-${props.scaleRange}-${props.pv}-${props.sp}`)
const pvx = computed(() => deg2dms(props.pv, 1))
// const spx = computed(() => deg2dms(props.sp, 1))

onMounted(throttledRenderScale)
watch(renderKey, throttledRenderScale)

function onSvgClick(e:Event) {
  console.log(e)
}
// ------------------- Tick generation and Helper functions ---------------------

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
  label: string;
}

// Adds a tick and its label to the ticks array, promoting to higher label levels if appropriate and ensuring only the highest-priority tick at each angle.
function pushTick(
  ticks: MarkDatum[],
  level: 'lg' | 'md' | 'sm',
  v: number,
  dWrapFn: (v: number) => number,
  dFormatFn: (v: number) => string
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


// pick the most suitable step size for the scale range
function selectStep (scaleRange: number, minLabels: number, maxLabels: number): Step {
  const steps: Step[] = [
    { stepSize: 180, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 90, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 30, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 15, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 10, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 5, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 2, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 1, dFormatFn: formatDegrees, label: 'lg' },
    { stepSize: 30 / 60, dFormatFn: formatArcMinutes, label: 'md' },
    { stepSize: 20 / 60, dFormatFn: formatArcMinutes, label: 'md' },
    { stepSize: 15 / 60, dFormatFn: formatArcMinutes, label: 'md' },
    { stepSize: 10 / 60, dFormatFn: formatArcMinutes, label: 'md' },
    { stepSize: 5 / 60, dFormatFn: formatArcMinutes, label: 'md' },
    { stepSize: 2 / 60, dFormatFn: formatArcMinutes, label: 'md' },
    { stepSize: 1 / 60, dFormatFn: formatArcMinutes, label: 'md' },
    { stepSize: 30 / 3600, dFormatFn: formatArcSeconds, label: 'sm' },
    { stepSize: 20 / 3600, dFormatFn: formatArcSeconds, label: 'sm' },
    { stepSize: 15 / 3600, dFormatFn: formatArcSeconds, label: 'sm' },
    { stepSize: 10 / 3600, dFormatFn: formatArcSeconds, label: 'sm' },
    { stepSize: 5 / 3600, dFormatFn: formatArcSeconds, label: 'sm' },
    { stepSize: 2 / 3600, dFormatFn: formatArcSeconds, label: 'sm' },
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


// Generates an array of tick MarkDatum for the given scale range and label count constraints.
function generateTicks(scaleStart: number, scaleRange: number, dWrapFn:(v:number)=>number,
                      minLabels:number = 6, maxLabels:number = 30): { stepSize: number, ticks: MarkDatum[] }
{

  // array of tick marks selected, then select best step size
  const ticks: MarkDatum[] = [];
  const { stepSize, dFormatFn, label } = selectStep(scaleRange, minLabels, maxLabels);

  const start = Math.ceil(scaleStart / stepSize) * stepSize;
  const end = scaleStart + scaleRange;
  const count = Math.floor((end - start) / stepSize);
  for (let i = 0; i <= count && i < maxLabels; i++) {
    const v = +(start + i * stepSize).toFixed(6);
    pushTick(ticks, label as 'lg' | 'md' | 'sm', v, dWrapFn, dFormatFn);
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
          const flip = (d.label) ? (Math.cos(angle * Math.PI / 180) < 0) : false;
          return radialTransform(angle, radius, d.offset ?? 1.0, flip);
        }),

      update => update.transition(t)
        // .attr('opacity', d => d.opacity ?? 1)
        .attr('opacity', d => determineOpacity(d, min, max))
        .each(function (d) { zOrder<MarkDatum>(this, d) })
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const flip = (d.label) ? (Math.cos(angle * Math.PI / 180) < 0) : false;
          return radialTransform(angle, radius, d.offset ?? 1, flip);
        }),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .attrTween('transform', d => t => {
          const angle = interp(d.angle)(t);
          const flip = (d.label) ? (Math.cos(angle * Math.PI / 180) < 0) : false;
          return radialTransform(angle, radius, d.offset ?? 1, flip);
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
  const { stepSize, ticks } = generateTicks(low, props.scaleRange, dProps.dAngleFn)
  const arcs = generateArcs(low, high, stepSize, 5)


  const cx = width * dProps.centerVw
  const cy = height * dProps.centerVh
  const radius = width / 2 - 60;
  const newScale = scaleLinear().domain([low, high]).range([dProps.sAngleLow, dProps.sAngleHigh]);
  const oldScale = prevScale ?? newScale;
  prevScale = newScale;

  const group = select(circularGroup.value).attr('transform', `translate(${cx},${cy})`);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = transition().duration(200).ease(easeCubicOut) as Transition<BaseType, any, any, any>;




  // add an arc dashed-line for the small ticks
  // const stepDiv = 5
  // const fractionalStep = stepSize / stepDiv
  // const beginAngle = (Math.ceil(low / fractionalStep)) * fractionalStep;
  // const endAngle = beginAngle + high - low;
  // joinArcs('arcDashes', group, [{beginAngle, endAngle, stepSize, stepDiv, offset:1, zorder: 'low'}], oldScale, newScale, radius, t);
  // joinArcs('arcLine', group, [{beginAngle:low, endAngle:high, offset:1, zorder: 'low'}], oldScale, newScale, radius, t);
    joinArcs('tkArcPVtoSP', group, [{ beginAngle:props.pv, endAngle:props.sp, offset:1, opacity: 0.9, zorder: 'low' }], oldScale, newScale, radius, t);
    joinArcs('tkArc', group, arcs, oldScale, newScale, radius, t);

  // ticks and labels
  joinMarks('tkMarks', group, ticks, oldScale, newScale, radius, t);

  // pv and sp marks and tests
  joinMarks('pvMark', group, [{angle:props.pv, path:'M-6,0 L-30,15 L-30,-15 Z', offset: 1, zorder: 'high'}], newScale, newScale, radius, t);
  joinMarks('spLine', group, [{angle:props.sp, path:'M-10,0 L60,0', zorder: 'low'}], oldScale, newScale, radius, t);    // example SP line
  // joinMarks('spMark', group, [{angle:180.4, path:'M0,0 L-10,5 L-10,-5 L-10,-10 L-10,10 L2,10 L2,-10 L-10,-10 L-10,-5 Z', offset:0.85}], oldScale, newScale, radius, t);
  // joinMarks('textMark', group, [{angle:180.1, label:'test', offset:0.5}], oldScale, newScale, radius, t);
  joinArcs('tkArcHighWarning', group, [{ beginAngle:92, endAngle:120, offset:1, opacity: 0.7, zorder: 'low' }], oldScale, newScale, radius, t);


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
    stroke-width: 12;
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
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
}


.background-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}


.foreground-content {
  position: relative;
  z-index: 1;
  text-align: center;
   pointer-events: none;

  width: 400px;
  height: 320px;
}

.foreground-content .q-field {
  pointer-events: auto;
}
.foreground-content .q-btn {
  pointer-events: auto;
}
.foreground-content .q-btn-group {
  pointer-events: auto;
}
</style>
