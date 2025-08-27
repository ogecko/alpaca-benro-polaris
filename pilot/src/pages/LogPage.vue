<template>
  <q-page class="q-pa-md">
    <div class="text-h6 q-mb-md">
      Alpaca Driver Logfile
      <q-badge v-if="isAtBottom" size="lg" color="primary">Live</q-badge>
    </div>

    <q-card flat bordered>
      <q-card-section style="font-family: monospace;">
        <q-scroll-area ref="scrollArea" @scroll="onScroll" style="height: 70vh; font-family: monospace;">
          <div>
            <div v-for="(entry, index) in logEntries" :key="index">
              {{ format(entry) }}
            </div>
            <q-intersection @visibility="onSentinelVisibility" />
          </div>
        </q-scroll-area>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed,  } from 'vue'
import { useStreamStore } from 'stores/stream'
import type { TelemetryRecord } from 'stores/stream'
import type { ComponentPublicInstance } from 'vue'

export type QScrollAreaScrollEvent = {
  ref: ComponentPublicInstance
  verticalPosition: number
  verticalPercentage: number
  verticalSize: number
  verticalContainerSize: number
  verticalContainerInnerSize: number
  horizontalPosition: number
  horizontalPercentage: number
  horizontalSize: number
  horizontalContainerSize: number
  horizontalContainerInnerSize: number
}


const store = useStreamStore()
const logEntries = computed(() => store.topics['log'] || [])
const isAtBottom = ref(false)
const scrollArea = ref()

onMounted(() => {
  store.connect('ws://192.168.50.54:5556/ws')
  store.subscribe('log')
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

function onSentinelVisibility(visible: boolean) {
  isAtBottom.value = visible
}


function onScroll(pos: QScrollAreaScrollEvent) {
  console.log('Scroll position:', pos)
  // const scrollEl = scrollArea.value?.$el?.querySelector('.q-scrollarea__scroll')
  // if (!scrollEl) return

  // const threshold = 20 // px from bottom to count as "at bottom"
  // const maxScrollTop = scrollEl.scrollHeight - scrollEl.clientHeight
  // isAtBottom.value = position.top >= maxScrollTop - threshold

  // lastScrollTop.value = position.top
}


</script>
