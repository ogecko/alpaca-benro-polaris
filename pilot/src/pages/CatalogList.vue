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
            <template v-if="cat.page === 1" >
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
            </template>
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
                <q-item-label overline v-if="dso.Name && dso.Name !== dso.MainID">{{ dso.Name }} </q-item-label>
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
                  <q-btn v-if="!isDeletableItem(dso)" class="gt-xs" flat dense icon="mdi-sync" @click.stop="onClickSync(dso)">
                    <q-tooltip>Sync</q-tooltip>
                  </q-btn>
                  <q-btn v-if="isDeletableItem(dso)" class="gt-xs" flat dense color="negative" icon="mdi-delete-outline" @click.stop="onClickRemoveOrbital(dso)">
                    <q-tooltip>Remove from orbital cache</q-tooltip>
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
import { useRoute, useRouter, onBeforeRouteUpdate } from 'vue-router'
import type { DsoType, DsoSubtype, CatalogItem, DsoAltitude, DsoConstellation, DsoRating, DsoSize, DsoBrightness } from 'src/stores/catalog' // adjust path as needed
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'
import { useCatalogStore, typeLookupIcon, typeLookup } from 'src/stores/catalog'
import { useConfigStore } from 'src/stores/config'
import { useUIStore } from 'src/stores/ui'
import VBar from 'src/components/VBar.vue'
import MultiSelect from 'src/components/MultiSelect.vue'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const dev = useDeviceStore()
const cat = useCatalogStore()
const cfg = useConfigStore()
const p = useStatusStore()
const ui = useUIStore()
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

function nowISOString(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
}


// ---------- Computed

const maxPages = computed(() => $q.screen.gt.sm ? 9 : 4)
const sorted_str = computed(() => isProxSort.value ?  'Nearby Proximity' : 'Ranking and Size' )
const isProxSort = computed(() => cat.sorting[0]?.field === 'Proximity')
const isNoResults = computed(() => cat.paginated.length == 0 && !cat.filter.C1?.some(c => [6,7,8,11].includes(c)))
const isNoradSearch = computed(() => check(cat.searchFor, [noradRegex]) || cat.filter.C1?.includes(6))
const isCometSearch = computed(() => check(cat.searchFor, [cometRegex]) || cat.filter.C1?.includes(7))
const isAsteroidSearch = computed(() => check(cat.searchFor, [namedRegex, numberedRegex, provisionalRegex]) || cat.filter.C1?.includes(8))
const isDeletableItem = (dso:CatalogItem) => (dso.Cn === 84 && dso.C1 >= 6)
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
    C1: 7 as DsoType, icon: typeLookupIcon[7], title: 'International Meteor Organisation',
    caption: 'Meteor Shower Calendar, a comprehensive list of meteor showers for the current year (external site). Copy the Meteor Shower Radiant hh:mm ±dd° into the Dashboards Right Ascension (hh:mm) and Declination (±dd) setpoints.',
    href: `https://www.imo.net/resources/calendar/`,
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
  {
    C1: 11 as DsoType, icon: "mdi-weather-sunny", title: 'Sunrise & Sunset',
    caption: 'Time and Date - Sunrise, Sunset, and Twilight Periods. (external site).',
    href: `https://www.timeanddate.com/sun/@${cfg.site_latitude},${cfg.site_longitude}`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-moon-waning-crescent", title: 'Moonrise & Moonset',
    caption: 'Time and Date - Moonrise, Moonset, and Moon Phases. (external site).',
    href: `https://www.timeanddate.com/moon/@${cfg.site_latitude},${cfg.site_longitude}`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-theme-light-dark", title: 'Upcoming Eclipses',
    caption: 'Time and Date - Calendar of Solar and Lunar Eclipses. (external site).',
    href: `https://www.timeanddate.com/eclipse/in/@${cfg.site_latitude},${cfg.site_longitude}`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-weather-cloudy", title: 'Clear Outside',
    caption: '7-day hourly cloud & weather forecasts. Designed by astronomers for astronomers. (external site).',
    href: `https://clearoutside.com/forecast/${cfg.site_latitude}/${cfg.site_longitude}`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-weather-rainy", title: 'Ventusky',
    caption: '3-hour precipitation forecast, with excellent visualisation of other weather maps. (external site).',
    href: `https://www.ventusky.com/precipitation-map/3-hours#p=${cfg.site_latitude};${cfg.site_longitude};11`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-weather-windy", title: 'Windy',
    caption: 'Provides detailed, visual forecasts of wind, cloud cover, and weather. (external site).',
    href: `https://www.windy.com/?${cfg.site_latitude},${cfg.site_longitude},11`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-weather-night-partly-cloudy", title: 'Meteoblue',
    caption: 'Astronomoy Seeing Conditions and Predictions (external site).',
    href: `https://www.meteoblue.com/fr/meteo/outdoorsports/seeing/`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-lightbulb-on-outline", title: 'Light Polution',
    caption: 'Find the best dark sky locations for Astrophotography (external site).',
    href: `https://lightpollutionmap.app/?lat=${cfg.site_latitude}&lng=${cfg.site_longitude}&zoom=10`,
  },  
  {
    C1: 11 as DsoType, icon: "mdi-image-filter-hdr", title: 'Peak Finder',
    caption: 'Identify a mountain peak that Polaris is pointing toward and determine its elevation (external site).',
    href: `https://www.peakfinder.com/fr/?lat=${cfg.site_latitude}&lng=${cfg.site_longitude}&ele=${cfg.site_elevation}&azi=${p.azimuth}&alt=-15&teleazi=${p.azimuth}&telealt=${p.altitude}&fov=110&date=${nowISOString()}&cfg=es&name=${cfg.location}`,
  },
  {
    C1: 11 as DsoType, icon: "mdi-aurora", title: 'Space Weather Prediction Center',
    caption: 'Aurora Dashboard predicts when and where you can see the northern and sothern lights (external site).',
    href: `https://www.swpc.noaa.gov/communities/aurora-dashboard-experimental`,
  },

])


