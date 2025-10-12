<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Pilot Catalog
        <div class="text-caption text-grey-6">
        Interactive Catalog of Stellar and Deep-Sky Objects.
       </div>
      </div>
      <q-space />
          <div>
            <q-btn dense v-if="cat.isFiltered" color="primary" icon="mdi-filter-off" 
                         :label="$q.screen.gt.sm ? 'Filters' : ''" @click="cat.clearFilter()" />
            <q-btn dense v-else icon="mdi-filter" 
                         :label="$q.screen.gt.sm ? 'Filters' : ''" @click="showFilters=!showFilters">
            </q-btn>
          </div>
          <div>
            <q-pagination v-if="$q.screen.gt.xs" v-model="cat.page" :max="cat.numPages" :max-pages="maxPages" direction-links
              icon-first="skip_previous" icon-last="skip_next" icon-prev="fast_rewind" icon-next="fast_forward"
            />
            <div v-else>
              <q-btn dense flat color="primary" icon="fast_rewind" @click="cat.page = Math.max(1, cat.page - 1)" />
              <q-btn dense color="primary" :label="cat.page" style="min-width:30px"/>
              <q-btn dense flat color="primary" icon="fast_forward" @click="cat.page = Math.min(cat.numPages, cat.page + 1)" />
            </div>
          </div>
  </div>
    <div v-if="showFilters" class="row q-pb-sm " style="background-color:rgba(255, 255, 255, 0.07);">
      <MultiSelect label="Rating" v-model="cat.filter['Rt']" :options="cat.RtOptions" color="accent"/>
      <MultiSelect label="Altitude" v-model="cat.filter['Alt']" :options="cat.AltOptions" color="positive"/>
      <MultiSelect label="Type" v-model="cat.filter['C1']" :options="cat.C1Options" color="grey-7"/>
      <MultiSelect label="SubType" v-model="cat.filter['C2']" :options="cat.C2Options" color="grey-7"/>
      <MultiSelect label="Size" v-model="cat.filter['Sz']" :options="cat.SzOptions" color="primary"/>
      <MultiSelect label="Brightness" v-model="cat.filter['Vz']" :options="cat.VzOptions" color="primary"/>
    </div>
    <div class="row q-pb-sm q-col-gutter-md items-center">

    </div>
    <!-- Page Body -->
    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-12">
        <q-card flat bordered class="col">
          <q-list bordered separator>
            <q-item v-if="cat.paginated.length==0" class="q-pt-lg q-pb-lg">
              <q-item-section avatar><q-icon name="mdi-help" /></q-item-section>
              <q-item-section>
                <q-item-label>No Results Found</q-item-label>
                <q-item-label caption>Clear the search and filters to try again</q-item-label>
              </q-item-section>
              <q-item-section side>
                  <q-btn flat dense icon="mdi-close" label="Clear" class="position-right" @click="cat.clearFilter()"/>
              </q-item-section>
            </q-item>
            <q-item v-else clickable v-for="dso in cat.paginated" v-bind:key="dso.MainID" @click="onClickDSO(dso)">
              <q-item-section avatar>
                <q-icon :name="typeLookupIcon[dso.C1]" />
              </q-item-section>
              <q-item-section top>
                <q-item-label>
                  <span class="text-weight-bolder">{{dso.MainID}}</span>
                  <span v-if="dso.OtherIDs" class="text-grey-7"> &nbsp;&nbsp;|&nbsp;&nbsp; {{ dso.OtherIDs }}</span>
                </q-item-label>
                <q-item-label overline>{{ dso.Name }} </q-item-label>
                <q-item-label caption class="text-grey-6"> 
                  {{dso.Subtype}} in {{ dso.Constellation }}. {{ dso.Notes }} 
                </q-item-label>
                <q-item-label caption class="text-grey-6">
                  <span v-if="dso.Class">Class: {{ dso.Class }}<VBar /></span>
                  RA: {{ deg2fulldms(dso.RA_hr,1,'hr') }} <VBar /> Dec: {{ deg2fulldms(dso.Dec_deg) }}
                  <span v-if="dso.Az_deg"> <VBar /> Az: {{ formatAngle(dso.Az_deg,'deg',0) }}</span>
                  <span v-if="dso.Alt_deg"> <VBar /> Altitude: {{ formatAngle(dso.Alt_deg,'deg',0) }}</span>
                </q-item-label>
              </q-item-section>

              <q-item-section top side class="q-gutter-xs">
                  <q-item-label caption></q-item-label>
                  <q-chip dense color="accent" class="text-caption">{{ dso.Rating }}</q-chip>
                  <q-chip v-if="!(dso.Vz==7 && dso.Sz==8)" dense color="primary" class="text-caption">{{ dso.Visibility }}</q-chip>
                  <q-chip v-if="dso.Position" dense :color="altLookupColor[dso.Alt??2]" class="text-caption">{{ dso.Position }}</q-chip>
              </q-item-section>
              <q-item-section side class="q-gutter-xs">
                <div class="column text-grey-8 q-gutter-xs">
                  <q-btn class="gt-xs" flat dense icon="mdi-move-resize-variant" @click.stop="onClickGoto(dso)">
                    <q-tooltip>Goto</q-tooltip>
                  </q-btn>
                  <q-btn class="gt-xs" flat dense icon="mdi-sync" @click.stop="onClickSync(dso)">
                    <q-tooltip>Sync</q-tooltip>
                  </q-btn>
                </div>
              </q-item-section>

            </q-item>
          </q-list>
        </q-card>
      </div>    
  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { deg2fulldms } from 'src/utils/angles'
