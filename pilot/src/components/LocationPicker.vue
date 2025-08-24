<template>
  <div class="map-container">
    <div id="map" :class="mapAvailable ? 'showMap' : 'hideMap'"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch, ref, toRefs } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import axios from 'axios'
import { getLocationServices, } from 'src/utils/locationServices'
import type { LocationResult } from 'src/utils/locationServices'

import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

L.Icon.Default.imagePath = ''
L.Icon.Default.mergeOptions({
  iconRetinaUrl: new URL(markerIcon2x, import.meta.url).href,
  iconUrl: new URL(markerIcon, import.meta.url).href,
  shadowUrl: new URL(markerShadow, import.meta.url).href
})

// Props
const props = defineProps<{
  lat: number
  lon: number
}>()

// Emits
const emit = defineEmits<{
  (e: 'locationInfo', value: LocationResult): void
}>()

const { lat, lon } = toRefs(props)
const mapAvailable = ref(false)
let map: L.Map
let marker: L.Marker | undefined

onMounted(() => {
  serviceCheck()

  map = L.map('map').setView([lat.value, lon.value], 13)
  marker = L.marker([lat.value, lon.value], { title: 'Site location' }).addTo(map)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(map)

  map.on('click', (e) => {
    void (async () => {
      const { lat: newLat, lng: newLon } = e.latlng
      if (marker) {
        marker.setLatLng(e.latlng)
      } else {
        marker = L.marker(e.latlng).addTo(map)
      }

      const result = await getLocationServices(newLat, newLon)
      emit('locationInfo', result)
    })()
  })
})

watch([lat, lon], ([newLat, newLon]) => {
  if (typeof newLat === 'number' && typeof newLon === 'number' && marker && map) {
    marker.setLatLng([newLat, newLon])
    map.setView([newLat, newLon], map.getZoom())
  }
})

function serviceCheck() {
  axios.head('https://tile.openstreetmap.org/0/0/0.png')
    .then(() => {
      mapAvailable.value = true
      setTimeout(() => map.invalidateSize(), 100)
    })
    .catch((err) => {
      console.error('OpenStreetMap unavailable:', err)
      mapAvailable.value = false
    })
}
</script>

<style lang="scss">
.showMap {
  height: 200px;
}
.hideMap {
  height: 0px;
}
.map-container {
  width: 100%;
  max-height: 200px;
  overflow: hidden;
  position: relative;
}
</style>
