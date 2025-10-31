<template>
  <div class="overlay-container relative-position" >

    <div class="interaction-area"
      :style="`width:${dProps.width}px; height: ${dProps.height}px`"
      @mouseenter="showButtons = true"
      @mouseleave="showButtons = false"
      @pointerdown="showButtons = true"
    >
    <!-- Outer Boundary Content for buttons -->
    <div class="outer-content" :style="`width:${dProps.width}px; height: ${dProps.height}px`">
      <transition appear enter-active-class="animated fadeIn" leave-active-class="animated fadeOut">
        <div v-if="showButtons">
          <div class="row absolute-top-left q-pl-xl q-pb-sm" > 
          </div>
          <q-btn-group rounded  class="row absolute-top-right q-pr-lg" > 
            <div class="column">
              <q-btn @click="onScaleZoomInClick" dense flat color="secondary" icon="mdi-magnify-plus-outline"></q-btn>
            </div>
            <div class="column" text-primary>
              <q-btn @click="onScaleAutoClick" dense flat color="secondary">{{ formatAngle(scaleRange, unit) }}</q-btn>
              <q-btn @click="onScaleZoomOutClick" dense flat color="secondary" icon="mdi-magnify-minus-outline"></q-btn>
            </div>
          </q-btn-group>
          <div class="row absolute-bottom-left q-pa-sm" > 
          </div>
          <div class="row absolute-bottom-right q-pa-sm" > 
          </div>
        </div>
      </transition>
    </div>

    <!-- SVG Background -->
    <svg class="background-svg" @pointerdown="onSvgPointerDown" @wheel="onScaleWheel" ref="svgElement" :width="dProps.width" :height="dProps.height" 
    >
      <rect :width="dProps.width" :height="dProps.height" fill="none" pointer-events="all"/>
      <g v-if="isLinear" ref="linearGroup" />
      <g v-else-if="isCircular" ref="circularGroup" />
    </svg>

    <!-- Center Content -->
    <div class="center-content no-edit-cursor" :style="`left:${100*dProps.cx/dProps.width}%; top: ${100*dProps.cy/dProps.height}%`" >
      <div class="column items-center ">
        <div :class="{'row': true, 'order-last': dProps.cy>dProps.height/2} " >
          <div class="row text-positive text-h6 items-center q-gutter-xs  no-wrap text-weight-light">
            <div v-if="showButtons">
              <MoveFab v-if="props.label=='Roll'" icon="mdi-format-align-middle" >
                <q-fab-action color="positive" @click="onClickFabAngle({roll: 0})" >0°</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({roll: -70})">-70°</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({roll: +70})">+70°</q-fab-action>
              </MoveFab>
              <MoveFab v-if="props.label=='Altitude'" icon="mdi-angle-acute" >
                <q-fab-action color="positive" @click="onClickFabAngle({alt: 0})" >0°</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({alt: 30})">30°</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({alt: 45})">45°</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({alt: 60})">60°</q-fab-action>
              </MoveFab>
              <MoveFab v-if="props.label=='Azimuth'" icon="mdi-compass-rose" >
                <q-fab-action color="positive" @click="onClickFabAngle({az: 180})">S</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({az: 90})" >E</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({az: 270})">W</q-fab-action>
                <q-fab-action color="positive" @click="onClickFabAngle({az: 0})"  >N</q-fab-action>
              </MoveFab>
            </div>
            <MoveButton v-if="showButtons" activeColor="positive" icon="mdi-minus-circle" @push="onMinus"/>
            <div class="column items-left sp-readout-value">
              <div class="absolute text-positive text-caption">Setpoint</div>
              <div class="q-pt-md">{{ spxValueDisplayStr }}</div>
              <q-popup-edit v-model="spxValueEditStr" v-slot="scope" color="positive" @before-show="onPopupShowSPEdit" >
                <q-input :label="props.label+' SP'" color="positive" ref="spxInputRef" v-model="spxValueEditStr" autofocus @keyup.enter="onClickSetpoint(true, scope)">
                  <template v-slot:prepend>
                    <q-icon name="mdi-arrow-up-bold" color="positive"/>
                  </template>                  
                  <template v-slot:after>
                    <q-btn flat dense round color="negative" icon="cancel" @click="onClickSetpoint(false, scope)"/>
                    <q-btn flat dense round color="positive" icon="check_circle" @click="onClickSetpoint(true, scope)"/>
                  </template>
                </q-input>
              </q-popup-edit>
            </div>
            <MoveButton v-if="showButtons" activeColor="positive" icon="mdi-plus-circle" @push="onPlus"/>
          </div>
        </div>
        <div class="text-h4 text-grey-6 text-center text-no-wrap">
          {{props.label}}
        </div>
        <div class="row items-center q-gutter-xs no-wrap">
          <div class="text-h4">{{ pvx.sign }}</div>
          <div class="text-h2 text-weight-bold">{{ pvx.degreestr }}</div>
          <div class="column">
            <div class="text-h5 text-grey-4">{{ pvx.minutestr }}</div>
            <div class="text-subtitle2 text-grey-5">{{ pvx.secondstr }}</div>
          </div>
        </div>
      </div>
    </div>


    </div>

  </div>