import { useCatalogStore } from 'src/stores/catalog'
import MultiSelect from 'src/components/MultiSelect.vue'
import { useQuasar } from 'quasar'
import { useRoute, useRouter } from 'vue-router'
import type { DsoType, DsoSubtype, CatalogItem, DsoAltitude } from 'src/stores/catalog' // adjust path as needed
import { useDeviceStore } from 'src/stores/device'
import VBar from 'src/components/VBar.vue'
import { formatAngle } from 'src/utils/scale'



const cat = useCatalogStore()
const $q = useQuasar()
const route = useRoute()
const dev = useDeviceStore()
const router = useRouter()

const showFilters = ref<boolean>(false)


// function fmt(x:number|undefined, unit:UnitKey="deg"): string {
//   const s = deg2dms(x ?? 0, 1, unit)
//   return `${s.sign}${s.degreestr}${s.minutestr}${s.secondstr}`
// }


// ---------- Computed

const maxPages = computed(() => $q.screen.gt.sm ? 9 : 4)

// ---------- Watches
watch(() => route.query.q, (newQ) => {
    cat.searchFor = typeof newQ === 'string' ? newQ.trim() : ''
  },
  { immediate: true }
)
watch(() => route.query, syncFiltersFromRoute, { deep: true })


// ---------- Helpers
const typeLookupIcon: Record<DsoType, string>  = {
  0: 'mdi-horse-variant', 
  1: 'mdi-cryengine', 
  2: 'mdi-blur', 
  3: 'mdi-flare'
}

const altLookupColor: Record<DsoAltitude, string>  = {
  0: 'negative', 
  1: 'warning', 
  2: 'positive', 
  3: 'positive', 
  4: 'positive', 
  5: 'positive', 
  6: 'negative'
}

function parseNumberArray(param: unknown): number[] {
  if (typeof param === 'string') {
    return param
      .split(',')
      .map(s => parseInt(s))
      .filter(n => !isNaN(n))
  }
  return []
}

function syncFiltersFromRoute() {
  cat.filter.C1 = parseNumberArray(route.query.C1) as DsoType[]
  cat.filter.C2 = parseNumberArray(route.query.C2) as DsoSubtype[]
}


function onClickDSO(dso: CatalogItem) {
    $q.notify({
    message: `Ready to sync or goto ${dso.MainID} ${dso.Name ? dso.Name : ''}?`,
    color: 'warning', position: 'top', timeout: 5000,
    actions: [
      { label: 'Sync', icon: 'mdi-sync', color: 'yellow', handler: () => { void onClickSync(dso)} },
      { label: 'Goto', icon: 'mdi-move-resize-variant', color: 'yellow', handler: () => {void onClickGoto(dso)} },
      { label: 'Cancel', icon: 'mdi-close', color: 'white', handler: () => { /* ... */ } }
    ]
  })

}

async function onClickSync(dso: CatalogItem) {
  await dev.alpacaSyncToRADec(dso.RA_hr, dso.Dec_deg)
  $q.notify({ message:`Sync issued for ${dso.MainID} ${dso.Name}.`, icon:typeLookupIcon[dso.C1],
  type: 'positive', position: 'top', timeout: 5000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  cat.dsoGotoed = dso
  await router.push({ path: '/sync', query: { ...route.query, q: cat.searchFor } }) 

}


async function onClickGoto(dso: CatalogItem) {
  await dev.alpacaSlewToCoord(dso.RA_hr, dso.Dec_deg)
  $q.notify({ message:`Goto issued for ${dso.MainID} ${dso.Name}.`, icon:typeLookupIcon[dso.C1],
  type: 'positive', position: 'top', timeout: 5000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  cat.dsoGotoed = dso
  await router.push({ path: '/', query: { ...route.query, q: cat.searchFor } }) 

}

// ---------- Lifecycle Events

onMounted(async () => {
    await cat.catalogFetch()
    syncFiltersFromRoute()
    cat.startPositionUpdater();
})

onUnmounted(() => {
    cat.stopPositionUpdater();
})


</script>

<style lang="scss">
  .q-markdown--link {
    color: $grey-6;

    &:hover {
      text-decoration: underline;
      color: $grey-4;
    }
  }
</style>