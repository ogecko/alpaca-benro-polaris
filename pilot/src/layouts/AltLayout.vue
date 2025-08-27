<template>
  <q-layout view="hHh LpR fFf" class="dark-page">
    <q-header elevated class="q-py-xs" height-hint="58">
      <q-toolbar>
        <q-btn flat dense round
          @click="toggleLeftDrawer"
          aria-label="Menu"
          icon="mdi-menu"
        />

        <q-btn flat no-caps no-wrap class="q-ml-xs" to="/" v-if="$q.screen.gt.xs">
          <q-toolbar-title shrink class="text-weight-bold">
            Alpaca Pilot
          </q-toolbar-title>
        </q-btn>

        <q-space />

        <div class="YL__toolbar-input-container row no-wrap">
          <q-input dense outlined square v-model="search" placeholder="Search" class="bg-blue-9 col" />
          <q-btn class="YL__toolbar-input-btn" color="grey-4" text-color="grey-8" icon="mdi-magnify" unelevated />
        </div>

        <q-space />

        <div class="q-gutter-sm row items-center no-wrap">
            <div v-if="p.battery_is_available">
                <span class="text-body">{{p.battery_level}}%</span>
                <q-icon class="" size="md" :name="getBatteryIcon()" :color="getBatteryColor()"/>
                <q-tooltip>Polaris Battery Level</q-tooltip>
            </div>
            <q-btn round dense flat  icon="mdi-bell">
                <q-badge color="red" text-color="white" floating>
                2
                </q-badge>
                <q-tooltip>Notifications</q-tooltip>
            </q-btn>
        </div>
      </q-toolbar>
    </q-header>

    <q-drawer
      v-model="leftDrawerOpen"
      show-if-above
      bordered
      class="dark-page"
      :width="200"
    >
      <q-separator class="q-my-md" />

      <q-scroll-area class="fit">
        <q-list dense>
          <q-item v-for="link in links1" :key="link.text" :to="link.to" v-ripple clickable>
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>

          <q-separator class="q-my-md" />

          <q-item-label header class="text-weight-bold text-uppercase">
            Deep Sky Objects
          </q-item-label>

          <q-item v-for="link in links2" :key="link.text" v-ripple clickable>
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>

          <q-separator class="q-mt-md q-mb-xs" />

          <q-item-label header class="text-weight-bold text-uppercase">
            Orbitals
          </q-item-label>

          <q-item v-for="link in links3" :key="link.text" v-ripple clickable>
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>

          <q-separator class="q-my-md" />
          <q-item-label header class="text-weight-bold text-uppercase">
            Experimental
          </q-item-label>

          <q-item v-for="link in links4" :key="link.text" v-ripple clickable>
            <q-item-section avatar>
              <q-icon color="grey" :name="link.icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ link.text }}</q-item-label>
            </q-item-section>
          </q-item>

          <q-separator class="q-mt-md q-mb-lg" />

          <div class="q-px-md text-grey-7">
            <div class="row items-center q-gutter-x-sm q-gutter-y-xs">
              <a
                v-for="button in buttons1"
                :key="button.text"
                class="YL__drawer-footer-link"
                href="javascript:void(0)"
              >
                {{ button.text }}
              </a>
            </div>
          </div>
          <div class="q-py-md q-px-md text-grey-7">
            <div class="row items-center q-gutter-x-sm q-gutter-y-xs">
              <a
                v-for="button in buttons2"
                :key="button.text"
                class="YL__drawer-footer-link"
                href="javascript:void(0)"
              >
                {{ button.text }}
              </a>
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
import { ref, onMounted, onUnmounted  } from 'vue'
import { useStatusStore } from 'stores/status'
import { PollingManager } from 'src/utils/polling'

const leftDrawerOpen = ref(false)
const search = ref('')
const poll = new PollingManager()
const p = useStatusStore()

  onMounted(() => {
    poll.startPolling(() => { void p.statusFetch() }, 1, 'statusFetch')
  })

  onUnmounted(() => {
    poll.stopPolling()
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

  const links1 = [
    { icon: 'mdi-home', text: 'Home', to: '/' },
    { icon: 'mdi-power', text: 'Connections', to: '/connect' },
    { icon: 'mdi-cog-outline', text: 'Settings', to: '/config' },
    { icon: 'mdi-database-clock-outline', text: 'Log', to: '/log' },
  ]
  const links2 = [
    { icon: 'mdi-flare', text: 'Stars' },
    { icon: 'mdi-horse-variant', text: 'Nebulae' },
    { icon: 'mdi-cryengine', text: 'Galaxies' },
    { icon: 'mdi-blur', text: 'Clusters' },
  ]
  const links3 = [
    { icon: 'mdi-earth', text: 'Planets' },
    { icon: 'mdi-moon-waning-crescent', text: 'Moons' },
    { icon: 'mdi-cookie', text: 'Asteroids' },
    { icon: 'mdi-magic-staff', text: 'Comets' },
    { icon: 'mdi-satellite-variant', text: 'Satelites' }
  ]
  const links4 = [
    { icon: 'mdi-camera', text: 'Imaging' },
    { icon: 'mdi-format-vertical-align-top', text: 'Leveling' },
    { icon: 'mdi-set-split', text: 'Calibration' },
    { icon: 'mdi-chart-bell-curve-cumulative', text: 'Telemetry' },
    { icon: 'mdi-stethoscope', text: 'Diagnostics' }
  ]
  const buttons1 = [
    { text: 'About' },
    { text: 'Copyright' },
    { text: 'Contact us' },
    { text: 'Contributors' },
    { text: 'Developers' }
  ]
  const buttons2 = [
    { text: 'Terms' },
    { text: 'Privacy' },
    { text: 'Policy & Safety' },
  ]


</script>

<style lang="sass">
.YL

  &__toolbar-input-container
    min-width: 100px
    width: 55%

  &__toolbar-input-btn
    border-radius: 0
    border-style: solid
    border-width: 1px 1px 1px 0
    border-color: rgba(0,0,0,.24)
    max-width: 60px
    width: 100%

  &__drawer-footer-link
    color: inherit
    text-decoration: none
    font-weight: 500
    font-size: .75rem

    &:hover
      color: #000
</style>