</template>


<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed } from 'vue'
import { throttle } from 'quasar'
import { scaleLinear } from 'd3-scale'
import { axisBottom } from 'd3-axis'
import { select } from 'd3-selection'
import { transition } from 'd3-transition'
import { easeCubicOut } from 'd3-ease'
import { deg2dms, dms2deg, isAngleBetween, wrapTo360, wrapTo180, wrapTo24, angularDifference } from 'src/utils/angles'
import { formatAngle, formatArcMinutes, getClosestSteps, selectStep } from 'src/utils/scale'
import MoveButton from 'src/components/MoveButton.vue'
import MoveFab from 'src/components/MoveFab.vue'
import type { ScaleLinear } from 'd3-scale'
import type { Selection } from 'd3-selection';
import type { Transition } from 'd3-transition';
import type { BaseType } from 'd3-selection';
import type { LevelKey, UnitKey } from 'src/utils/angles'

// Component properties
const props = defineProps<{
	pv: number | undefined
	sp: number | undefined
	lst?: number 
  label: string
  domain: DomainStyleType
}>()

// dynamic variables/refs
const linearGroup = ref<SVGGElement | null>(null)
const circularGroup = ref<SVGGElement | null>(null)
const svgElement = ref<SVGSVGElement | null>(null);
const scaleRange = ref<number>(200)
const showButtons = ref<boolean>(false);
const spxValueEditStr = ref<string>('')
const spxInputRef = ref();

// computed properties
const isLinear = computed(() => props.domain === 'linear_360')
const renderKey = computed(() => `${props.domain}-${scaleRange.value}-${props.pv}-${props.sp}-${props.lst}`)
const pvn = computed(() => dProps.value.dAngleFn(props.pv??0))        // pv normalised
const spn = computed(() => dProps.value.dAngleFn(props.sp??0))        // sp normalised
const pvx = computed(() => deg2dms(pvn.value, 1, dProps.value.unit))   // pv decomposed
const spx = computed(() => deg2dms(spn.value, 1, dProps.value.unit))   // sp decomposed
const spxValueDisplayStr = computed(() => (spx.value ? ((spx.value.sign??'') + spx.value.degreestr + spx.value.minutestr + spx.value.secondstr) : '') )
const dProps = computed(() => domainStyle[props.domain])
const unit = computed(() => dProps.value.unit)
const isCircular = computed(() => [
  'circular_360', 'semihi_360', 'semilo_360', 'semihi_180', 'semihi_24', 'semilo_180', 'circular_180', 
  'az_360', 'alt_90', 'roll_180', 'ra_24', 'dec_180', 'pa_360',
].includes(props.domain))


// events that can be emitted
const emit = defineEmits<{
  (e: 'clickScale', payload: { label: string, angle: number, radialOffset: number }): void,
  (e: 'clickFabAngle', payload: { az?: number, alt?: number, roll?: number }): void,
  (e: 'clickMove', payload: { label: string, rateScale: number} ): void,
}>();


// ------------------- Layout Configuration Data ---------------------

export type DomainStyleType =
	| 'linear_360'
	| 'circular_360'
	| 'az_360'
	| 'alt_90'
	| 'roll_180'
	| 'ra_24'
	| 'dec_180'
	| 'pa_360'

