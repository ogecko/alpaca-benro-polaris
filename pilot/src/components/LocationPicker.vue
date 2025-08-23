<template>
    <div class="map-container">
      <div id="map" :class="mapAvailable ? 'showMap' : 'hideMap'"></div>
    </div>
</template>

<script setup lang="ts">
import axios from 'axios'
import { onMounted, watch, ref } from 'vue';
import { useConfigStore } from 'stores/config';

import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix to ensure quasar picks up the default marker icon paths
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
L.Icon.Default.imagePath = '';
L.Icon.Default.mergeOptions({
  iconRetinaUrl: new URL(markerIcon2x, import.meta.url).href,
  iconUrl: new URL(markerIcon, import.meta.url).href,
  shadowUrl: new URL(markerShadow, import.meta.url).href
});

const mapAvailable = ref(false)
const cfg = useConfigStore()
let marker: L.Marker | undefined;
let map: L.Map;

onMounted(() => {
    map = L.map('map').setView([cfg.site_latitude, cfg.site_longitude], 13);
    marker = L.marker([cfg.site_latitude, cfg.site_longitude], { title: 'Site location' }).addTo(map);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    map.on('click', (e) => {
        const { lat, lng } = e.latlng;
        if (marker) {
        marker.setLatLng(e.latlng);
        } else {
        marker = L.marker(e.latlng).addTo(map);
        }
        void cfg.configUpdate({ site_latitude: lat, site_longitude: lng });
    });

    axios.head('https://tile.openstreetmap.org/0/0/0.png')
    .then(() => {
        mapAvailable.value = true
    })
    .catch((err) => {
        console.error('OpenStreetMap unavailable:', err);
        mapAvailable.value = false;
    });

});

// Watch for reactive updates to cfg.site_latitude and cfg.site_longitude
watch(
  () => [cfg.site_latitude, cfg.site_longitude],
  ([lat, lng]) => {
    if (typeof lat === 'number' && typeof lng === 'number' && marker && map ) {
      marker.setLatLng([lat, lng]);
      map.setView([lat, lng], map.getZoom()); // recenter map
    }
  }
);

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
