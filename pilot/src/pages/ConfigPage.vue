

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
        <q-input filled v-model="cfg.location" label="Location" @update:model-value="put('location', cfg.location)" />
        <div><strong>Latitude:</strong> {{ cfg.site_latitude }}</div>
        <div><strong>Longitude:</strong> {{ cfg.site_longitude }}</div>
        <div><strong>Elevation:</strong> {{ cfg.site_elevation }} m</div>
      </div>
      <div v-else class="text-negative">
        Configuration not loaded.
      </div>
            <q-btn flat label="Test" @click="putcall" />

    </q-card>
</q-page>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useConfigStore } from 'stores/config';
import { useDeviceStore } from 'src/stores/device';
import type { ConfigResponse } from 'stores/config';
import { debounce } from 'quasar'

const dev = useDeviceStore()
const cfg = useConfigStore()

onMounted(async () => {
  const shouldFetch =
    dev.alpacaConnected &&
    dev.alpacaConnectedAt &&
    cfg.fetchedAt < dev.alpacaConnectedAt

  if (shouldFetch) {
    await cfg.fetchConfig()
  }
})

const put = debounce(rawUpdateField, 500)
async function rawUpdateField<K extends keyof typeof cfg.$state>(key: K, value: typeof cfg.$state[K]) {
  try {
    const updated = await dev.apiAction<ConfigResponse>('ConfigTOML', { [key]: value });
    cfg.$patch(updated);
  } catch (err) {
    console.warn(`Failed to update ${key}:`, err);
  }
}


async function putcall() {
    console.log('test');
    const value = await dev.apiAction<string>('ConfigTOML', { location:'Test change', site_elevation: 345, advanced_control: true });
    console.log(value);
}


</script>