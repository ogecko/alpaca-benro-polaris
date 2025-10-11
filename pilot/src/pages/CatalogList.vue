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
    <q-pagination
      v-model="cat.page" :max="cat.numPages" :max-pages="5"
      direction-links 
      icon-first="skip_previous"
      icon-last="skip_next"
      icon-prev="fast_rewind"
      icon-next="fast_forward"
    />
    </div>
    <div class="row q-pb-sm ">
        <div class="row ">
          <MultiSelect label="Rating" v-model="cat.filter['Rt']" :options="cat.RtOptions" />
          <MultiSelect label="Type" v-model="cat.filter['C1']" :options="cat.C1Options" />
          <MultiSelect label="SubType" size="220px" v-model="cat.filter['C2']" :options="cat.C2Options" />
          <MultiSelect label="Visibility" size="220px" v-model="cat.filter['Vz']" :options="cat.VzOptions" />
          <MultiSelect label="Size" size="220px" v-model="cat.filter['Sz']" :options="cat.SzOptions" />
          <div class="col">
            <q-btn v-if="cat.isFiltered" color="primary" icon="mdi-filter-off" label="Filters" @click="cat.clearFilter()" />
            <q-btn v-else  icon="mdi-filter" label="Filters"  />
          </div>
        </div>


    </div>
    <div class="row q-pb-sm q-col-gutter-md items-center">

    </div>
    <!-- Page Body -->
    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-12">
        <q-card flat bordered class="col">
          <q-list bordered separator>
            <q-item clickable v-for="dso in cat.paginated" v-bind:key="dso.MainID">
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
              </q-item-section>

              <q-item-section top side class="q-gutter-xs">
                  <q-item-label caption></q-item-label>
                  <q-badge  color="accent">{{ dso.Rating }}</q-badge>
                  <q-badge  color="primary">{{ dso.Size }}</q-badge>
                  <q-badge v-if="dso.Vz!=7" color="primary">{{ dso.Visibility }}</q-badge>
                  <q-badge v-if="dso.Class" color="positive">{{ dso.Class }}</q-badge>
              </q-item-section>
              <q-item-section side class="q-gutter-xs">
                <div class="text-grey-8 q-gutter-xs">
                  <q-btn class="gt-xs" size="12px" flat dense icon="mdi-move-resize-variant" />
                </div>
              </q-item-section>

            </q-item>
          </q-list>
          <div class="q-pa-md">
          </div>
        </q-card>
      </div>    
  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted } from 'vue'
// import { deg2dms } from 'src/utils/angles'
// import { useStatusStore } from 'src/stores/status'
// import type { UnitKey } from 'src/utils/angles'
// import { useDeviceStore } from 'src/stores/device'
import { useCatalogStore } from 'src/stores/catalog'
import MultiSelect from 'src/components/MultiSelect.vue'


// const dev = useDeviceStore()
const cat = useCatalogStore()

// const p = useStatusStore()
// const showFilters = ref<boolean>(false)


// function fmt(x:number|undefined, unit:UnitKey="deg"): string {
//   const s = deg2dms(x ?? 0, 1, unit)
//   return `${s.sign}${s.degreestr}${s.minutestr}${s.secondstr}`
// }


// ---------- Computed





// ---------- Helpers
type DsoType = 0 | 1 | 2 | 3;

const typeLookupIcon: Record<DsoType, string>  = {
  0: 'mdi-horse-variant', 
  1: 'mdi-cryengine', 
  2: 'mdi-blur', 
  3: 'mdi-flare'
}



// ---------- Lifecycle Events

onMounted(async () => {
    await cat.catalogFetch()
})

onUnmounted(() => {
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