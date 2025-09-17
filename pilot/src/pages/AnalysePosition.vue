<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Driver Performance Analysis
        <div class="text-caption text-grey-6">
        Use these pages to perform tests and analyse the performance of your Benro Polaris. 
       </div>
      </div>
      <q-space />
    </div>

    <!-- Page Body -->
    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-12 flex">
        <q-card flat bordered class="col q-pa-md">
          <div class="row">
            <!-- KF intro -->
            <div class="col-md-6">
  <q-markdown  :no-mark="false">
  # Position Analysis
  This page shows the current orientation parameters of the Benro Polaris.
  </q-markdown>
            </div>
          </div>
        </q-card>
      </div>
      <div class="col-12 flex">
        <q-card flat bordered class="col">
          <div class="q-pa-md">
              <q-table title="Current Mount Orientation" 
                    :selected-rows-label="getSelectedString" :pagination="initialPagination"
      selection="multiple"
      v-model:selected="selected"

                :rows="rows" :columns="columns" row-key="name">
              </q-table>
          </div>
        </q-card>
      </div>    
  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { deg2dms } from 'src/utils/angles'
import { useStatusStore } from 'src/stores/status'
import type { UnitKey } from 'src/utils/angles'

const p = useStatusStore()
const selected = ref([])
const axis = ref<number>(0)


watch(axis, ()=>selected.value=[])

function fmt(x:number|undefined, unit:UnitKey="deg"): string {
  const s = deg2dms(x ?? 0, 1, unit)
  return `${s.sign}${s.degreestr}${s.minutestr}${s.secondstr}`
}

type TableRow = {
  q:string, name:string, az:string, alt:string, roll:string, ra:string, dec:string, pa:string, 
}

onMounted(() => {
})

onUnmounted(() => {
})


type AlignType = 'left' | 'center' | 'right'

const columns = [
  { name: 'name', label: 'Position Variable', field: 'name', sortable: true, align: 'left' as AlignType, required: true },
  { name: 'q', label: 'Quaternion',  field: 'q', sortable: true, align: 'center' as AlignType,  },
  { name: 'az', label: 'Azimuth',  field: 'az', sortable: true, align: 'center' as AlignType,  },
  { name: 'alt', label: 'Altitude',  field: 'alt', sortable: true, align: 'center' as AlignType,  },
  { name: 'roll', label: 'Roll', field: 'roll', sortable: true, align: 'center' as AlignType, },
  { name: 'ra', label: 'RA',  field: 'ra', sortable: true, align: 'center' as AlignType,  },
  { name: 'dec', label: 'Dec',  field: 'dec', sortable: true, align: 'center' as AlignType,  },
  { name: 'pa', label: 'PA', field: 'pa', sortable: true, align: 'center' as AlignType, },
  ]

const rows = computed<TableRow[]>(() => {
  return [
  { name:'Polaris: q1', q:p.q1, az:'', alt:'', roll:'', ra:'', dec:'', pa:''},
  { name:'KF: Theta State (Motor Positions)', q:'', az:fmt(p.thetastate[0]), alt:fmt(p.thetastate[1]), roll:fmt(p.thetastate[2]), ra:'', dec:'', pa:'',},
  { name:'KF: q1s (derived from Theta)', q:p.q1s, az:'', alt:'', roll:'', ra:'', dec:'', pa:''},
  { name:'PID: Delta Ref (Body RADEC)', q:'', az:'', alt:'', roll:'', ra:fmt((p.deltaref[0]??0)/180*12, "hr"), dec:fmt(p.deltaref[1]), pa:fmt(p.deltaref[2])},
  { name:'PID: Alpha Ref (Body AzAlt)', q:'',  az:fmt(p.alpharef[0]), alt:fmt(p.alpharef[1]), roll:fmt(p.alpharef[2]), ra:'', dec:'', pa:'',},
  { name:'ASCOM: Orientation', q:'', az:fmt(p.azimuth), alt:fmt(p.altitude), roll:fmt(p.roll), ra:fmt(p.rightascension, "hr"), dec:fmt(p.declination), pa:fmt(p.rotation)},
  { name:'PID: Omega Ref (Motor Velocities)', q:'',  az:fmt(p.omegaref[0]), alt:fmt(p.omegaref[1]), roll:fmt(p.omegaref[2]), ra:'', dec:'', pa:'',},
  { name:'MC: Motor Ref (Motor Velocities)', q:'',  az:fmt(p.motorref[0]), alt:fmt(p.motorref[1]), roll:fmt(p.motorref[2]), ra:'', dec:'', pa:'',},

]
})

const initialPagination = {
        rowsPerPage: 30
      }


function getSelectedString () {
        return selected.value.length === 0 ? '' : `${selected.value.length} Test${selected.value.length > 1 ? 's' : ''} selected of ${rows.value.length}`
}

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