// ---------- Watches
watch(() => route.query.q, (newQ) => {
    cat.searchFor = typeof newQ === 'string' ? newQ.trim() : ''
  },
  { immediate: true }
)

watch(() => cat.filter, (f) => {
  ui.setCatalogFilter(f)
}, { deep: true })

watch(isProxSort, (isProx) => {
  ui.setCatalogSort(isProx ? 'Proximity' : '')
})

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

const FILTER_KEYS = ['C1', 'C2', 'Cn', 'Rt', 'Sz', 'Vz', 'Az', 'Alt'] as const

function syncFiltersFromRoute(query = route.query) {
  const hasExplicitFilter = FILTER_KEYS.some(k => k in query) || 'sort' in query
  const source = hasExplicitFilter
    ? {
        C1: parseNumberArray(query.C1),
        C2: parseNumberArray(query.C2),
        Cn: parseNumberArray(query.Cn),
        Rt: parseNumberArray(query.Rt),
        Sz: parseNumberArray(query.Sz),
        Vz: parseNumberArray(query.Vz),
        Az: parseNumberArray(query.Az),
        Alt: parseNumberArray(query.Alt),
      }
    : {
        C1: ui.catalogFilter.C1 ?? [],
        C2: ui.catalogFilter.C2 ?? [],
        Cn: ui.catalogFilter.Cn ?? [],
        Rt: ui.catalogFilter.Rt ?? [],
        Sz: ui.catalogFilter.Sz ?? [],
        Vz: ui.catalogFilter.Vz ?? [],
        Az: ui.catalogFilter.Az ?? [],
        Alt: ui.catalogFilter.Alt ?? [],
      }
  cat.filter.C1 = source.C1 as DsoType[]
  cat.filter.C2 = source.C2 as DsoSubtype[]
  cat.filter.Cn = source.Cn as DsoConstellation[]
  cat.filter.Rt = source.Rt as DsoRating[]
  cat.filter.Sz = source.Sz as DsoSize[]
  cat.filter.Vz = source.Vz as DsoBrightness[]
  cat.filter.Az = source.Az as DsoAltitude[]
  cat.filter.Alt = source.Alt as DsoAltitude[]

  const sortProximityWanted = hasExplicitFilter ? query.sort === 'Proximity' : ui.catalogSort === 'Proximity'
  if (sortProximityWanted) {
    cat.updateDsoProximity(p.rightascension, p.declination)
    cat.sorting = [{ field: 'Proximity', direction: 'asc' }]
  } else {
    cat.sorting = []
  }
}

function onClickDSO(dso: CatalogItem) {
  const actions = [
    { label: 'Sync', icon: 'mdi-sync', color: 'yellow', handler: () => { void onClickSync(dso) } },
    { label: 'Goto', icon: 'mdi-move-resize-variant', color: 'yellow', handler: () => { void onClickGoto(dso) } },
    { label: 'Cancel', icon: 'mdi-close', color: 'white', handler: () => {} },
  ]
  if (isDeletableItem(dso)) {
    actions.splice(-1, 0, { label: 'Remove', icon: 'mdi-delete-outline', color: 'yellow', handler: () => { void onClickRemoveOrbital(dso) }  })
  }
  $q.notify({
    message: `Ready to sync or goto ${dso.MainID}?`,
    color: 'warning', position: 'top', timeout: 5000,
    actions
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
    await dev.alpacaTrackOrbital(dso.MainID, dso.C1)
  }
  else if (dso.C1==9) {
    await dev.alpacaSlewToAltAz(dso.Alt_deg ?? 180, dso.Az_deg ?? 45)
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


async function onClickRemoveOrbital(dso: CatalogItem) {
  await dev.alpacaRemoveOrbital(dso.MainID)
  // Remove from local dsos immediately so UI updates without refresh
  cat.dsos = cat.dsos.filter(d => d.MainID !== dso.MainID)
  $q.notify({ message: `Removed ${dso.MainID} from orbital cache.`, 
    icon: 'mdi-delete-outline', type: 'negative', position: 'top', timeout: 3000,
    actions: [{ icon: 'mdi-close', color: 'white' }] })
}


async function onClickSearchOrbital(c1:DsoType=6) {
  const name = cat.searchFor
  const iconname = typeLookupIcon[c1]
  const typename = typeLookup[c1]
  await dev.alpacaTrackOrbital(name, c1)
  const notify = $q.notify({
    group: false, message:`${typename} search issued for "${name}".`, caption:'', icon:iconname,
    spinner: true, type: 'positive', position: 'top', timeout: 0, actions: [{ icon: 'mdi-close', color: 'white' }] 
  })
  setTimeout(() => {
    notify({
      caption: `${p.orbitalfetchmsg}`,
      spinner: false,  timeout: 5000
    })
  }, 1000)
  await router.push({ path: '/dashboard', query: { ...route.query, q: cat.searchFor } }) 
}

// ---------- Lifecycle Events

onMounted(async () => {
    await cat.catalogFetch()
    const shouldFetch =
      dev.restAPIConnected &&
      dev.restAPIConnectedAt &&
      cfg.fetchedAt < dev.restAPIConnectedAt

    if (shouldFetch) {
      await cfg.configFetch()
    }

    syncFiltersFromRoute()
    cat.startPositionUpdater();
})

onBeforeRouteUpdate((to, from, next) => {
  syncFiltersFromRoute(to.query)
  next()
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