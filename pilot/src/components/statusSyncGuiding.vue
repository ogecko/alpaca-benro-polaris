<template>
        <q-chip :color="statusColor" :outline="statusOutline" :icon="statusIcon" class="q-pa-md">
        {{statusLabel}}
      </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'stores/config';

const MAX_SYNC_INTERVAL_SEC = 60*5

const p = useStatusStore()
const cfg = useConfigStore()

const valid = computed(() => p.sgstatus ? p.sgstatus[0] : 0)
const interval = computed(() => p.sgstatus ? p.sgstatus[1] : 0)
const last = computed(() => p.sgstatus ? p.sgstatus[2] : 0)
const isfirst = computed(() => ((interval.value??0)==0) && ((last.value??0) > 0))
const islate = computed(() => ((interval.value??0) > 0) && ((last.value??0) > (interval.value??0)*2))
const isnone = computed(() => (last.value??0) > MAX_SYNC_INTERVAL_SEC)

const statusLabel = computed(() => 
  cfg.advanced_sync_guiding==false ? "Disabled" :
                    valid.value==0 ? "Idle" :
                      isnone.value ? `None for ${Math.floor((last.value??0)/60)} min` :
                      islate.value ? `Missed for ${last.value??0}s` :
                      isfirst.value ? `Received ${last.value??0}s ago` :
               interval.value == 0 ? 'Enabled' :
                                     `Every ${interval.value??0}s`
)

const statusColor = computed(() =>
  cfg.advanced_sync_guiding==false ? "grey-8" :
                    valid.value==0 ? "primary" :
                      isnone.value ? "warning" :
                      islate.value ? "warning" :
                                     "positive"
)

const statusOutline = computed(() => (
  cfg.advanced_sync_guiding==false ? true :
                    valid.value==0 ? true :
                                    false

))

const statusIcon = computed(() =>  "mdi-sync")



</script>

<style scoped>

</style>