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

// Pointing deviation on the sky (arcsec) between the PID's target and where the mount points: the RA difference is
// in RA coordinate units, so scaled by cos(Dec) (near the pole a 17" RA step is ~3" of sky); position angle is left
// out -- a roll error doesn't move the field centre, and near the pole it largely repeats the RA error.
const dev = computed(() => Math.hypot(
  angularDifference(p.deltaref[0] ?? 0, p.rightascension*15) * Math.cos(p.declination * Math.PI / 180),
  angularDifference(p.deltaref[1] ?? 0, p.declination) ) * 3600
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