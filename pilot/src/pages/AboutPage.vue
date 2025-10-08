<template>
  <q-page>
    <!-- Header Row -->
    <div class="row q-pa-lg">
    </div>

    <div class="row q-col-gutter-sm items-stretch">
      <!----- Logo Startup Image ----->
      <div class="row col-12 items-center q-pa-xl">
          <div class="col">
            <q-img src="../assets/abp-logo.png" fit="scale-down" position="100% 50%" style="height:200px"></q-img>
          </div>
          <div class="col">
            <div class="text-bold text-h4">
              <div>PRECISION</div>
              <div>CONTROL</div>
              <div>REIMAGINED</div>
            </div>
            <div class="q-pt-lg text-primary text-subtitle1">
              <div>Slewing, Rotating, Targeting,</div>
              <div>Tracking, and Guiding.</div>
            </div>
          </div>
      </div>

      <!-- Component Versions -->
      <div class="col-12 col-md-6 col-lg-4 flex">
        <div flat  class="q-pa-md full-width">
          <div class="text-h6">Component Versions</div>
          <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
              Software, firmware and hardware versions currently connected.
              </div>
          </div>
          <q-markup-table dense flat class="bg-grey-10">
            <thead>
              <tr><th class="text-left">Component</th><th class="text-left">Version</th></tr>
            </thead>
            <tr><td>Alpaca Pilot App</td><td>v2.0.0</td></tr>
            <tr><td>{{ dev.alpacaServerName }}</td><td>v{{ dev.alpacaServerVersion }}</td></tr>
            <tr><td>Benro Polaris Firmware</td><td>v{{ p.polarisswver }}</td></tr>
            <tr><td>Benro Polaris Hardware</td><td>v{{ p.polarishwver }}</td></tr>
          </q-markup-table>
        </div>
      </div>

      <!-- Kickstarter Recognition -->
      <div class="col-12 col-md-6 col-lg-4 flex">
        <div flat  class="q-pa-md full-width">
          <div class="text-h6">Kickstarter & Beta Recognition</div>
          <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
              Thanks to all Kickstarter backers and Beta testers, especially the following.
              </div>
          </div>
          <q-markup-table dense flat class="bg-grey-10">
            <thead>
              <tr><th class="text-left">Game Changer</th><th class="text-left">Beta Testers</th></tr>
            </thead>
            <tr><td>Mack Cameron</td><td>TBD</td></tr>
            <tr><td>Peter</td><td></td></tr>
            <tr><td>Simone Chiari</td><td></td></tr>
            <tr><td>Mark Bahu</td><td></td></tr>
            <tr><td>Richard Swaim</td><td></td></tr>
            <tr><td>William Siers</td><td></td></tr>
          </q-markup-table>
        </div>
      </div>

      <!-- Services Recognition -->
      <div class="col-12 col-md-6 col-lg-4 flex">
        <div flat  class="q-pa-md full-width">
          <div class="text-h6">Additional Recognition</div>
          <div class="row">
              <div class="col-12 text-caption text-grey-6 q-pb-md">
              Thanks to each of the following who made this possible.
              </div>
          </div>
          <q-markup-table dense flat class="bg-grey-10">
            <thead>
              <tr><th class="text-left">Company/Individual</th><th class="text-left">Web Services</th></tr>
            </thead>
            <tr><td>Benro (Polaris)</td><td>GitHub</td></tr>
            <tr><td>Stefan Berg (Nina)</td><td>Kickstarter</td></tr>
            <tr><td>Robert B. Denny (Alpaca)</td><td>Napkin AI</td></tr>
            <tr><td>Steven Byrnes (Seestar_alp)</td><td>Open AI</td></tr>
            <tr><td>Peter Simpson (ASCOM)</td><td>Grammarly</td></tr>
            <tr><td>ASCOM Initiative Members</td><td>Pictogrtammers</td></tr>
            <tr><td>Gary Imm (Catalog)</td><td>Stellarium</td></tr>
          </q-markup-table>
        </div>
      </div>


    </div>

</q-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useDeviceStore } from 'stores/device'
import { useStatusStore } from 'stores/status'

const dev = useDeviceStore()
const p = useStatusStore()


onMounted(() => {
})

onUnmounted(() => {
})


</script>
