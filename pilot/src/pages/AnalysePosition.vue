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
        <q-space />
        <div class="q-gutter-md flex justify-end q-mr-md">
          <div class="col-auto q-gutter-sm flex justify-end items-center">
            <q-btn rounded  icon="mdi-information-variant-circle" color="grey-9" label="Reference Documentation" class="position-right" 
                href="https://github.com/ogecko/alpaca-benro-polaris/blob/dev2_2/docs/kinematics.md"  target="_blank" rel="noopener" />
          </div>
        </div>
    </div>

    <!-- Page Body -->

        <q-card flat bordered class="col">
          <div class="row ">
            <div class="col-lg-6 col-12">
              <q-timeline layout="comfortable" class="">
                <q-timeline-entry heading tag="h4">Forward Kinematics</q-timeline-entry>
                <q-timeline-entry title="Polaris" >
                  <div class="text-grey-6 terminal">{{`motor_raw:   M1 ${fmt(p.zetameas[0])}   |   M2 ${fmt(p.zetameas[1])}   |   M3 ${fmt(p.zetameas[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Single-Point Alignment (Polaris)" subtitle="align" icon="mdi-rotate-orbit">
                  <div class="text-grey-6 terminal">{{`qC2B_raw:     w ${fmtn(p.qraw[0])}      x ${fmtn(p.qraw[1])}   y ${fmtn(p.qraw[2])}   z ${fmtn(p.qraw[3])}`}}</div>
                  <div class="text-grey-6 terminal">{{`theta_raw:   t1 ${fmt(p.traw[0])}   |   t2 ${fmt(p.traw[1])}   |   t3 ${fmt(p.traw[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Kalman Filter" subtitle="Smooth" icon="mdi-chart-line">
                  <div v-if="cfg.advanced_kf" >
                    <div class="text-grey-6 terminal">{{`qC2B_state:   w ${fmtn(p.qstate[0])}      x ${fmtn(p.qstate[1])}   y ${fmtn(p.qstate[2])}   z ${fmtn(p.qstate[3])}`}}</div>
                    <div class="text-grey-6 terminal">{{`theta_state: t1 ${fmt(p.tstate[0])}   |   t2 ${fmt(p.tstate[1])}   |   t3 ${fmt(p.tstate[2])}`}}</div>
                    <div class="text-grey-6 terminal">{{`alpha_state: Az ${fmt(p.astate[0])}   |  Alt ${fmt(p.astate[1])}   | Roll ${fmt(p.astate[2])}`}}</div>
                  </div>
                  <div v-else class="text-grey-6 terminal">Disabled</div>
                </q-timeline-entry>
                <q-timeline-entry title="Error Corrections" subtitle="Correct" icon="mdi-axis-x-rotate-clockwise">
                  <div v-if="cfg.advanced_pec" class="text-grey-6 terminal">{{`PEC: Predictive Error Correction                     Use PHD2`}}</div>
                  <div v-else class="text-grey-6 terminal">PEC: Disabled</div>
                  <div v-if="cfg.advanced_align_roll" class="text-grey-6 terminal">{{`RBC: Rotation Bias Correction                        Roll Adj ${fmt(p.rbcerror)}`}}</div>
                  <div v-else class="text-grey-6 terminal">RBC: Disabled</div>
                  <div v-if="cfg.advanced_align_local" class="text-grey-6 terminal">{{`LGC: Local Guassian Correction         Last Sync Residual Adj ${fmt(-p.lgcerror)}`}}</div>
                  <div v-else class="text-grey-6 terminal">LGC: Disabled</div>
                </q-timeline-entry>
                <q-timeline-entry title="Multi-Point Alignment (Driver)" subtitle="align" icon="mdi-rotate-orbit">
                  <div v-if="cfg.advanced_alignment" class="text-grey-6 terminal">{{`qB2T_align:   w ${fmtn(p.qalign[0])}      x ${fmtn(p.qalign[1])}   y ${fmtn(p.qalign[2])}   z ${fmtn(p.qalign[3])}`}}</div>
                  <div v-if="cfg.advanced_alignment" class="text-grey-6 terminal">{{`QUEST Adj:   Az ${fmt(p.az_adj)}   | Tilt ${fmt(p.tilt_adj_mag)}   |  Rot ${fmt(p.roll_adj)}`}}</div>
                  <div v-else class="text-grey-6 terminal">Disabled</div>
                </q-timeline-entry>
                <q-timeline-entry title="Alpaca API" subtitle="serve" icon="mdi-email-fast">
                  <div class="text-grey-6 terminal">{{`qC2T_pv:      w ${fmtn(p.qpv[0])}      x ${fmtn(p.qpv[1])}   y ${fmtn(p.qpv[2])}   z ${fmtn(p.qpv[3])}`}}</div>
                  <div class="text-grey-6 terminal">{{`theta_pv:    t1 ${fmt(p.tstate[0])}   |   t2 ${fmt(p.tstate[1])}   |   t3 ${fmt(p.tstate[2])}`}}</div>
                  <div class="text-grey-6 terminal">{{`alpha_pv:    Az ${fmt(p.azimuth)}   |  Alt ${fmt(p.altitude)}   | Roll ${fmt(p.roll)}`}}</div>
                  <div class="text-grey-6 terminal">{{`delta_pv:    RA ${fmt(p.rightascension,"hr")}   |  Dec ${fmt(p.declination)}   | PosA ${fmt(p.positionangle)}`}}</div>
                  <div class="text-grey-6 terminal">{{`ephem:       HA ${fmt(p.siderealtime - p.rightascension,"hr")}   |             Paralatic Angle ${fmt(p.parallacticangle)}`}}</div>
                  <div class="text-grey-6 terminal">{{`            LST ${fmt(p.siderealtime,"hr")}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Sky" ></q-timeline-entry>
              </q-timeline>
            </div>
            <div class="col-lg-6 col-12">
              <q-timeline layout="comfortable" class="q-pr-xl">
                <q-timeline-entry heading tag="h4">Inverse Kinematics</q-timeline-entry>
                <q-timeline-entry title="Sky" ></q-timeline-entry>
                <q-timeline-entry title="Pulse Guiding" subtitle="Guide" icon="mdi-pulse">
                  <div class="text-grey-6 terminal">delta_offset</div>
                </q-timeline-entry>
                <q-timeline-entry :title="tgt.title" :subtitle="tgt.task" :icon="tgt.icon">
                </q-timeline-entry>
                <q-timeline-entry title="DSO Target" subtitle="Track" icon="mdi-flare">
                  <div class="text-grey-6 terminal">{{`delta_sp:    RA ${fmt((p.deltaref[0]??0)/15,"hr")}   |  Dec ${fmt(p.deltaref[1])}   |   PA ${fmt(p.deltaref[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Orbital Target" subtitle="Track" icon="mdi-satellite-variant">
                  <div class="text-grey-6 terminal">{{`TLA_line1:   ISS (ZARYA)`}}</div>
                  <div class="text-grey-6 terminal">{{`TLA_line2:   1 25544U 98067A   03097.78853147  .00021906  00000-0  28403-3 0  8652`}}</div>
                  <div class="text-grey-6 terminal">{{`TLA_line3:   2 25544  51.6361  13.7980 0004256  35.6671  59.2566 15.58778559250029`}}</div>
                  <div class="text-grey-6 terminal">{{`delta_sp:    RA ${fmt((p.deltaref[0]??0)/15,"hr")}   |  Dec ${fmt(p.deltaref[1])}   |   PA ${fmt(p.deltaref[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="AzAlt Target" subtitle="Goto" icon="mdi-move-resize-variant">
                  <div class="text-grey-6 terminal">{{`alpha_sp:    Az ${fmt(p.alpharef[0],"hr")}   |  Alt ${fmt(p.alpharef[1])}   | Roll ${fmt(p.alpharef[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Adjust Target" subtitle="Slew" icon="mdi-move-resize-variant">
                  <div>
                    <VField label="delta_v_sp:  RA " :val="p.dvsp[0]??0" unit="hr/s"/>
                    <VField label=" |  Dec " :val="p.dvsp[1]??0" unit="deg/s"/>
                    <VField label=" |   PA " :val="p.dvsp[2]??0" unit="deg/s"/>
                  </div>
                  <div>
                    <VField label="alpha_v_sp:  Az " :val="p.avsp[0]??0" unit="deg/s"/>
                    <VField label=" |  Alt " :val="p.avsp[1]??0" unit="deg/s"/>
                    <VField label=" | Roll " :val="p.avsp[2]??0" unit="deg/s"/>
                  </div>
                  <div class="text-grey-6 terminal">{{`delta_offst: RA ${fmt(p.alpharef[0],"hr")}   |  Dec ${fmt(p.alpharef[1])}   |   PA ${fmt(p.alpharef[2])}`}}</div>
                  <div class="text-grey-6 terminal">{{`alpha_offst: Az ${fmt(p.alpharef[0],"hr")}   |  Alt ${fmt(p.alpharef[1])}   | Roll ${fmt(p.alpharef[2])}`}}</div>
                </q-timeline-entry>
                <q-timeline-entry title="Waiting for Command" subtitle="Idle"  icon="mdi-sleep" >
                </q-timeline-entry>
                <q-timeline-entry title="Optimal Movement Strategy" subtitle="Plan" icon="mdi-debug-step-over">
                  <div class="text-grey-6 terminal">delta_ref</div>
                  <div class="text-grey-6 terminal">alpha_ref</div>
                  <div class="text-grey-6 terminal">omega_ref</div>
                  <div class="text-grey-6 terminal">cameraQ_step</div>
                </q-timeline-entry>
                <q-timeline-entry title="Multi-Point Alignment" subtitle="Solve" icon="mdi-rotate-orbit">
                  <div class="text-grey-6 terminal">theta_ref</div>
                  <div class="text-grey-6 terminal">theta_pv</div>
                </q-timeline-entry>
                <q-timeline-entry icon="mdi-chart-bell-curve-cumulative">
                  <template v-slot:title>PID Controller <PIDStatus /></template>
                  <template v-slot:subtitle>Control</template>
                  <div class="text-grey-6 terminal">omega_Kp</div>
                  <div class="text-grey-6 terminal">omega_Ki</div>
                  <div class="text-grey-6 terminal">omega_Kd</div>
                  <div class="text-grey-6 terminal">omega_ff</div>
                  <div class="text-grey-6 terminal">omega_tgt</div>
                </q-timeline-entry>
                <q-timeline-entry title="Speed & Accel Governer" subtitle="Limit" icon="mdi-format-vertical-align-top">
                  <div class="text-grey-6 terminal">omega_op</div>
                </q-timeline-entry>
                <q-timeline-entry title="Speed Controller" subtitle="Comms" icon="mdi-speedometer-slow">
                  <div class="text-grey-6 terminal">protocol</div>
                  <div class="text-grey-6 terminal">{{`Protocol:    M1 +1 30:70 +2     |   M2 +2000           |  M3 ${fmt(p.astate[2])}`}}</div>
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
import PIDStatus from 'src/components/PIDStatus.vue'
import VField from 'src/components/VField.vue'


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


function fmtn(x:number|undefined, decimals:number=7): string {
  const n = x??0
  const sign = n < 0 ? '-' : '+';
  const nstr = Math.abs(n).toFixed(decimals)
  return sign+nstr
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

const wfc="Waiting for Command"

const tgt = computed(() => 
  p.pidmode=='PRESETUP' ? {task: "PreSetup", title: wfc, icon: 'mdi-cellphone-cog'} :
  p.pidmode=='LIMIT' ? {task: "Limit", title: wfc, icon: 'mdi-alert'} :
  p.pidmode=='HOMING' ? {task: "Home", title: 'Home Target', icon: 'mdi-home-outline'} :
  p.pidmode=='PARKING' ? {task: "Park", title: 'Park Target', icon: 'mdi-alpha-p'}:
  p.athome ? {task: "At Home", title: wfc, icon: 'mdi-home'} : 
  p.atpark ? {task: "Parked", title: wfc, icon: 'mdi-parking'} : 
  p.gotoing ? {task: "Goto", title: 'AzAlt Target', icon: 'mdi-move-resize-variant'} : 
  p.slewing ? {task: "Slew", title: 'Slewing Target', icon: 'mdi-cursor-move'} :
  p.rotating ? {task: "Rotate", title: 'Rotating Target', icon: 'mdi-restore'} :
  p.tracking  ? {task: "Track", title: `${trackingStatusLabel.value} Target`, icon: 'mdi-star-shooting-outline'} : 
  p.pidglock  ? {task: "Gimbal", title: 'Gimble Locked', icon: 'mdi-lock'} : 
               {task: "Idle", title: wfc, icon: 'mdi-sleep'}
)

const trackingStatusLabel = computed(() => {
  const [isTracking, az, alt] = p.orbitalstatus;
  const azText = az !== undefined ? `${Math.round(az)}°` : '—';
  const altText = alt !== undefined ? `${Math.round(alt)}°` : '—';
  return isTracking === 1
    ? `${trackingLabel.value} (Az ${azText} Alt ${altText})`
    : trackingLabel.value;
});



const trackingLabel = computed(() =>
  p.trackingrate==0 ? "Sidereal" : 
  p.trackingrate==1 ? "Lunar" : 
  p.trackingrate==2 ? "Solar" : 
  p.trackingrate==3 && p.trackingname ? p.trackingname : 
                      "Custom" 
)


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
  { name:'(3) Polaris: Motors Angles M1-3 (Zeta)', q:'', az:fmt(p.zetameas[0]), alt:fmt(p.zetameas[1]), roll:fmt(p.zetameas[2]), ra:'', dec:'', pa:'',},
  { name:'(4) Polaris: Motors 1-Aligned T1-3 (Theta)', q:'', az:fmt(p.tstate[0]), alt:fmt(p.tstate[1]), roll:fmt(p.tstate[2]), ra:'', dec:'', pa:'',},
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

  .c-ok {
    color: $grey-6;
  }

  .c-off {
    color: $grey-8;
  }

  .c-neg {
    color: $negative;
  }

  .c-war {
    color: $warning;
  }

  .c-pos {
    color: $positive;
  }

  .q-markdown--link {
    color: $grey-6;

    &:hover {
      text-decoration: underline;
      color: $grey-4;
    }
  }
</style>