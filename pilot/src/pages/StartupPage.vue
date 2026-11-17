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

import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useDeviceStore } from 'src/stores/device'
import { useRouter } from 'vue-router'


const router = useRouter()
const dev = useDeviceStore()

const show = ref(false)
let dashboardTimer: ReturnType<typeof setTimeout> | undefined

// ------------------- Lifecycle Events ---------------------

onMounted(async () => {
  await dev.connectRestAPI()
  show.value=true
  // After 2 seconds go to the dashboard, but only if the user is still on this banner page
  dashboardTimer = setTimeout(() => {
    if (router.currentRoute.value.path === '/') void router.push('/dashboard')
  }, 2000)
})

onBeforeUnmount(() => {
  clearTimeout(dashboardTimer)
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
