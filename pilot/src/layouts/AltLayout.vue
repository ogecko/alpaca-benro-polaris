<template>
  <q-layout view="hHh LpR fFf" class="dark-page">
    <q-header elevated class="q-py-xs" height-hint="58">
      <q-toolbar>
        <q-btn flat dense round
          @click="toggleLeftDrawer"
          aria-label="Menu"
          icon="menu"
        />

        <q-btn flat no-caps no-wrap class="q-ml-xs" to="/" v-if="$q.screen.gt.xs">
          <q-toolbar-title shrink class="text-weight-bold">
            Alpaca Pilot
          </q-toolbar-title>
        </q-btn>

        <q-space />

        <div class="YL__toolbar-input-container row no-wrap">
          <q-input dense outlined square v-model="search" placeholder="Search" class="bg-blue-9 col" />
          <q-btn class="YL__toolbar-input-btn" color="grey-4" text-color="grey-8" icon="search" unelevated />
        </div>

        <q-space />

        <div class="q-gutter-sm row items-center no-wrap">
            <div>
                <span>70%</span>
                <q-icon size="sm" name="battery_4_bar" />
                <q-tooltip>Polaris Battery Level</q-tooltip>
            </div>
            <q-btn round dense flat  icon="notifications">
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

<script lang="ts">
import { ref } from 'vue'
import { fabYoutube } from '@quasar/extras/fontawesome-v6'

export default {
  name: 'MyLayout',

  setup () {
    const leftDrawerOpen = ref(false)
    const search = ref('')

    function toggleLeftDrawer () {
      leftDrawerOpen.value = !leftDrawerOpen.value
    }

    return {
      fabYoutube,

      leftDrawerOpen,
      search,

      toggleLeftDrawer,

      links1: [
        { icon: 'home', text: 'Home', to: '/' },
        { icon: 'power', text: 'Connections', to: '/connect' },
        { icon: 'settings', text: 'Settings', to: '/settings' },
      ],
      links2: [
        { icon: 'flare', text: 'Stars' },
        { icon: 'whatshot', text: 'Nebulae' },
        { icon: 'album', text: 'Galaxies' },
        { icon: 'blur_on', text: 'Clusters' },
      ],
      links3: [
        { icon: 'motion_photos_on', text: 'Planets' },
        { icon: 'brightness_2', text: 'Moons' },
        { icon: 'hdr_strong', text: 'Asteroids' },
        { icon: 'egg', text: 'Comets' },
        { icon: 'satellite_alt', text: 'Satelites' }
      ],
      links4: [
        { icon: 'camera', text: 'Imaging' },
        { icon: 'vertical_align_top', text: 'Leveling' },
        { icon: 'ads_click', text: 'Calibration' },
        { icon: 'flag', text: 'Telemetry' },
        { icon: 'analytics', text: 'Diagnostics' }
      ],
      buttons1: [
        { text: 'About' },
        { text: 'Copyright' },
        { text: 'Contact us' },
        { text: 'Contributors' },
        { text: 'Developers' }
      ],
      buttons2: [
        { text: 'Terms' },
        { text: 'Privacy' },
        { text: 'Policy & Safety' },

      ]
    }
  }
}
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