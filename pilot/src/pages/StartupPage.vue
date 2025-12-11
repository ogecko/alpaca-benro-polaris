<template>
  <transition name="fade">
  <q-page v-if="show">
      <!----- Logo Startup Image ----->
      <div class="row col-12 items-center fixed-center" style="height:100%; width:100%">
        <div class="col flex flex-center" style="height: 300px; ">
          <q-img
            src="../assets/abp-v2-logo-hires-full.png"
            fit="scale-down"
            style="max-width: 100%; max-height: 100%;"
          />
        </div>
      </div>
  </q-page>
  </transition>
</template>

<script setup lang="ts" >

import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from 'src/stores/device'
import { useRouter } from 'vue-router'


const router = useRouter()
const route = useRoute()
const dev = useDeviceStore()

const show = ref(false)

// ------------------- Lifecycle Events ---------------------

onMounted(async () => {
  const apiParam = Array.isArray(route.query.api)
    ? route.query.api[0]
    : route.query.api

  if (apiParam) {
    dev.restAPIPort = parseInt(apiParam)
  }

  if (!dev.alpacaHost && window.location.hostname) {
    dev.alpacaHost = window.location.hostname
  }

  if (!dev.restAPIPort && window.location.port) {
    dev.restAPIPort = parseInt(window.location.port)
  }

  if (dev.alpacaHost && dev.restAPIPort) {
    await dev.connectRestAPI()
  }
  show.value=true
  setTimeout(() => { void router.push('/dashboard') }, 2000)  // 2 seconds delay
})


// ------------------- Helper Functions ---------------------


// ------------------- Event Handlers ---------------------


</script>
<style>
.fade-enter-active, .fade-leave-active {
  transition: opacity .6s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
