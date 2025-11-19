<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Pilot Catalog
        <div class="text-caption text-grey-6">
        Interactive Catalog of Stellar and Deep-Sky Objects, sorted by {{ sorted_str }}.
       </div>
      </div>
      <q-space />
          <div>
            <q-btn dense v-if="showFilters && cat.isFiltered" color="primary" icon="mdi-filter-off" 
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
            <q-item v-if="isNoradSearch" class="q-pt-lg q-pb-lg">
              <q-item-section avatar><q-icon name="mdi-satellite-variant" /></q-item-section>
              <q-item-section>
                <q-item-label>Satellite NORAD ID?</q-item-label>
                <q-item-label caption>Search Celestrak for satellite data using a NORAD ID. If found, tracking will begin automatically.</q-item-label>
                <q-item-label caption>You can find NORAD IDs on external sites, then enter one into the field here.</q-item-label>
              </q-item-section>
              <q-item-section side>
                  <q-input v-model="cat.searchFor" icon="mdi-satellite-variant" label="NORAD ID" class="position-right"/>
              </q-item-section>
              <q-item-section side>
                  <q-btn color="positive" rounded  icon="mdi-satellite-variant" label="Search" class="position-right" @click="onClickSearchOrbital(6)"/>
              </q-item-section>
            </q-item>
            <q-item v-if="isCometSearch" class="q-pt-lg q-pb-lg">
              <q-item-section avatar><q-icon name="mdi-magic-staff" /></q-item-section>
              <q-item-section>
                <q-item-label>Comet ID?</q-item-label>
                <q-item-label caption>Search NASA JPL Horizons for comet data. If found, tracking will begin automatically.</q-item-label>
                <q-item-label caption>You can use long period (eg. C/2025 A6), short period (eg. P/2023 R1), or provisional IDs (eg. 2006 F8).</q-item-label>
              </q-item-section>
              <q-item-section side>
                  <q-input v-model="cat.searchFor" icon="mdi-magic-staff" label="Comet ID" class="position-right"/>
              </q-item-section>
              <q-item-section side>
                  <q-btn color="positive" rounded  icon="mdi-magic-staff" label="Search" class="position-right" @click="onClickSearchOrbital(7)"/>
              </q-item-section>
            </q-item>
            <q-item v-if="isAsteroidSearch" class="q-pt-lg q-pb-lg">
              <q-item-section avatar><q-icon name="mdi-cookie" /></q-item-section>
              <q-item-section>
                <q-item-label>Asteroid ID?</q-item-label>
                <q-item-label caption>Search NASA JPL Horizons for asteriod data. If found, tracking will begin automatically.</q-item-label>
                <q-item-label caption>You can use named asteriods (eg. Ceres), numbered asteriods (eg. 00433), or provisional IDs (eg. 2023 BU).</q-item-label>
              </q-item-section>
              <q-item-section side>
                  <q-input v-model="cat.searchFor" icon="mdi-cookie" label="Asteroid ID" class="position-right"/>
              </q-item-section>
              <q-item-section side>
                  <q-btn color="positive" rounded  icon="mdi-cookie" label="Search" class="position-right" @click="onClickSearchOrbital(8)"/>
              </q-item-section>
            </q-item>
              <q-item v-for="(link, index) in filteredLinks" :key="index" class="q-pt-lg q-pb-lg" >
                <q-item-section avatar><q-icon :name="link.icon" /></q-item-section>
                <q-item-section>
                  <q-item-label>{{ link.title }}</q-item-label>
                  <q-item-label caption>{{ link.caption }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                    <q-btn flat dense icon="mdi-open-in-new" label="Open Site" class="position-right" :href="link.href"  target="_blank" rel="noopener" />
                </q-item-section>
              </q-item>
            <q-item v-if="isNoResults" class="q-pt-lg q-pb-lg">
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
                  <span v-if="isProxSort"> <VBar /> Proximity: {{ formatAngle(dso.Proximity??0,'deg',1) }}</span>
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
import { formatAngle } from 'src/utils/scale'
import { useQuasar } from 'quasar'
import { useRoute, useRouter } from 'vue-router'
import type { DsoType, DsoSubtype, CatalogItem, DsoAltitude, DsoConstellation, DsoRating, DsoSize, DsoBrightness } from 'src/stores/catalog' // adjust path as needed
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'
import { useCatalogStore, typeLookupIcon, typeLookup } from 'src/stores/catalog'
import VBar from 'src/components/VBar.vue'
import MultiSelect from 'src/components/MultiSelect.vue'
import { useConfigStore } from 'src/stores/config'


const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const dev = useDeviceStore()
const cat = useCatalogStore()
const cfg = useConfigStore()
const p = useStatusStore()

const showFilters = ref<boolean>(false)


// function fmt(x:number|undefined, unit:UnitKey="deg"): string {
//   const s = deg2dms(x ?? 0, 1, unit)
//   return `${s.sign}${s.degreestr}${s.minutestr}${s.secondstr}`
// }

// Satellites: NORAD ID's
const noradRegex = /^\d{1,6}$/

// Comets: short or long period, or provisional 
const cometRegex = /^(C|P)?\/?\d{4} [A-Z][0-9]+$/i

// Named asteroids: single word, starts with uppercase, no digits
const namedRegex = /^[A-Z][a-zA-Z]+$/

// Numbered asteroids: 3–6 digits, optionally zero-padded
const numberedRegex = /^\d{3,6}$/

// Provisional designations:
// - Format: YYYY XX## (e.g., "2023 BU", "2021 PH27", "2022 AE1")
// - Format: A### XX (e.g., "A801 AA")
const provisionalRegex = /^(\d{4} [A-Z]{1,2}\d{0,2}|A\d{3} [A-Z]{2})$/i

// check whether the query string matches any of the regex's
function check(query: string, criteria: RegExp[]): boolean {
  return criteria.some(regex => regex.test(query.trim()))
}




// ---------- Computed

const maxPages = computed(() => $q.screen.gt.sm ? 9 : 4)
const sorted_str = computed(() => isProxSort.value ?  'Nearby Proximity' : 'Ranking and Size' )
const isProxSort = computed(() => cat.sorting[0]?.field === 'Proximity')
const isNoResults = computed(() => cat.paginated.length == 0 && !cat.filter.C1?.some(c => [6,7,8].includes(c)))
const isNoradSearch = computed(() => check(cat.searchFor, [noradRegex]) || cat.filter.C1?.includes(6))
const isCometSearch = computed(() => check(cat.searchFor, [cometRegex]) || cat.filter.C1?.includes(7))
const isAsteroidSearch = computed(() => check(cat.searchFor, [namedRegex, numberedRegex, provisionalRegex]) || cat.filter.C1?.includes(8))
const filteredLinks = computed(() => allLinks.value.filter(link => cat.filter.C1?.includes(link.C1)))
const allLinks = computed(() => [
  {
    C1: 6 as DsoType, icon: typeLookupIcon[6], title: 'Nearby Satellites',
    caption: 'View satellites currently visible from your location using Heavens-Above.com (external site).',
    href: `https://www.heavens-above.com/skyview/?lat=${cfg.site_latitude}&lng=${cfg.site_longitude}&cul=en#/livesky`,
  },
  {
    C1: 6 as DsoType, icon: typeLookupIcon[6], title: 'Brightest Satellites',
    caption: 'Explore satellites ranked by brightness (apparent magnitude) on N2YO.com (external site).',
    href: `https://www.n2yo.com/satellites/?c=1&srt=4&dir=1&p=0`,
  },
  {
    C1: 6 as DsoType, icon: typeLookupIcon[6], title: 'Global Satellites',
    caption: 'View real-time positions of the brightest satellites around the globe on satellitemap.space (external site).',
    href: `https://satellitemap.space/`,
  },
  {
    C1: 6 as DsoType, icon: typeLookupIcon[6], title: 'Celestrak',
    caption: 'Official site used by Alpaca Pilot to search for Satellite orbital data (external site).',
    href: `https://celestrak.org/NORAD/elements/`,
  },
  {
    C1: 7 as DsoType, icon: typeLookupIcon[7], title: 'Nearby Comets',
    caption: 'View comets currently visible from your location using TheSkyLive.com (external site).',
    href: `https://theskylive.com/comets`,
  },
  {
    C1: 7 as DsoType, icon: typeLookupIcon[7], title: 'Sky Tonight',
    caption: 'Displays comet positions relative to stars and constellations using Sky-Tonight.com (external site).',
    href: `https://sky-tonight.com/comets`,
  },
  {
    C1: 7 as DsoType, icon: typeLookupIcon[7], title: 'Astro Forum',
    caption: 'Shows a live planetarium with visible comets using AstroForumSpace.com (external site).',
    href: `https://astroforumspace.com/real-time-sky-live-planets-comets-finder/`,
  },
  {
    C1: 7 as DsoType, icon: typeLookupIcon[7], title: 'Comet Observation Database',
    caption: 'Open clearing house for comet observations at cobs.si (external site).',
    href: `https://cobs.si/`,
  },
  {
    C1: 8 as DsoType, icon: typeLookupIcon[8], title: 'Eyes on Asteriods',
    caption: 'Real-time visualization of every known Near-Earth Object (NEO) using jpl.nasa.gov (external site).',
    href: `https://eyes.nasa.gov/apps/asteroids/#/watch`,
  },
  {
    C1: 8 as DsoType, icon: typeLookupIcon[8], title: 'Near Earth Objects',
    caption: 'View NEOs currently visible from your location using TheSkyLive.com (external site).',
    href: `https://theskylive.com/near-earth-objects`,
  },
  {
    C1: 8 as DsoType, icon: typeLookupIcon[8], title: 'Minor Planet Center',
    caption: 'Clearinghouse for Near Earth Objects using MinorPlanetCenter.net (external site).',
    href: `https://minorplanetcenter.net/data`,
  },
  {
    C1: 8 as DsoType, icon: typeLookupIcon[8], title: 'JPL Horizons',
    caption: 'Official site used by Alpaca Pilot for Comet and Asteroid orbital data (external site).',
    href: `https://ssd.jpl.nasa.gov/horizons/`,
  },

])


// ---------- Watches
watch(() => route.query.q, (newQ) => {
    cat.searchFor = typeof newQ === 'string' ? newQ.trim() : ''
  },
  { immediate: true }
)


// watch(() => route.query, syncFiltersFromRoute, { deep: true })
watch(() => route.query, syncFiltersFromRoute, { deep: true, flush: 'sync' });


// ---------- Helpers
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
  cat.filter.Cn = parseNumberArray(route.query.Cn) as DsoConstellation[]
  cat.filter.Rt = parseNumberArray(route.query.Rt) as DsoRating[]
  cat.filter.Sz = parseNumberArray(route.query.Sz) as DsoSize[]
  cat.filter.Vz = parseNumberArray(route.query.Vz) as DsoBrightness[]
  cat.filter.Az = parseNumberArray(route.query.Az) as DsoAltitude[]
  cat.filter.Alt = parseNumberArray(route.query.Alt) as DsoAltitude[]

  if (route.query.sort === 'Proximity') {
    cat.updateDsoProximity(p.rightascension, p.declination);
    cat.sorting = [{ field: 'Proximity', direction: 'asc' }];
  } else {
    cat.sorting = [];
  }
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
  await dev.alpacaJ2000Sync(dso.RA_hr, dso.Dec_deg)
  const name = dso.Name?.trim() || '';
  $q.notify({ message:`Sync issued for ${dso.MainID} ${name}.`, icon:typeLookupIcon[dso.C1],
  type: 'positive', position: 'top', timeout: 5000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  cat.dsoGotoed = dso
  await router.push({ path: '/sync', query: { ...route.query, q: cat.searchFor } }) 

}


async function onClickGoto(dso: CatalogItem) {
  if (dso.Cn==84) {
    await dev.alpacaTrackOrbital(dso.MainID)
  }
  else {
    await dev.alpacaJ2000Goto(dso.MainID, dso.RA_hr, dso.Dec_deg)
  }
  const name = dso.Name?.trim() || '';
  $q.notify({ message:`Goto issued for ${dso.MainID} ${name}.`, icon:typeLookupIcon[dso.C1],
  type: 'positive', position: 'top', timeout: 5000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  cat.dsoGotoed = dso
  await router.push({ path: '/dashboard', query: { ...route.query, q: cat.searchFor } }) 
}

async function onClickSearchOrbital(c1:DsoType=6) {
  const name = cat.searchFor
  const iconname = typeLookupIcon[c1]
  const typename = typeLookup[c1]
  await dev.alpacaTrackOrbital(name)
  $q.notify({ message:`${typename} search issued for ${name}.`, icon:iconname,
  type: 'positive', position: 'top', timeout: 5000, actions: [{ icon: 'mdi-close', color: 'white' }] })
  await router.push({ path: '/dashboard', query: { ...route.query, q: cat.searchFor } }) 
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