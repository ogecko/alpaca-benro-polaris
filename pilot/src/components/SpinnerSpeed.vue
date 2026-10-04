<template>
  <div class="row items-center no-wrap ">
    <svg ref="svgRef" class="q-spinner text-primary" width="50px" height="80px" viewBox="0 0 100 122"
         preserveAspectRatio="xMidYMid" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="50" r="44" fill="none" stroke-width="4" stroke-opacity=".5" stroke="currentColor" />
      <text x="50" y="50" text-anchor="middle" dominant-baseline="middle" fill="currentColor" font-size="35px">
        {{ props.label }}
      </text>
      <circle ref="orbitingCircle" cx="8" cy="54" r="6" fill="currentColor" stroke-width="3" stroke="currentColor" />
      <text x="50" y="130" text-anchor="middle" dominant-baseline="middle" fill="currentColor" font-size="35px">
        {{ positionStr }}
      </text>    </svg>
  </div>
</template>

<script lang="ts" setup>
import { ref,  onMounted, onUnmounted, computed } from 'vue'
import { formatDegreesHr } from 'src/utils/scale';
import { onFrame } from 'src/utils/animationClock'

const props = defineProps<{
  speed: number | undefined
  position: number | undefined
  label: string | undefined
}>()

const orbitingCircle = ref<SVGCircleElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)

const rotationSpeed = computed(() => {
  const s = props.speed ?? 0
  return mapLog(s) // seconds per full rotation
})

const positionStr = computed(() => {
  return props.position!=undefined ? formatDegreesHr(props.position, "deg", 1) : ''
})

function mapLog(x: number): number {
  const absx = Math.abs(x)
  const xMin = 0.002
  const xMax = 9
  const yMin = 0.2
  const yMax = 5
  if (absx < xMin) return 0
  const logX = Math.log10(absx)
  const logMin = Math.log10(xMin)
  const logMax = Math.log10(xMax)
  const t = (logX - logMin) / (logMax - logMin)
  const y =  yMax - t * (yMax - yMin)
  return 360 / y

}

// 🌀 Rotation logic
// Driven by the shared redraw clock (animationClock: at most 20 redraws a second, fewer on a slow PC, together with
// the live charts) instead of its own requestAnimationFrame loop, which repainted at the display's full rate. The dot
// is only moved when it has visibly moved, so a stopped motor costs nothing.
const MIN_STEP_DEG = 0.5      // smallest rotation worth redrawing
let angle = 0
let shown: number | null = null
let lastTime = performance.now()
let stopTicking: (() => void) | null = null

function tick(t: number) {
  const delta = (t - lastTime) / 1000 // seconds
  lastTime = t

  const direction = (props.speed ?? 0) <= 0 ? 1 : -1
  const speed = direction * rotationSpeed.value // signed degrees/sec
  angle = (angle + delta * speed) % 360

  if (orbitingCircle.value && (shown === null || Math.abs(angle - shown) >= MIN_STEP_DEG)) {
    orbitingCircle.value.setAttribute('transform', `rotate(${angle.toFixed(2)} 50 50)`)
    shown = angle
  }
}

onMounted(() => {
  lastTime = performance.now()
  stopTicking = onFrame(tick)
})

onUnmounted(() => {
  stopTicking?.()
  stopTicking = null
})
</script>

<style scoped>
.q-spinner {
  transition: transform 0.2s ease;
}
</style>
