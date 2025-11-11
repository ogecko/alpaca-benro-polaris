<template>
  <q-page>
    <!-- Header Row -->
    <div class="row q-pa-lg">
    </div>

    <div class="row q-col-gutter-sm items-stretch">
      <!----- Logo Startup Image ----->
      <div class="row col-12 items-center q-pa-lg">
        <div class="col flex flex-center" style="height: 300px; ">
          <q-img
            src="../assets/abp-v2-logo-hires-full.png"
            fit="scale-down"
            style="max-width: 100%; max-height: 100%;"
          />
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
            <tr><td>Alpaca Pilot App</td><td>v2.0 Beta5</td></tr>
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
            <tr><td>ADC</td><td>Validimir Vyskocil</td></tr>
            <tr><td>Bertolissio</td><td>Mark Long</td></tr>
            <tr><td>Billy Buchanan</td><td>Steve Everitt</td></tr>
            <tr><td>Alan Johnston</td><td>Alex Murdoch</td></tr>
            <tr><td>William Siers</td><td>Daniel Michaud</td></tr>
            <tr><td>Richard Swaim</td><td>Paul C</td></tr>
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
            <tr><td>Benro (Polaris), Ivy</td><td>GitHub</td></tr>
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
