<template>
    <div class="bg-white"  style="width: 100vw; height: 100vh;">
        <q-btn flat dense round to="/dashboard" aria-label="Menu" >
          <q-avatar>
            <q-img src="icons/favicon-128x128.png" style="width: 35px; height: 35px;"/>
          </q-avatar>
        </q-btn>
    </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'
import { useQuasar } from 'quasar'

const $q = useQuasar()

onMounted(async () => {
  try {
    await $q.fullscreen.request()
  } catch (err) {
    console.error('Failed to enter fullscreen', err)
  }
})

onBeforeUnmount(async () => {
  if ($q.fullscreen.isActive) {
    try {
        await $q.fullscreen.exit()
    } catch (err) {
        console.error('Failed to exit fullscreen', err)
    }
  }
})
</script>