<template>
      <div class="row no-wrap items-center">
        <!-- @click.stop: the status row's click opens the PID page -->
        <div v-if="isOrbital" class="q-mr-sm" @click.stop>
          <q-knob v-model="lead_var" show-value reverse size="44px" font-size="11px" :thickness="0.22" color="positive"
                  track-color="grey-4" :min="-5.556" :inner-min="-5.0" :inner-max="5.0" :max="5.556" :step="0.05"
                  @change="onLeadChange">{{lead_str}}</q-knob>
          <q-tooltip>Orbital lead (s): aim this far ahead of the orbital body</q-tooltip>
        </div>
        <q-chip :color="statusColor" :outline="statusOutline" :icon="statusIcon" class="q-pa-md">
        {{statusLabel}}
      </q-chip>
      </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'src/stores/config'
import { angularDifference } from 'src/utils/angles'


const p = useStatusStore()
const cfg = useConfigStore()

// Orbital lead knob: tunes orbital_lead_sec live while tracking an orbital. Reversed with +-5 s inside a +-5.556 s scale,
// so 0 sits at the bottom, +5 s at 5% and -5 s at 95% of the dial.
const isOrbital = computed(() => p.tracking && (p.orbitalstatus[0] ?? 0) > 0)
const lead_var = ref<number>(cfg.orbital_lead_sec ?? 0)
const lead_str = computed<string>(() => `${lead_var.value > 0 ? '+' : ''}${lead_var.value.toFixed(2)}`)

watch(() => cfg.orbital_lead_sec, (v) => { lead_var.value = v ?? 0 })

async function onLeadChange(v: number) {
  await cfg.configUpdate({ orbital_lead_sec: v })
}

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