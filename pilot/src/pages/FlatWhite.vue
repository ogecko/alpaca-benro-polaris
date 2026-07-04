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
  await $q.fullscreen.request()
})

onBeforeUnmount(() => {
  if ($q.fullscreen.isActive) {
    $q.fullscreen.exit()
  }
})
</script>