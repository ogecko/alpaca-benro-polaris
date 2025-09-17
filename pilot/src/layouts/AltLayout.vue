<template>
  <q-layout view="hHh LpR fFf" class="dark-page">
    <!-- Alpaca Pilot Header Bar -->
    <q-header elevated height-hint="58">
      <q-toolbar>
        <!-- Alpaca Pilot Icon/Menu -->
        <q-btn flat dense round @click="toggleLeftDrawer" aria-label="Menu" >
          <q-avatar>
            <q-img src="icons/favicon-128x128.png" style="width: 35px; height: 35px;"/>
          </q-avatar>
        </q-btn>
        <!-- Home, Connect, Settings, Logs Tabs -->
        <q-tabs inline-label  active-class="active-link-bottom" active-bg-color="secondary">
          <q-btn v-if="$q.screen.gt.xs" flat no-caps no-wrap to="/">
            <q-toolbar-title shrink class="text-weight-bold">Alpaca Pilot</q-toolbar-title>
          </q-btn>
          <q-route-tab v-else icon="mdi-home"  to="/"/>
          <q-route-tab icon="mdi-transit-connection-variant" :label="$q.screen.gt.sm ? 'Connect' : ''"  to="/connect" 
                      :alert="dev.restAPIConnected?'positive':'negative'" />
          <q-route-tab icon="mdi-cog" :label="$q.screen.gt.sm ? 'Settings' : ''" to="/config"/>
          <q-route-tab icon="mdi-database-clock-outline" :label="$q.screen.gt.sm ? 'Logs' : ''" to="/log"/>
        </q-tabs>
        <!-- Search -->
        <div class="row no-wrap q-pl-md">
          <q-input rounded dense filled bg-color="blue-9" v-model="search" placeholder="Search Catalogue">
            <template v-slot:append>
              <q-btn  round icon="mdi-magnify" unelevated />
            </template>
          </q-input>
        </div>

        <q-space />

        <!-- Battery and Notifications -->
        <div class="q-gutter-sm row items-center no-wrap">
            <div v-if="p.battery_is_available">
                <span class="text-body">{{p.battery_level}}%</span>
                <q-icon class="" size="md" :name="getBatteryIcon()" :color="getBatteryColor()"/>
                <q-tooltip>Polaris Battery Level</q-tooltip>
            </div>
            <!-- <q-btn round dense flat  icon="mdi-bell">
                <q-badge color="red" text-color="white" floating>
                2
                </q-badge>
                <q-tooltip>Notifications</q-tooltip>
            </q-btn> -->
        </div>
      </q-toolbar>
    </q-header>

    <!-- LHS Draw menu -->
    <q-drawer v-model="leftDrawerOpen" show-if-above bordered class="dark-page" :width="200" >
      <q-scroll-area class="fit">
        <!-- Deep Sky Objects -->
        <q-list dense>
          <q-item-label header class="text-weight-bold text-uppercase">
            Deep Sky Objects
          </q-item-label>
          <q-item v-for="link in links2" :key="link.text" v-ripple clickable :to="link.to" active-class="active-link-right">
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-separator class="q-mt-md q-mb-xs" />          
        </q-list>
       
        <!-- Orbitals -->
        <q-list dense>
          <q-item-label header class="text-weight-bold text-uppercase">
            Orbitals
          </q-item-label>

          <q-item v-for="link in links3" :key="link.text" v-ripple clickable :to="link.to">
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-separator class="q-my-md" />
        </q-list>
       
        <!-- Experimental -->
        <q-list dense>
          <q-item-label header class="text-weight-bold text-uppercase">
            Experimental
          </q-item-label>
          <q-item v-for="link in links4" :key="link.text" v-ripple clickable :to="link.to">
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>
          <q-separator class="q-mt-md q-mb-lg" />
        </q-list>
       
        <!-- About Us and Terms-->
        <q-list dense>
          <div class="q-px-md text-grey-7">
            <div class="row items-center q-gutter-x-sm q-gutter-y-xs">
              <RouterLink v-for="button in buttons1" :key="button.text" :to="button.to" class="YL__drawer-footer-link">
                {{ button.text }}
              </RouterLink>
            </div>
          </div>

          <!-- Terms -->
          <div class="q-py-md q-px-md text-grey-7">
            <div class="row items-center q-gutter-x-sm q-gutter-y-xs">
              <RouterLink v-for="button in buttons2" :key="button.text" :to="button.to" class="YL__drawer-footer-link">
                {{ button.text }}
              </RouterLink>
            </div>
          </div>
        </q-list>


      </q-scroll-area>
    </q-drawer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>



</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch  } from 'vue'
import { useStatusStore } from 'stores/status'
import { RouterLink } from 'vue-router'
import { useDeviceStore } from 'src/stores/device'
import { useStreamStore } from 'src/stores/stream'

