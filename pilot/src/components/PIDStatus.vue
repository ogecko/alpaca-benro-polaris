<template>
        <q-chip :color="statusColor" :outline="statusOutline" :icon="statusIcon" class="q-pa-md">
        {{statusLabel}}
        <q-circular-progress v-if="long_cmd" :value="progress" :thickness="0.4" size="25px" color="white" track-color="green-10" class="q-ml-md"/>
      </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStatusStore } from 'src/stores/status'

const p = useStatusStore()

const long_cmd = computed(() => p.gotoing || p.rotating || p.pidmode=='HOMING' || p.pidmode=='PARKING' )

const progress = computed(() => {
  const [x,y,z] = p.errsig as [number, number, number] 
  const magnitude = Math.max(Math.abs(x), Math.abs(y), Math.abs(z))
  const log = Math.log(magnitude)
  const tollerance = p.tracking ? p.pidKc/60/20 : p.pidKc/60
  const min = Math.log(tollerance)
  const max = Math.log(15)
  const raw = (log - min) / (max - min) * 100
  return 100 - Math.min(100, Math.max(0, raw))
})

const statusLabel = computed(() => 
  p.pidmode=='PRESETUP' ? "PreSetup" :
  p.pidmode=='LIMIT' ? "Limit" :
  p.pidmode=='HOMING' ? "Homing" :
  p.pidmode=='PARKING' ? "Parking" :
  p.pidmode=='FLIP CW' ? "Flip CW" :
  p.pidmode=='FLIP CCW' ? "Flip CCW" :
  p.pidmode=='UNWIND' ? "Unwind" :
  p.athome ? "At Home" : 
  p.atpark ? "Parked" : 
  p.gotoing ? "Gotoing" : 
  p.slewing ? "Slewing" :
  p.rotating ? "Rotating" :
  p.ispulseguiding ? "Guiding" :
  p.tracking  ? trackingStatusLabel.value : 
  p.pidglock  ? "Gimbal" : 
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
  statusLabel.value==="Idle" ? "primary" :
  "positive"
)

const statusOutline = computed(() => (
  statusLabel.value==="Idle" ||
  statusLabel.value==="Gimbal" ||
  statusLabel.value==="At Home"
))

const statusIcon = computed(() => 
  p.pidmode=='PRESETUP' ? "mdi-cellphone-cog" :
  p.pidmode=='LIMIT' ? "mdi-alert" :
  p.pidmode=='HOMING' ? "mdi-home-outline" :
  p.pidmode=='PARKING' ? "mdi-alpha-p" :
  p.pidmode=='FLIP CW' ? "mdi-rotate-360" :
  p.pidmode=='FLIP CCW' ? "mdi-rotate-360" :
  p.pidmode=='UNWIND' ? "mdi-rotate-360" :
  p.pidglock  ? "mdi-lock" : 
  p.atpark ? "mdi-parking" : 
  p.athome ? "mdi-home" : 
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