type WarningRange = [number, number];
type DomainStyleConfig = {
  width: number;
  height: number;
  cx: number;
  cy: number;
  radius: number;
  sAngleLow: number;
  sAngleHigh: number;
  dAngleFn: (angle: number) => number;
  unit: UnitKey;
  minScale: number;
  maxScale: number;
  warnings: WarningRange[];
};


const domainStyle: Record<DomainStyleType, DomainStyleConfig> = {
  'linear_360':   { width:400, height:400, cx:200, cy:200, radius:150, sAngleLow:-10, sAngleHigh:190, dAngleFn:wrapTo360, unit:'deg', minScale:2/60, maxScale:200, warnings:[] },
  'circular_360': { width:400, height:400, cx:200, cy:200, radius:150, sAngleLow:10,  sAngleHigh:340, dAngleFn:wrapTo360, unit:'deg', minScale:2/60, maxScale:200, warnings:[] },
  'az_360':       { width:400, height:270, cx:200, cy:190, radius:150, sAngleLow:170, sAngleHigh:370, dAngleFn:wrapTo360, unit:'deg', minScale:2/60, maxScale:200, warnings:[] },
  'alt_90':       { width:400, height:270, cx:200, cy:190, radius:150, sAngleLow:170, sAngleHigh:370, dAngleFn:wrapTo180, unit:'deg', minScale:2/60, maxScale:200, warnings:[[82,200],[-100,-8]] },
  'roll_180':     { width:400, height:270, cx:200, cy:190, radius:150, sAngleLow:170, sAngleHigh:370, dAngleFn:wrapTo180, unit:'deg', minScale:2/60, maxScale:200, warnings:[[82,200],[-82,-200]] },
  'ra_24':        { width:400, height:270, cx:200, cy:190, radius:150, sAngleLow:170, sAngleHigh:370, dAngleFn:wrapTo24,  unit:'hr',  minScale:1/60, maxScale:12,  warnings:[] },
  'dec_180':      { width:400, height:270, cx:200, cy:190, radius:150, sAngleLow:170, sAngleHigh:370, dAngleFn:wrapTo180, unit:'deg', minScale:2/60, maxScale:200, warnings:[[90,200],[-90,-200]] },
  'pa_360':       { width:400, height:270, cx:200, cy:190, radius:150, sAngleLow:170, sAngleHigh:370, dAngleFn:wrapTo360, unit:'deg', minScale:2/60, maxScale:200, warnings:[] },
};


// radial dial label formatting data
const pathMap = { lg: 'M-8,0 L18,0', md: 'M-8,0 L14,0', sm: 'M-8,0 L11,0' };
const offsetMap = { lg: 1.20, md: 1.165, sm: 1.13 }
const opacityMap = { lg: 1, md: 1, sm: 0.5 }


// ------------------- Lifecycle Functions ---------------------

const throttledRenderScale = throttle(renderScale, 20)
onMounted(throttledRenderScale)

watch(renderKey, throttledRenderScale)

watch(dProps, () => {
  // clap the scaleRange to the valid range for the given domain style
  scaleRange.value = Math.max(dProps.value.minScale, Math.min(dProps.value.maxScale, scaleRange.value));
})


// ------------------- Event handlers ---------------------

function onClickFabAngle(payload: { az?: number, alt?: number, roll?: number}) {
  emit('clickFabAngle', payload)
}

// handle clicks on the labels and emit a clickScale event
function onLabelClick(e: MouseEvent, angle: number) {
  e.preventDefault()
  e.stopPropagation()
  angle = dProps.value.dAngleFn(angle) 
  emit('clickScale', { label: props.label, angle, radialOffset: 1.0 }); 
}

async function onPopupShowSPEdit() {
  // initialise the edit field
  spxValueEditStr.value = spxValueDisplayStr.value
  // select all the text
  await nextTick()
  const el = spxInputRef.value?.$el?.querySelector('input');
  if (el) el.select();
}

function onClickSetpoint(isSetEvent:boolean, scope: { cancel: () => void }) {
  scope.cancel()
  if (isSetEvent) {
    const angle = dms2deg(spxValueEditStr.value)
    emit('clickScale', { label: props.label, angle, radialOffset: 1.0 }); 
  }
}


