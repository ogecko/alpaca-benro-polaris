<template>
  <q-page class="q-pa-sm">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Driver Logfile
        <q-badge v-if="isAtBottom" size="lg" color="primary">Live</q-badge>
        <div v-if="$q.screen.gt.xs" class="text-caption text-grey-6">
        Monitor device status, activity, communications, and events in real time 
       </div>
      </div>
      <q-space />
      <div class="q-gutter-md flex justify-end q-mr-md">
        <q-btn-dropdown rounded color="grey-9" label="Log Settings" :content-style="{ width: '600px' }">
          <LogSettings />
        </q-btn-dropdown>
        <q-toggle dense label="Live" v-model="keepAtBottom"/>
      </div>
    </div>

    <!-- Log card fills rest -->
    <q-card flat bordered class="col">
      <q-card-section class="column" style="font-family: monospace;" >
        <q-scroll-area ref="scrollArea" @scroll="onScroll"  style="height: 85vh; font-family: monospace;" class="text-body1"
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
import { useStreamStore } from 'src/stores/stream'
import LogSettings from 'src/components/LogSettings.vue'
import StatusBanners from 'src/components/StatusBanners.vue'

import type { TelemetryRecord } from 'src/stores/stream'
import type { ComponentPublicInstance } from 'vue'
import { useDeviceStore } from 'src/stores/device'

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


const socket = useStreamStore()
const dev = useDeviceStore()
const logEntries = computed(() => socket.topics['log'] || [])
const isAtBottom = ref(true)
const keepAtBottom = ref(true)
const scrollArea = ref()

onMounted(() => {
  socket.connectSocket()   //    'ws://192.168.50.54:5556/ws'
  socket.subscribe('log')
  scrollToBottom()
})

onUnmounted(() => {
  socket.unsubscribe('log')
})

watch(() => dev.isVisible, (isVisible) => {
  void (isVisible ? socket.subscribe('log') : socket.unsubscribe('log'))
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
