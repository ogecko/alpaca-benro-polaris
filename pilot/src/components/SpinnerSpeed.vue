<template>
  <div class="row items-center no-wrap q-pb-md">
    <svg ref="svgRef" class="q-spinner text-primary" width="50px" height="50px" viewBox="0 0 100 100"
         preserveAspectRatio="xMidYMid" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="50" r="44" fill="none" stroke-width="4" stroke-opacity=".5" stroke="currentColor" />
      <text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" fill="currentColor" font-size="35px">
        {{ props.label }}
      </text>
      <circle ref="orbitingCircle" cx="8" cy="54" r="6" fill="currentColor" stroke-width="3" stroke="currentColor" />
    </svg>
  </div>
</template>

<script lang="ts" setup>
import { ref,  onMounted, onUnmounted, computed } from 'vue'

const props = defineProps<{
  speed: number | undefined
  label: string | undefined
}>()

const orbitingCircle = ref<SVGCircleElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)

const rotationSpeed = computed(() => {
  const s = props.speed ?? 0
  return mapLog(Math.abs(s)) // seconds per full rotation
})


function mapLog(x: number): number {
  const xMin = 0.0059018
  const xMax = 9
  const yMin = 0.2
  const yMax = 5
  const logX = Math.log10(x)
  const logMin = Math.log10(xMin)
  const logMax = Math.log10(xMax)
  const t = (logX - logMin) / (logMax - logMin)
  return yMax - t * (yMax - yMin)
}

// 🌀 Rotation logic
let angle = 0
let lastTime = performance.now()
let animationFrameId: number | null = null

function animate() {
  const now = performance.now()
  const delta = (now - lastTime) / 1000 // seconds
  lastTime = now

  const direction = (props.speed ?? 0) <= 0 ? 1 : -1
  const speed = direction * (360 / rotationSpeed.value) // signed degrees/sec
  angle = (angle + delta * speed) % 360

  if (orbitingCircle.value) {
    orbitingCircle.value.setAttribute(
      'transform',
      `rotate(${angle.toFixed(2)} 50 50)`
    )
  }

  animationFrameId = requestAnimationFrame(animate)
}

onMounted(() => {
  lastTime = performance.now()
  animationFrameId = requestAnimationFrame(animate)
})

onUnmounted(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }
})
</script>

<style scoped>
.q-spinner {
  transition: transform 0.2s ease;
}
</style>