// handle clicks on the scale and emit a clickScale event
function onSvgPointerDown(e: PointerEvent) {
  const svg = svgElement.value;
  if (!svg) return;

  const pt = svg.createSVGPoint();
  pt.x = e.clientX;
  pt.y = e.clientY;

  const svgCoords = pt.matrixTransform(svg.getScreenCTM()?.inverse());

  // determine screen angle from cx,cy, and reject clicks outside scale angle
  const screen_angleRad = Math.atan2(svgCoords.y - dProps.value.cy, svgCoords.x - dProps.value.cx)
  const screen_angleDeg = wrapTo360(screen_angleRad * (180 / Math.PI))
  if (screen_angleDeg<dProps.value.sAngleLow || screen_angleDeg>dProps.value.sAngleHigh) return

  // calculate inverse scaleLinear and wrap the domain angle value
  const low = (props.pv ?? 0) - scaleRange.value / 2
  const high = (props.pv ?? 0) + scaleRange.value / 2
  const inverseScale = scaleLinear().domain([dProps.value.sAngleLow, dProps.value.sAngleHigh]).range([low, high]);
  const angle = dProps.value.dAngleFn(inverseScale(screen_angleDeg));

  // Compute radial offset relative to scale radius
  const dx = svgCoords.x - dProps.value.cx;
  const dy = svgCoords.y - dProps.value.cy;
  const distance = Math.sqrt(dx * dx + dy * dy);
  const radialOffset = distance / dProps.value.radius;

  // check that click was within the scale radial offset
  if (radialOffset<0.8 || radialOffset>1.25) return

  // check that the buttons are visible and it wasnt an accidental scroll tap on phone
  if (!showButtons.value) return

  emit('clickScale', { label: props.label, angle, radialOffset });
}


// handle mouse wheel events while over the svg and change zoom level/scaleRange
function onScaleWheel(e: WheelEvent) {
  e.preventDefault();  

  const baseFactor = 1.2;   // tweak baseFactor for step sensitivity     
  const divisor = 50        // tweak divisor for magnitude sensitivity

  const direction = Math.sign(e.deltaY);
  const magnitude = Math.abs(e.deltaY);
  const zoomFactor = Math.pow(baseFactor, magnitude / divisor); 

  // Scroll down → dir is +1, zoom out; Scroll up → dir is -1, zoom in
  let newRange = scaleRange.value;
  newRange *= Math.pow(zoomFactor, direction);

  // clap the new range
  newRange = Math.max(dProps.value.minScale, Math.min(dProps.value.maxScale, newRange));
  scaleRange.value = newRange;
}



// handle click on ZOOM-IN button to decrease scaleRange
function onScaleZoomInClick() {
  const closest = getClosestSteps(scaleRange.value)
  if (closest.nextDown && closest.nextDown >= dProps.value.minScale) scaleRange.value = closest.nextDown
}

// handle click on ZOOM-OUT button to increase scaleRange
function onScaleZoomOutClick() {
  const closest = getClosestSteps(scaleRange.value)
  if (closest.nextUp && closest.nextUp <= dProps.value.maxScale) scaleRange.value = closest.nextUp
}

// handle click on top right AUTO button to change scaleRange to maxScale
function onScaleAutoClick() {
  scaleRange.value = dProps.value.maxScale
}

// handle click on movePlus
function onPlus(payload: { isPressed: boolean }) {
  emit('clickMove', { label: props.label, rateScale: payload.isPressed ? scaleRange.value: 0})
}

// handle click on moveMinus
function onMinus(payload: { isPressed: boolean }) {
  emit('clickMove', { label: props.label, rateScale: payload.isPressed ? -scaleRange.value: 0})
}

// ------------------- Tick generation and Helper functions ---------------------

