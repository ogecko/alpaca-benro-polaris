

<template>
  <q-page class="q-pa-md">
    <div v-if="!dev.alpacaConnected" >
      <q-banner inline-actions rounded class="bg-warning">
        WARNING: You have lost connection to the Alpaca Driver. This app is offline.
        <template v-slot:action>
            <q-btn flat label="Reconnect" to="/connect" />
        </template>
      </q-banner>
    </div>
    <q-card flat bordered class="q-pa-md">
      <div class="text-h6">Alpaca Configuration</div>
      <q-separator spaced />
      <div v-if="cfg.fetchedAt">
        <div><strong>Location:</strong> {{ cfg.location }}</div>
        <div><strong>Latitude:</strong> {{ cfg.site_latitude }}</div>
        <div><strong>Longitude:</strong> {{ cfg.site_longitude }}</div>
        <div><strong>Elevation:</strong> {{ cfg.site_elevation }} m</div>
      </div>
      <div v-else class="text-negative">
        Configuration not loaded.
      </div>

    </q-card>
</q-page>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';

const dev = useDeviceStore()
const cfg = useConfigStore()

// onMounted(async () => {
//     if (dev.alpacaConnected)
//       await cfg.fetchConfig()
// })
onMounted(async () => {
  const shouldFetch =
    dev.alpacaConnected &&
    dev.alpacaConnectedAt &&
    cfg.fetchedAt < dev.alpacaConnectedAt

  if (shouldFetch) {
    await cfg.fetchConfig()
  }
})

</script>