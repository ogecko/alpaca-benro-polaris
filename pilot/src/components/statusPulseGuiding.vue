<template>
        <q-chip :color="statusColor" :outline="statusOutline" :icon="statusIcon" class="q-pa-md">
        {{statusLabel}}
      </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'stores/config';


const p = useStatusStore()
const cfg = useConfigStore()

const last = computed(() => Math.hypot(p.gdpulse[0] ?? 0, p.gdpulse[1] ?? 0, p.gdpulse[2] ?? 0) * 3600 )
const isIdle = computed(() => last.value==0 || !p.tracking)

const statusLabel = computed(() => 
  cfg.advanced_pulse_guiding==false ? "Disabled" :
                       isIdle.value ? "Idle" :
                                     `Last pulse ${(last.value??0).toFixed(2)}"`
)

const statusColor = computed(() =>
  cfg.advanced_pulse_guiding==false ? "grey-8" :
                        isIdle.value? "primary" :
                                      "positive"
)

const statusOutline = computed(() => (
  cfg.advanced_pulse_guiding==false ? true :
                       isIdle.value ? true :
                                    false

))

const statusIcon = computed(() =>  "mdi-pulse")



</script>

<style scoped>

</style>