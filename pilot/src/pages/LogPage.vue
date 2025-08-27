<template>
  <q-page class="q-pa-md">
    <div class="row q-col-gutter-lg items-center">
      <div class="col text-h6 q-mb-md">
        Alpaca Driver Logfile
        <q-badge v-if="isAtBottom" size="lg" color="primary">Live</q-badge>
        <q-badge v-if="storeChangedRecently" size="lg" color="primary">Updated</q-badge>
      </div>
      <div class="col-auto q-gutter-sm flex justify-end">
        <q-toggle class='col' label="Live" v-model="keepAtBottom"/>
      </div>
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
import { debounce } from 'quasar'
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
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
const isAtBottom = ref(true)
const keepAtBottom = ref(true)
const scrollArea = ref()

onMounted(() => {
  store.connect('ws://192.168.50.54:5556/ws')
  store.subscribe('log')
  setStoreChangedRecently()
  scrollToBottom()
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

function scrollToBottom() {
  const pos = scrollArea.value.getScroll()
    const maxPos = pos.verticalSize - pos.verticalContainerSize
    scrollArea.value.setScrollPosition('vertical', maxPos, 100)

}

const storeChangedRecently = ref(false)
let resetTimer: ReturnType<typeof setTimeout> | null = null
function setStoreChangedRecently() {
  storeChangedRecently.value = true
  if (resetTimer) {
    clearTimeout(resetTimer)
  }
  // only reset after X seconds of no changes
  resetTimer = setTimeout(() => { 
    storeChangedRecently.value = false
    resetTimer = null
  }, 1000)
}

const debouncedCheckForUserScroll = debounce(checkForUserScroll, 50)
function checkForUserScroll() {
  setTimeout(() => { 
    // scrolls without any store changes are user scrolls, turn off keepAtBottom
    if (!storeChangedRecently.value) {
      keepAtBottom.value = false
    }
  }, 50)
}

watch(store.topics['log'] ?? [], debounce(setStoreChangedRecently, 10))

watch(keepAtBottom, (newVal) => {
  if (newVal) {
    setStoreChangedRecently()
    scrollToBottom()
  }
})

function onScroll() {
    debouncedCheckForUserScroll()
    if (keepAtBottom.value) {
      scrollToBottom()
    }
}


</script>
