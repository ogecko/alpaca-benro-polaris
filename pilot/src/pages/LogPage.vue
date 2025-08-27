<template>
  <q-page class="q-pa-sm column">
    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-lg items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Driver Logfile
        <q-badge v-if="isAtBottom" size="lg" color="primary">Live</q-badge>
      </div>
      <div class="col q-gutter-sm flex justify-end">
        <q-btn-dropdown rounded color="grey-9" label="Log Settings" >
          <LogSettings />
        </q-btn-dropdown>
      </div>
      <div class="col-auto q-gutter-sm flex justify-end">
        <q-toggle class='col' label="Live" v-model="keepAtBottom"/>
      </div>
    </div>
    <!-- Log card fills rest -->
    <q-card flat bordered class="col">
      <q-card-section class="column" style="font-family: monospace;" >
        <q-scroll-area ref="scrollArea" @scroll="onScroll"  style="height: 80vh; font-family: monospace;" class="text-body1"
          @wheel="resetKeepAtBottom" @click="resetKeepAtBottom" @touchstart="resetKeepAtBottom">
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
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useStreamStore } from 'stores/stream'
import type { TelemetryRecord } from 'stores/stream'
import type { ComponentPublicInstance } from 'vue'
import LogSettings from 'components/LogSettings.vue'

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
    scrollArea.value.setScrollPosition('vertical', maxPos, 200)
}

function resetKeepAtBottom() {
    keepAtBottom.value = false
}


function onScroll() {
  if (keepAtBottom.value) {
    scrollToBottom()
  }
}

watch(keepAtBottom, (val) => {
  if (val) {
    scrollToBottom()
  }
})


</script>