// Adds a tick and its label to the ticks array, promoting to higher label levels if appropriate and ensuring only the highest-priority tick at each angle.
function pushTick(
  ticks: MarkDatum[],
  level: LevelKey,
  v: number,
  dWrapFn: (v: number) => number,
  dFormatFn: (v: number, unit: UnitKey) => string,
  stepSize: number,
) {
  const keyBase = v.toFixed(6);
  const angle = v;  // dont wrap the angle so comparisons still work
  let labelText = dFormatFn(dWrapFn(v), unit.value);

  // Promote md ticks that look like whole degrees
  if (['md','sm'].includes(level) && /^[+-]?\d+[°ʰ]$/.test(labelText)) {
    level = 'lg'
  } 
  // Promote sm ticks that look like whole minutes
  if ('sm' === level  && /^[+-]?\d+[′ᵐ]$/.test(labelText)) {
    level = 'md'
  } 
  // Promote sm ticks that look like 60" to whole minutes
  if ('sm' === level  && /^[+-]?60[″ˢ]$/.test(labelText)) {
    level = 'md'
    labelText = formatArcMinutes(v, unit.value)
  } 
  // Demote if we have too many degree labels
  if (stepSize==1 && v%5!=0 && dProps.value.unit=='deg') level='md'
  if (stepSize==2 && v%10!=0 && dProps.value.unit=='deg') level='md'
  if (stepSize==5 && v%30!=0) level='md'
  if (stepSize==10 && v%30!=0) level='md'
  if (stepSize==15 && v%90!=0) level='md'
  if (stepSize==30 && v%90!=0) level='md'

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
    key: `${props.label}-tkLabel-${level}-${keyBase}`,
    angle,
    label: labelText,
    level: `tkLabel tk-${level} no-edit-cursor`,
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
function generateScaleArcs(low: number, high: number, stepSize: number, stepDiv: number): ArcDatum[] {
  const fractionalStep = stepSize / stepDiv
  const beginAngle = (Math.ceil(low / fractionalStep)) * fractionalStep;
  const endAngle = beginAngle + high - low;
  return [
    { key: `tkArcS-${stepSize}-${stepDiv}`, level:'tk-solid', beginAngle:low, endAngle:high, offset:1, opacity: 0.2, zorder: 'low' },
    { key: `tkArcD-${stepSize}-${stepDiv}`, level:'tk-dashed', beginAngle, endAngle, stepSize, stepDiv, offset:1, zorder: 'low' },
  ]
}

function generateWarningArcs(low: number, high: number, stepSize: number): ArcDatum[] {
  const arcs = dProps.value.warnings.map( w => {
    return { key: `tkWrn-${w[0]}-${w[1]}-${stepSize}`, beginAngle:w[0], endAngle:w[1], offset:1, opacity: 0.7, zorder: 'low' } as ArcDatum
  })
 return arcs
}


// ------------------- D3 Helper functions ---------------------

// Computes a fn(angle, oldangle) that returns an interpolator fn(t) to tween between old and new scale values for smooth transitions, assumes angle changes too
function movingAngleInterp(oldScale: ScaleLinear<number, number>, newScale: ScaleLinear<number, number>) {
   return (angle:number|undefined, oldAngle?:number) => {
    const a0 = oldScale(oldAngle ?? angle ?? 0);
    const a1 = newScale(angle ?? 0);
    const delta = angularDifference(a0, a1)
    return (t: number) => a0 + delta * t;
  };
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

function determineOpacity<T extends { angle?: number, opacity?: number }>(d: T, min:number, max:number): number {
  if (typeof d.angle !== 'number') return 0;
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
  const largeArc = wrapTo360(endAngle - startAngle) > 180 ? 1 : 0;

  return `M${x0},${y0} A${radius},${radius} 0 ${largeArc} 1 ${x1},${y1}`;
}

// swap beginAngle and endAngle if they are in the wrong order
function normalizeArcAngles(arcs: ArcDatum[]): ArcDatum[] {
  return arcs.map(arc => {
    const { beginAngle, endAngle } = arc;
    if (
      typeof beginAngle === 'number' &&
      typeof endAngle === 'number' &&
      endAngle < beginAngle
    ) {
      return {
        ...arc,
        beginAngle: endAngle,
        endAngle: beginAngle
      };
    }
    return arc;
  })
}


// ------------------- D3 Join Functions ---------------------

type MarkDatum = {
  key?: string;       // element key used by D3 to match existing elements
  angle?: number;     // domain angle in degrees
  oldAngle?: number;  // optional old domain angle in degrees (if you want it animated from old to new)
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
  const visibleMarks = marks.filter(m => isAngleBetween(m.angle ?? 0, min, max));
  const interp = movingAngleInterp(oldScale, newScale);

  group.selectAll<SVGTextElement | SVGPathElement, MarkDatum>(`.${cname}`)
    .data(visibleMarks, d => `${d.key}`)
    .join(
      enter => enter.append(d => document.createElementNS('http://www.w3.org/2000/svg', d.path ? 'path' : 'text'))
        .attr('class', d => `${cname} ${d.level}`.trim())
        .each(function (d) { zOrder<MarkDatum>(this, d) })
        .each(function (d) { addPathOrText(this, d) })
        .attr('opacity', 0)
        .on('mousedown', function (event, d) { if (d.label) { event.preventDefault(); event.stopPropagation() }})
        .on('click', function (event, d) { if (d.label && typeof d.angle==='number') { onLabelClick(event, d.angle) } })
        .transition(t)
        .attr('opacity', d => determineOpacity(d, min, max))
        .attrTween('transform', d => t => {
          const angle = interp(d.angle, d.oldAngle)(t);
          const spin = (!d.label) ? 0 : (Math.sin(smid * Math.PI / 180) > 0) ? -90 : +90;
          return radialTransform(angle, radius, d.offset ?? 1.0, spin);
        }),

      update => update.transition(t)
        .attr('opacity', d => determineOpacity(d, min, max))
        .each(function (d) { zOrder<MarkDatum>(this, d) })
        .attrTween('transform', d => t => {
          const angle = interp(d.angle, d.oldAngle)(t);
          const spin = (!d.label) ? 0 : (Math.sin(smid * Math.PI / 180) > 0) ? -90 : +90;
          return radialTransform(angle, radius, d.offset ?? 1.0, spin);
        }),

      exit => exit.transition(t)
        .attr('opacity', 0)
        .attrTween('transform', d => t => {
          const angle = interp(d.angle, d.oldAngle)(t);
          const spin = (!d.label) ? 0 : (Math.sin(angle * Math.PI / 180) > 0) ? -90 : +90;
          return radialTransform(angle, radius, d.offset ?? 1.0, spin);
        })
        .remove()
    );
}




interface ArcDatum {
  key?: string;       // element key used by D3 to match existing elements
  beginAngle?: number; // where the arc starts in domain angle degrees 
  endAngle?: number;   // where the arc ends in domain angle degrees 
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
  const normalisedArcs = normalizeArcAngles(arcs)
  const visibleArcs = normalisedArcs.filter(m => {
    if (typeof m.beginAngle !== 'number' || typeof m.endAngle !== 'number') return false;
    if ((m.beginAngle>=min) && (m.endAngle<=max)) return true  // within range
    if ((m.beginAngle>max) || (m.endAngle<min)) return false   // not within range
    if (m.beginAngle<min) m.beginAngle=min                     // clip to min
    if (m.endAngle>max) m.endAngle=max                         // clip to max
    return true
  }) ;
  const interp = movingAngleInterp(oldScale, newScale);

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
          const a0 = interp(d.beginAngle ?? 0)(t);
          const a1 = interp(d.endAngle ?? 0)(t);
          return arcPath(a0, a1, radius * (d.offset ?? 1));
        }),

      update => update.transition(t)
        .each(function (d) { zOrder<ArcDatum>(this, d) })
        .attr('opacity', d => d.opacity ?? 1)
        .style('stroke-dasharray', d => strokeDashArray(radius, newScale, d.stepSize, d.stepDiv))
        .attrTween('d', d => t => {
          const a0 = interp(d.beginAngle ?? 0)(t);
          const a1 = interp(d.endAngle ?? 0)(t);
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
		.domain([props.pv??0 - scaleRange.value / 2, props.pv??0 + scaleRange.value / 2])
		.range([0, dProps.value.width - 40])

	const axis = axisBottom(scale).ticks(10)
	const group = select(linearGroup.value)

	group.transition().duration(200).ease(easeCubicOut).call(axis)
}

// global used to remember previous scale, PV and SP for tweening circular scales
let prevScale: ScaleLinear<number, number> | undefined;
let prevSP: number | undefined

// Renders a circular scale with major/minor ticks and labels
function renderCircularScale() {
  if (!circularGroup.value) return;


  const low = (props.pv ?? 0) - scaleRange.value / 2
  const high = (props.pv ?? 0) + scaleRange.value / 2
  const { stepSize, ticks } = generateTicks(low, scaleRange.value, dProps.value.dAngleFn)
  const scaleArcs = generateScaleArcs(low, high, stepSize, 5)
  const warningArcs = generateWarningArcs(low, high, stepSize)

  const radius = dProps.value.radius;
  const newScale = scaleLinear().domain([low, high]).range([dProps.value.sAngleLow, dProps.value.sAngleHigh]);
  const oldScale = prevScale ?? newScale;
  prevScale = newScale;
 
  const closeSP = (props.pv??0) + angularDifference(props.pv??0, props.sp??0) 
  const oldSP = prevSP ?? closeSP
  prevSP = closeSP;

  const group = select(circularGroup.value).attr('transform', `translate(${dProps.value.cx},${dProps.value.cy})`);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const t = transition().duration(200).ease(easeCubicOut) as Transition<BaseType, any, any, any>;

  // arcs, arc ticks, and annotations for SP and HighWarning
  joinArcs('scaleArcs', group, scaleArcs, oldScale, newScale, radius, t);
  joinArcs('warningArcs', group, warningArcs, oldScale, newScale, radius, t);
  joinArcs('tkArcPVtoSP', group, [{ beginAngle:props.pv, endAngle:closeSP, offset:1, opacity: 0.9, zorder: 'low' } as ArcDatum], oldScale, newScale, radius, t);

  // scale ticks and labels
  joinMarks('tkMarks', group, ticks, oldScale, newScale, radius, t);

  // pv and sp marks and tests
  joinMarks('pvMark', group, [{key: 'pvMark', angle:props.pv, path:'M-8,0 L-30,15 L-30,-15 Z', offset: 1, zorder: 'high'} as MarkDatum], newScale, newScale, radius, t);
  joinMarks('spMark', group, [{key: 'spMark', angle:closeSP, oldAngle: oldSP, path:'M-8,0 L-30,15 L-30,-15 Z', zorder: 'high'} as MarkDatum], oldScale, newScale, radius, t); 
  joinMarks('spLine', group, [{key: 'spLine', angle:closeSP, oldAngle: oldSP, path:'M-60,0 L-15,0', zorder: 'high'} as MarkDatum], oldScale, newScale, radius, t); 

  if (props.domain=='ra_24' && props.lst) {
     joinMarks('lstMark', group, [
       { key: '1', angle:props.lst, path:'M-8,0 L18,0', offset:1, zorder:'high', level: 'dash'},
       { key: '2', angle:props.lst, label:'LST', offset:1.2, zorder:'high', level: 'label'},
     ], oldScale, newScale, radius, t);
  } else {
     joinMarks('lstMark', group, [], oldScale, newScale, radius, t);
  }

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

  .lstMark {
    fill: rgb(250, 166, 135);
    &.label {
      font-size: 16px; 
    }
    &.dash {
      stroke: rgb(250, 166, 135);
      stroke-width: 5; 
    }
  }

  .scaleArcs {
    fill: none;
    stroke-width: 16;
    &.tk-dashed { stroke: lightskyblue; }
    &.tk-solid { stroke: lightskyblue; }
  }

  .warningArcs {
    fill: none;
    stroke-width: 12;
    stroke: var(--q-warning); 
  }

  .tkArcPVtoSP {
    fill: none;
    stroke-width: 12;
    stroke: var(--q-positive); 
  }

  .pvMark { fill: white; }
  .spMark { fill: var(--q-positive); }
  .spLine {
    stroke: var(--q-positive);
    stroke-width: 8;
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
  position: absolute;
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
  pointer-events: none;
}


.overlay-container .sp-readout-value {
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
.q-fab__actions--closed .q-btn {
  pointer-events: none;     // fixes aria issues when fab buttons are hidden
}
.q-fab__actions {
  opacity: 1;
}
.overlay-container .q-fab.row {
  pointer-events: auto;
  opacity: 0.5;
}

:deep(.no-edit-cursor) {
  cursor: default;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;

}

</style>
