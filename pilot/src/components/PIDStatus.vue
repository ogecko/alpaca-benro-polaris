<template>
        <q-chip :color="statusColor" :outline="statusLabel=='Idle'" :icon="statusIcon" class="q-pa-md">
        {{statusLabel}}
      </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStatusStore } from 'src/stores/status'

const p = useStatusStore()

const statusLabel = computed(() => 
  p.pidmode=='PRESETUP' ? "PreSetup" :
  p.pidmode=='LIMIT' ? "Limit" :
  p.pidmode=='HOMING' ? "Homing" :
  p.pidmode=='PARKING' ? "Parking" :
  p.atpark ? "Parked" : 
  p.gotoing ? "Gotoing" : 
  p.slewing ? "Slewing" :
  p.rotating ? "Rotating" :
  p.ispulseguiding ? "Guiding" :
  p.tracking ? "Tracking" : 
               "Idle"
)

const statusColor = computed(() =>
  p.pidmode=='PRESETUP' ? "negative" :
  p.pidmode=='LIMIT' ? "negative" : "positive"
)

const statusIcon = computed(() => 
  p.pidmode=='PRESETUP' ? "mdi-cellphone-cog" :
  p.pidmode=='LIMIT' ? "mdi-alert" :
  p.pidmode=='HOMING' ? "mdi-home-outline" :
  p.pidmode=='PARKING' ? "mdi-alpha-p" :
  p.atpark ? "mdi-parking" : 
  p.gotoing ? "mdi-move-resize-variant" : 
  p.slewing ? "mdi-cursor-move" :
  p.rotating ? "mdi-restore" :
  p.ispulseguiding ? "mdi-pulse" :
  p.tracking ? "mdi-star-shooting-outline" : 
               "mdi-sleep"
)



</script>

<style scoped>

</style>