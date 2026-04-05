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

        <q-card flat bordered class="col">
          <div class="row ">
            <div class="col-6">
              <q-timeline layout="comfortable" class="">
                <q-timeline-entry heading>Forward Kinematics</q-timeline-entry>
                <q-timeline-entry title="Polaris" >
                  <div class="text-grey-6 terminal">{{`q1:          ${p.q1}`}}</div>
                  <div class="text-grey-6 terminal">{{`motor_raw:   M1 ${fmt(p.zetameas[0])}   |   M2 ${fmt(p.zetameas[1])}   |   M3 ${fmt(p.zetameas[2])}`}}</div>
                  <div class="text-grey-6 terminal">{{`theta_raw:   t1 ${fmt(p.thetastate[0])}   |   t2 ${fmt(p.thetastate[1])}   |   t3 ${fmt(p.thetastate[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry v-if="cfg.advanced_kf" title="Kalman Filter" subtitle="Smooth" icon="mdi-chart-line">
                  <div class="text-grey-6 terminal">{{`theta_state: t1 ${fmt(p.thetastate[0])}   |   t2 ${fmt(p.thetastate[1])}   |   t3 ${fmt(p.thetastate[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Error Corrections" subtitle="Correct" icon="mdi-axis-x-rotate-clockwise">
                  <div v-if="cfg.advanced_pec" class="text-grey-6 terminal">PEC:</div>
                  <div v-if="cfg.advanced_align_roll" class="text-grey-6 terminal">{{`RBC: Roll Error = (0.9921 * tan(Alt) + 0.2323) * Roll  =  Adj ${fmt(p.thetastate[2])}`}}</div>
                  <div v-if="cfg.advanced_align_local" class="text-grey-6 terminal">LGC:</div>
                </q-timeline-entry>
                <q-timeline-entry v-if="cfg.advanced_alignment" title="Multi-Point Alignment" subtitle="align" icon="mdi-rotate-orbit">
                  <div class="text-grey-6 terminal">QUEST:</div>
                </q-timeline-entry>
                <q-timeline-entry title="Alpaca API" subtitle="serve" icon="mdi-rotate-orbit">
                  <div class="text-grey-6 terminal">{{`theta_pv:    t1 ${fmt(p.thetastate[0])}   |   t2 ${fmt(p.thetastate[1])}   |   t3 ${fmt(p.thetastate[2])}`}}</div>
                  <div class="text-grey-6 terminal">{{`alpha_pv:    Az ${fmt(p.azimuth)}   |  Alt ${fmt(p.altitude)}   | Roll ${fmt(p.roll)}`}}</div>
                  <div class="text-grey-6 terminal">{{`delta_pv:    RA ${fmt(p.rightascension,"hr")}   |  Dec ${fmt(p.declination)}   | PosA ${fmt(p.positionangle)}`}}</div>
                  <div class="text-grey-6 terminal">{{`ephem:       HA ${fmt(p.rightascension,"hr")}   |             Paralatic Angle ${fmt(p.positionangle)}`}}</div>
                  <div class="text-grey-6 terminal">{{`            LST ${fmt(p.rightascension,"hr")}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Sky" ></q-timeline-entry>
              </q-timeline>
            </div>
            <div class="col-6">
              <q-timeline layout="comfortable" class="q-pr-xl">
                <q-timeline-entry heading>Inverse Kinematics</q-timeline-entry>
                <q-timeline-entry title="DSO Target" >
                  <div class="text-grey-6 terminal">{{`delta_sp:    RA ${fmt((p.deltaref[0]??0)/15,"hr")}   |  Dec ${fmt(p.deltaref[1])}   |   PA ${fmt(p.deltaref[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Orbital Target">
                  <div class="text-grey-6 terminal">3Line</div>
                </q-timeline-entry>
                <q-timeline-entry title="AzAlt Target">
                  <div class="text-grey-6 terminal">{{`alpha_sp:    Az ${fmt(p.alpharef[0],"hr")}   |  Alt ${fmt(p.alpharef[1])}   | Roll ${fmt(p.alpharef[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Pulse Guiding" subtitle="Guide" icon="mdi-pulse">
                  <div class="text-grey-6 terminal">delta_offset</div>
                </q-timeline-entry>
                <q-timeline-entry title="Sidereal Motion" subtitle="Track" icon="mdi-flare">
                  <div class="text-grey-6 terminal">delta_ref</div>
                  <div class="text-grey-6 terminal">omega_ref</div>
                  <div class="text-grey-6 terminal">alpha_ref</div>
                </q-timeline-entry>
                <q-timeline-entry title="Shortest Path" subtitle="Plan" icon="mdi-debug-step-over">
                  <div class="text-grey-6 terminal">cameraQ_step</div>
                </q-timeline-entry>
                <q-timeline-entry title="Multi-Point Alignment" subtitle="Translate" icon="mdi-rotate-orbit">
                  <div class="text-grey-6 terminal">theta_ref</div>
                  <div class="text-grey-6 terminal">theta_pv</div>
                </q-timeline-entry>
                <q-timeline-entry title="PID Controller" subtitle="Control" icon="mdi-chart-bell-curve-cumulative">
                  <div class="text-grey-6 terminal">omega_Kp</div>
                  <div class="text-grey-6 terminal">omega_Ki</div>
                  <div class="text-grey-6 terminal">omega_Kd</div>
                  <div class="text-grey-6 terminal">omega_ff</div>
                  <div class="text-grey-6 terminal">omega_tgt</div>
                </q-timeline-entry>
                <q-timeline-entry title="Speed & Accel Monitor" subtitle="Limit" icon="mdi-format-vertical-align-top">
                  <div class="text-grey-6 terminal">omega_op</div>
                </q-timeline-entry>
                <q-timeline-entry title="Speed Controller" subtitle="Comms" icon="mdi-speedometer-slow">
                  <div class="text-grey-6 terminal">protocol</div>
                </q-timeline-entry>
                <q-timeline-entry title="Motors" ></q-timeline-entry>

              </q-timeline>

            </div>
          </div>
        </q-card>

    <div class="row q-col-gutter-sm items-stretch">
      <div class="col-lg-8 col-12 flex">
        <q-card flat bordered class="col">
          <div class="q-pa-md">
              <q-table title="Current Mount Orientation" 
                    :pagination="initialPagination"
                    :rows="rows" :columns="columns" row-key="name">
              </q-table>
          </div>
        </q-card>
      </div>    
      <div class="col-lg-4 col-12 flex">
        <q-card flat bordered class="col">
          <q-img src="../assets/process-diagram.png" contain></q-img>
        </q-card>
      </div>    
  </div>

</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { deg2dms } from 'src/utils/angles'
import { PollingManager } from 'src/utils/polling';
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'src/stores/config';
import { useDeviceStore } from 'src/stores/device';
import type { UnitKey } from 'src/utils/angles'

const p = useStatusStore()
const dev = useDeviceStore()
const cfg = useConfigStore()
const selected = ref([])
const axis = ref<number>(0)
const poll = new PollingManager()

watch(axis, ()=>selected.value=[])

function fmt(x:number|undefined, unit:UnitKey="deg"): string {
  const s = deg2dms(x ?? 0, 1, unit)
  return `${s.sign}${s.degreestr}${s.minutestr}${s.secondstr}`
}

type TableRow = {
  q:string, name:string, az:string, alt:string, roll:string, ra:string, dec:string, pa:string, 
}

onMounted(async () => {
  const shouldFetch =
    dev.restAPIConnected &&
    dev.restAPIConnectedAt &&
    cfg.fetchedAt < dev.restAPIConnectedAt

  if (shouldFetch) {
    await cfg.configFetch()
  }
  poll.startPolling(() => { void cfg.configFetch() }, 10, 'configFetch')
})

onUnmounted(() => {
  poll.stopPolling()
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
  { name:'(1) Polaris: Quaternion (Q1)', q:p.q1, az:'', alt:'', roll:'', ra:'', dec:'', pa:''},
  { name:'(2) ASCOM: n-Aligned and KF (Q1S)', q:p.q1s, az:'', alt:'', roll:'', ra:'', dec:'', pa:''},
  { name:'(3) Polaris: Motors Angles M1-3 (Zeta)', q:'', az:fmt(p.zetameas[0]), alt:fmt(p.zetameas[1]), roll:fmt(p.zetameas[2]), ra:'', dec:'', pa:'',},
  { name:'(4) Polaris: Motors 1-Aligned T1-3 (Theta)', q:'', az:fmt(p.thetastate[0]), alt:fmt(p.thetastate[1]), roll:fmt(p.thetastate[2]), ra:'', dec:'', pa:'',},
  { name:'(5) Polaris: Orientation 1-Aligned L1-3 (Lota)', q:'', az:fmt(p.lotameas[0]), alt:fmt(p.lotameas[1]), roll:fmt(p.lotameas[2]), ra:fmt(p.lotameas[3], "hr"), dec:fmt(p.lotameas[4]), pa:'',},
  { name:'(6) ASCOM: Orientation n-Aligned (ASCOM)', q:'', az:fmt(p.azimuth), alt:fmt(p.altitude), roll:fmt(p.roll), ra:fmt(p.rightascension, "hr"), dec:fmt(p.declination), pa:fmt(p.positionangle)},
  { name:'(7) ASCOM: Parallatic Angle', q:'', az:'', alt:'', roll:'', ra:'', dec:'', pa:fmt(p.parallacticangle)},
  { name:'(8) Alpaca: PID Setpoint (Alpha & Delta)', q:'',  az:fmt(p.alpharef[0]), alt:fmt(p.alpharef[1]), roll:fmt(p.alpharef[2]), ra:fmt((p.deltaref[0]??0)/180*12, "hr"), dec:fmt(p.deltaref[1]), pa:fmt(p.deltaref[2])},
  { name:'(9) Alpaca: PID Feed forwad (Omega)', q:'',  az:fmt(p.omegaref[0]), alt:fmt(p.omegaref[1]), roll:fmt(p.omegaref[2]), ra:'', dec:'', pa:'',},
  { name:'(0) Alpaca: PID Controller (OP dps)', q:'',  az:fmt(p.motorref[0]), alt:fmt(p.motorref[1]), roll:fmt(p.motorref[2]), ra:'', dec:'', pa:'',},

]
})

const initialPagination = {
        rowsPerPage: 30
      }


</script>

<style lang="scss">
  .terminal {
    font-family: monospace;
    white-space: pre;
  }
  .q-markdown--link {
    color: $grey-6;

    &:hover {
      text-decoration: underline;
      color: $grey-4;
    }
  }
</style>