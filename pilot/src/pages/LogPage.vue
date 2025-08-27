<template>
  <q-page class="q-pa-md">
    <div class="text-h6 q-mb-md">Live Root Logfile</div>

    <q-card flat bordered>
      <q-card-section style="font-family: monospace;">
        <q-scroll-area ref="scrollArea" style="height: 80vh;">
          <div style="font-family: monospace;">
            <div v-for="(entry, index) in logEntries" :key="index">
              {{ format(entry) }}
            </div>
            <div ref="sentinel"></div> <!-- This is our observer target -->
          </div>
        </q-scroll-area>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, onBeforeUnmount, ref, watch, nextTick, computed } from 'vue'
import { useStreamStore } from 'stores/stream'
import type { TelemetryRecord } from 'stores/stream'

const store = useStreamStore()
const logEntries = computed(() => store.topics['log'] || [])
const scrollArea = ref()
const sentinel = ref()
const isAtBottom = ref(true)

let observer: IntersectionObserver | null = null


onMounted(() => {
  store.connect('ws://192.168.50.54:5556/ws')
  store.subscribe('log')

  const trySetupObserver = () => {
    const rootEl = scrollArea.value?.$el
    const targetEl = sentinel.value
    if (!rootEl || !targetEl) {
      requestAnimationFrame(trySetupObserver)
      return
    }
    observer = new IntersectionObserver((entries) => {
      const entry = entries[0]
      isAtBottom.value = !!entry?.isIntersecting
    }, { root: rootEl, threshold: 1.0 })
    observer.observe(targetEl)
  }

  trySetupObserver()
})


onBeforeUnmount(() => {
  if (observer && sentinel.value) {
    observer.unobserve(sentinel.value)
  }
})

onUnmounted(() => {
  store.unsubscribe('log')
})

function format(entry: TelemetryRecord): string {
  const ts = entry.ts || ''
  const level = entry.level || ''
  const msg = ('text' in entry.data) ? entry.data.text : JSON.stringify(entry.data)
  return `[${ts}] [${level}] ${msg}`
}

watch(logEntries, async () => {
  await nextTick()
  if (isAtBottom.value && scrollArea.value) {
    scrollArea.value.setScrollPosition('vertical', scrollArea.value.scrollHeight)
  }
})


</script>