const leftDrawerOpen = ref(false)
const search = ref('')
const dev = useDeviceStore()
const p = useStatusStore()
const socket = useStreamStore()

onMounted(() => {
  // socket.connectSocket()   //    connect whenever the socketURL changes
  // socket.subscribe('status')
})

onUnmounted(() => {
  socket.unsubscribe('status')
  socket.disconnectSocket()
})

watch([() => dev.restAPIConnected, ()=>socket.socketURL], ()=>{
  if (dev.restAPIConnected && socket) {
    socket.connectSocket()   //    
    socket.subscribe('status')
  }

})


function toggleLeftDrawer () {
  leftDrawerOpen.value = !leftDrawerOpen.value
}

function getBatteryColor(): string {
  if (p.battery_level >= 50) {
    return p.battery_is_charging ? 'light-green' : 'white'
  } else if (p.battery_level >= 20) {
    return 'warning'
  } else {
    return 'negative'
  }
}

function getBatteryIcon(): string {
  const levels = [
    { threshold: 95, charging: 'mdi-battery-charging-100', discharging: 'mdi-battery' },
    { threshold: 90, charging: 'mdi-battery-charging-90', discharging: 'mdi-battery-90' },
    { threshold: 80, charging: 'mdi-battery-charging-80', discharging: 'mdi-battery-80' },
    { threshold: 70, charging: 'mdi-battery-charging-70', discharging: 'mdi-battery-70' },
    { threshold: 60, charging: 'mdi-battery-charging-60', discharging: 'mdi-battery-60' },
    { threshold: 50, charging: 'mdi-battery-charging-50', discharging: 'mdi-battery-50' },
    { threshold: 40, charging: 'mdi-battery-charging-40', discharging: 'mdi-battery-40' },
    { threshold: 30, charging: 'mdi-battery-charging-30', discharging: 'mdi-battery-30' },
    { threshold: 20, charging: 'mdi-battery-charging-20', discharging: 'mdi-battery-20' },
    { threshold: 10, charging: 'mdi-battery-charging-10', discharging: 'mdi-battery-10' },
  ]

  for (const level of levels) {
    if (p.battery_level >= level.threshold) {
      return p.battery_is_charging ? level.charging : level.discharging
    }
  }

  return 'mdi-battery-alert'
}

const links2 = [
  { icon: 'mdi-flare', text: 'Stars', to: '/' },
  { icon: 'mdi-horse-variant', text: 'Nebulae', to: '/' },
  { icon: 'mdi-cryengine', text: 'Galaxies', to: '/' },
  { icon: 'mdi-blur', text: 'Clusters', to: '/' },
]

const links3 = [
  { icon: 'mdi-earth', text: 'Planets', to: '/' },
  { icon: 'mdi-moon-waning-crescent', text: 'Moons', to: '/' },
  { icon: 'mdi-cookie', text: 'Asteroids', to: '/' },
  { icon: 'mdi-magic-staff', text: 'Comets', to: '/' },
  { icon: 'mdi-satellite-variant', text: 'Satelites', to: '/' },
]

const links4 = [
  { icon: 'mdi-set-split', text: 'Calibration', to: '/speed' },
  { icon: 'mdi-chart-line', text: 'KF Tuning', to: '/kalman' },
  { icon: 'mdi-chart-bell-curve-cumulative', text: 'PID Tuning', to: '/' },
  { icon: 'mdi-pulse', text: 'PWM Testing', to: '/pwm' },
  { icon: 'mdi-format-vertical-align-top', text: 'Leveling', to: '/' },
  { icon: 'mdi-stethoscope', text: 'Diagnostics', to: '/' },
]
  const buttons1 = [
    { text: 'About', to: '/' },
    { text: 'Copyright', to: '/' },
    { text: 'Contact us', to: '/' },
    { text: 'Position', to: '/position' },
    { text: 'Markdown', to: '/markdown' },
    { text: 'Widgets', to: '/test' },
  ]
  const buttons2 = [
    { text: 'Terms', to: '/' },
    { text: 'Privacy', to: '/' },
    { text: 'Policy & Safety', to: '/' },
  ]


</script>

<style scoped lang="scss">
.active-link-bottom {
  ::v-deep(.q-tab__indicator) {
    border-bottom: 6px solid $blue-3; 
  }
}

.active-link-right {
  border-right: 6px solid $blue-3; 
}


.YL__drawer-footer-link {
  color: var(--q-color-grey-6);
  font-size: 0.75rem;
  text-decoration: none;
  cursor: pointer;

  &:hover {
      text-decoration: underline;
      color: $grey-4;
  }
}
</style>