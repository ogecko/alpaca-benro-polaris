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
  p.tracking  ? trackingStatusLabel.value : 
               "Idle"
)


const trackingStatusLabel = computed(() => {
  const [isTracking, az, alt] = p.orbitalstatus;
  const azText = az !== undefined ? `${Math.round(az)}°` : '—';
  const altText = alt !== undefined ? `${Math.round(alt)}°` : '—';
  return isTracking === 1
    ? `${trackingLabel.value} (Az ${azText} Alt ${altText})`
    : trackingLabel.value;
});



const trackingLabel = computed(() =>
  p.trackingrate==0 ? "Sidereal" : 
  p.trackingrate==1 ? "Lunar" : 
  p.trackingrate==2 ? "Solar" : 
  p.trackingrate==3 && p.trackingname ? p.trackingname : 
                      "Custom" 
)

const statusColor = computed(() =>
  p.pidmode=='PRESETUP' ? "negative" :
  p.pidmode=='LIMIT' ? "negative" : 
  p.orbitalstatus[0] == 1 && p.pidmode == 'TRACK' ? "warning" : 
  "positive"

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