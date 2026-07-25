<template>
        <q-chip :color="statusColor" :outline="statusOutline" :icon="statusIcon" class="q-pa-md">
        {{statusLabel}}
      </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStatusStore } from 'src/stores/status'
import { angularDifference } from 'src/utils/angles'


const p = useStatusStore()

const dev = computed(() => Math.hypot(
  angularDifference(p.deltaref[0] ?? 0, p.rightascension*15), 
  angularDifference(p.deltaref[1] ?? 0, p.declination),
  angularDifference(p.deltaref[2] ?? 0, p.positionangle) ) * 3600
)
const isIdle = computed(() => !p.tracking)

const statusLabel = computed(() => 
                       isIdle.value ? "Idle" :
                                     `Deviation ${(dev.value??0).toFixed(1)}"`
)

const statusColor = computed(() =>
                        isIdle.value? "primary" :
                                      "positive"
)

const statusOutline = computed(() => (
                       isIdle.value ? true :
                                    false

))

const statusIcon = computed(() =>  "mdi-star-shooting-outline")



</script>

<style scoped>

</style>