<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Header Row -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        Alpaca Driver Performance Analysis
        <div class="text-caption ok">
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
                <!-- Polaris -->
                <q-timeline-entry title="Polaris Motors" >
                  <div>
                    <VField label="motor_raw:   M1 " :val="p.zetameas[0]" unit="deg"/>
                    <VField label="   |   M2 " :val="p.zetameas[1]" unit="deg"/>
                    <VField label="   |   M3 " :val="p.zetameas[2]" unit="deg"/>
                  </div>
                </q-timeline-entry>
                <!-- SPA -->
                <q-timeline-entry title="Single-Point Alignment (Polaris)" subtitle="align" icon="mdi-rotate-orbit">
                  <div>
                    <VField label="qC2B_raw:     w " :val="p.qraw[0]" unit="number"/>
                    <VField label="      x " :val="p.qraw[1]" unit="number"/>
                    <VField label="   y " :val="p.qraw[2]" unit="number"/>
                    <VField label="   z " :val="p.qraw[3]" unit="number"/>
                  </div>
                  <div>
                    <VField label="theta_raw:   t1 " :val="p.traw[0]" unit="deg"/>
                    <VField label="   |   t2 " :val="p.traw[1]" unit="deg"/>
                    <VField label="   |   t3 " :val="p.traw[2]" unit="deg"/>
                  </div>
                </q-timeline-entry>
                <!-- KF -->
                <q-timeline-entry title="Kalman Filter" subtitle="Smooth" icon="mdi-chart-line">
                  <div v-if="cfg.advanced_kf" >
                    <div>
                      <VField label="qC2B_state:   w " :val="p.qstate[0]" unit="number"/>
                      <VField label="      x " :val="p.qstate[1]" unit="number"/>
                      <VField label="   y " :val="p.qstate[2]" unit="number"/>
                      <VField label="   z " :val="p.qstate[3]" unit="number"/>
                    </div>
                    <div>
                      <VField label="theta_state: t1 " :val="p.tstate[0]" unit="deg"/>
                      <VField label="   |   t2 " :val="p.tstate[1]" unit="deg"/>
                      <VField label="   |   t3 " :val="p.tstate[2]" unit="deg"/>
                    </div>
                    <div>
                      <VField label="alpha_state: Az " :val="p.astate[0]" unit="deg"/>
                      <VField label="   |  Alt " :val="p.astate[1]" unit="deg"/>
                      <VField label="   | Roll " :val="p.astate[2]" unit="deg"/>
                    </div>
                  </div>
                  <div v-else class="haz terminal">Disabled</div>
                </q-timeline-entry>
                <!-- Corrections -->
                <q-timeline-entry title="Error Corrections" subtitle="Adjust" icon="mdi-axis-x-rotate-clockwise">
                  <!-- MAC -->
                  <div class="ok terminal">
                    <span>{{`MAC: Mechanical Alignment Correction`}}</span>
                    <VField v-if="cfg.advanced_align_mac" label="           Mechanical Adj " :val="p.rbcerror" unit="deg_ofst"/>
                    <span v-else class="haz">{{ `                              Disabled`}}</span>
                  </div>
                  <!-- SCC -->
                  <div class="ok terminal">
                    <span>{{`SCC: Slew & Center Correction`}}</span>
                    <span v-if="cfg.advanced_scc_enabled">
                        <VField v-if="cfg.advanced_scc_choice==0" label="          Zero Last Residual Adj " :val="p.sccerror" unit="deg_ofst"/>
                        <VField v-if="cfg.advanced_scc_choice==1" label="              Local Guassian Adj " :val="p.sccerror" unit="deg_ofst"/>
                        <VField v-if="cfg.advanced_scc_choice==2" label="                Sync Guiding Adj " :val="p.sccerror" unit="deg_ofst"/>
                    </span>
                    <span v-else class="haz">{{ `                                     Disabled`}}</span>
                  </div >
                  <!-- PEC -->
                  <div class="ok terminal">
                    <span>{{`PEC Rate:`}}</span>
                    <span v-if="cfg.advanced_pec" >
                      <VField label="    RA " :val="p.pec[0]" unit="deg/hr"/>
                      <VField label=" |  Dec " :val="p.pec[1]" unit="deg/hr"/>
                      <VField label=" | R² " :val="p.pec[2]" unit="r2"/>
                      <VField label=" | R² " :val="p.pec[3]" unit="r2"/>
                    </span>
                    <span v-else>
                      <span >{{` Periodic Error Correction  `}}</span>
                      <span class="haz">{{ `                             Disabled`}}</span>
                    </span>
                  </div>
                  <!-- Guiding -->
                  <div class="ok terminal">
                    <span>{{`Guide Pulse:`}}</span>
                    <span v-if="cfg.advanced_pulse_guiding || cfg.advanced_sync_guiding" >
                      <VField label=" RA " :val="p.gdpulse[0]" unit="deg_ofst"/>
                      <VField label="   |  Dec " :val="p.gdpulse[1]" unit="deg_ofst"/>
                      <VField label="   | PosA " :val="p.gdpulse[2]" unit="deg_ofst"/>
                    </span>
                    <span v-else>
                      <span >{{`   Sync/Pulse Guiding`}}</span>
                      <span class="haz">{{ `                                  Disabled`}}</span>
                    </span>
                  </div>
                  <div class="ok terminal">
                    <span>{{`Guide Accum:`}}</span>
                    <span v-if="cfg.advanced_pulse_guiding || cfg.advanced_sync_guiding" >
                      <VField label=" RA " :val="p.gdaccum[0]" unit="deg_ofst"/>
                      <VField label="   |  Dec " :val="p.gdaccum[1]" unit="deg_ofst"/>
                      <VField label="   | PosA " :val="p.gdaccum[2]" unit="deg_ofst"/>
                    </span>
                    <span v-else>
                      <span >{{`  Sync/Pulse Guiding`}}</span>
                      <span class="haz">{{ `                                  Disabled`}}</span>
                    </span>
                  </div>
                </q-timeline-entry>
                <!-- MPA -->
                <q-timeline-entry title="Multi-Point Alignment (Driver)" subtitle="align" icon="mdi-rotate-orbit">
                  <div v-if="cfg.advanced_alignment">
                    <VField label="qB2T_align:   w " :val="p.qalign[0]" unit="number"/>
                    <VField label="      x " :val="p.qalign[1]" unit="number"/>
                    <VField label="   y " :val="p.qalign[2]" unit="number"/>
                    <VField label="   z " :val="p.qalign[3]" unit="number"/>
                  </div>
                  <div v-if="cfg.advanced_alignment">
                    <VField label="QUEST Adj:   Az " :val="p.az_adj" unit="deg"/>
                    <VField label="   | Tilt " :val="p.tilt_adj_mag" unit="deg"/>
                    <VField label="   | Roll " :val="p.roll_adj" unit="deg"/>
                  </div>
                  <div v-else class="haz terminal">Disabled</div>
                </q-timeline-entry>
                <!-- API -->
                <q-timeline-entry title="Alpaca API" subtitle="serve" icon="mdi-email-fast">
                  <div>
                    <VField label="qC2T_pv:      w " :val="p.qpv[0]" unit="number"/>
                    <VField label="      x " :val="p.qpv[1]" unit="number"/>
                    <VField label="   y " :val="p.qpv[2]" unit="number"/>
                    <VField label="   z " :val="p.qpv[3]" unit="number"/>
                  </div>
                  <div>
                    <VField label="alpha_pv:    Az " :val="p.azimuth" unit="deg"/>
                    <VField label="   |  Alt " :val="p.altitude" unit="deg"/>
                    <VField label="   | Roll " :val="p.roll" unit="deg" v-if="cfg.advanced_rotator"/>
                  </div>
                  <div>
                    <VField label="delta_pv:    RA " :val="p.rightascension" unit="hr"/>
                    <VField label="   |  Dec " :val="p.declination" unit="deg"/>
                    <VField label="   | PosA " :val="p.positionangle" unit="deg" v-if="cfg.advanced_rotator"/>
                  </div>
                  <div>
                    <VField label="gamma_pv:   lat " :val="p.gpv[0]" unit="deg"/>
                    <VField label="   |  lon " :val="p.gpv[1]" unit="deg"/>
                    <VField label="   |  gpa " :val="p.gpv[2]" unit="deg" v-if="cfg.advanced_rotator"/>
                  </div>
                  <div>
                    <VField label="ephem:       HA " :val="p.siderealtime - p.rightascension" unit="hr"/>
                    <VField label="   |             Paralatic Angle " :val="p.declination" unit="deg"  v-if="cfg.advanced_rotator"/>
                  </div>
                  <div>
                    <VField label="            LST " :val="p.siderealtime" unit="hr"/>
                  </div>
                </q-timeline-entry>
                <q-timeline-entry title="Sky" ></q-timeline-entry>
              </q-timeline>
            </div>
            <div class="col-lg-6 col-12">
              <q-timeline layout="comfortable" class="q-pr-xl">
                <q-timeline-entry heading tag="h4">Inverse Kinematics</q-timeline-entry>
                <q-timeline-entry title="Sky" ></q-timeline-entry>
                <!-- SET POINT -->
                <q-timeline-entry :title="tgt.title" :subtitle="tgt.task" :icon="tgt.icon">
                  <div>
                    <VField label="orbital_sp:  ID " :val="orbital.label" unit="string" :color="orbital.color"/>
                  </div>
                  <div>
                    <VField label="delta_sp:    RA " :val="p.dsp[0]" unit="deg2hr" :color="dsp_color"/>
                    <VField label="   |  Dec " :val="p.dsp[1]" unit="deg"  :color="dsp_color"/>
                    <VField label="   | PosA " :val="p.dsp[2]" unit="deg" :color="dsp_color"/>
                  </div>
                  <div>
                    <VField label="alpha_sp:    Az " :val="p.asp[0]" unit="deg" :color="asp_color"/>
                    <VField label="   |  Alt " :val="p.asp[1]" unit="deg" :color="asp_color"/>
                    <VField label="   | Roll " :val="p.asp[2]" unit="deg" :color="rsp_color"/>
                  </div>
                </q-timeline-entry>
                <!-- SLEWING and OFFSETS -->
                <q-timeline-entry title="Slewing and Offsets" subtitle="Adjust" icon="mdi-pulse">
                  <div v-if="cfg.advanced_slewing" >
                    <VField label="delta_slew:  RA " :val="p.dslew[0]" unit="deg/s"/>
                    <VField label=" |  Dec " :val="p.dslew[1]" unit="deg/s"/>
                    <VField label=" | PosA " :val="p.dslew[2]" unit="deg/s"/>
                  </div>
                  <div v-else class="haz terminal">Advanced Slewing: Disabled</div>
                  <div>
                    <VField label="delta_offst: RA " :val="p.dofst[0]" unit="deg_ofst"/>
                    <VField label="   |  Dec " :val="p.dofst[1]" unit="deg_ofst"/>
                    <VField label="   | PosA " :val="p.dofst[2]" unit="deg_ofst"/>
                  </div>
                  <!-- <div>&nbsp;</div> -->
                  <div v-if="cfg.advanced_slewing">
                    <VField label="alpha_slew:  Az " :val="p.aslew[0]" unit="deg/s"/>
                    <VField label=" |  Alt " :val="p.aslew[1]" unit="deg/s"/>
                    <VField label=" | Roll " :val="p.aslew[2]" unit="deg/s"/>
                  </div>
                  <div v-else class="haz terminal">Advanced Slewing: Disabled</div>
                  <div>
                    <VField label="alpha_offst: Az " :val="p.aofst[0]" unit="deg_ofst"/>
                    <VField label="   |  Alt " :val="p.aofst[1]" unit="deg_ofst"/>
                    <VField label="   | Roll " :val="p.aofst[2]" unit="deg_ofst"/>
                  </div>
                </q-timeline-entry>
                <!-- MPA-PLANNING REF -->
                <q-timeline-entry title="Model Predictive Control" subtitle="Plan" icon="mdi-debug-step-over">
                  <div v-if="cfg.advanced_goto">
                    <div>
                      <VField label="delta_ref:   RA " :val="p.deltaref[0]" unit="deg2hr"/>
                      <VField label="   |  Dec " :val="p.deltaref[1]" unit="deg"/>
                      <VField label="   | PosA " :val="p.deltaref[2]" unit="deg"/>
                    </div>
                    <div>
                      <VField label="delta_pv:    RA " :val="p.rightascension" unit="hr"/>
                      <VField label="   |  Dec " :val="p.declination" unit="deg"/>
                      <VField label="   | PosA " :val="p.positionangle" unit="deg" v-if="cfg.advanced_rotator"/>
                    </div>
                    <div>
                      <VField label="alpha_ref:   Az " :val="p.alpharef[0]" unit="deg"/>
                      <VField label="   |  Alt " :val="p.alpharef[1]" unit="deg"/>
                      <VField label="   | Roll " :val="p.alpharef[2]" unit="deg"/>
                    </div>
                    <div>
                      <VField label="alpha_pv:    Az " :val="p.azimuth" unit="deg"/>
                      <VField label="   |  Alt " :val="p.altitude" unit="deg"/>
                      <VField label="   | Roll " :val="p.roll" unit="deg" v-if="cfg.advanced_rotator"/>
                    </div>
                  </div>
                  <div v-else class="haz terminal">Advanced Goto: Disabled</div>
                </q-timeline-entry>
                <!-- PID CONTROLLER -->
                <q-timeline-entry icon="mdi-chart-bell-curve-cumulative">
                  <template v-slot:title>PID Controller <PIDStatus /></template>
                  <template v-slot:subtitle>Control</template>
                  <div v-if="cfg.advanced_tracking">
                    <div>
                      <VField label="theta_ref:   t1 " :val="p.tref[0]" unit="deg"/>
                      <VField label="   |   t2 " :val="p.tref[1]" unit="deg"/>
                      <VField label="   |   t3 " :val="p.tref[2]" unit="deg"/>
                    </div>
                    <div>
                      <VField label="theta_pv:    t1 " :val="p.tpv[0]" unit="deg"/>
                      <VField label="   |   t2 " :val="p.tpv[1]" unit="deg"/>
                      <VField label="   |   t3 " :val="p.tpv[2]" unit="deg"/>
                    </div>
                    <div>
                      <VField label="error_sig:   t1 " :val="p.errsig[0]" unit="deg_ofst" :tollerance="2/3600"/>
                      <VField label="   |   t2 " :val="p.errsig[1]" unit="deg_ofst" :tollerance="2/3600"/>
                      <VField label="   |   t3 " :val="p.errsig[2]" unit="deg_ofst" :tollerance="2/3600"/>
                    </div>
                  </div>
                  <div v-else class="haz terminal">PID Controller: Disabled</div>
                </q-timeline-entry>
                <!-- SPEED CONTROLLER -->
                <q-timeline-entry title="Speed Controller" subtitle="Comms" icon="mdi-speedometer-slow">
                  <div>
                    <VField label="omega_ref:   t1 " :val="p.omegaref[0]" unit="deg/s"/>
                    <VField label=" |   t2 " :val="p.omegaref[1]" unit="deg/s"/>
                    <VField label=" |   t3 " :val="p.omegaref[2]" unit="deg/s"/>
                  </div>
                  <div>
                    <VField label="omega_op:    t1 " :val="p.motorref[0]" unit="deg/s"/>
                    <VField label=" |   t2 " :val="p.motorref[1]" unit="deg/s"/>
                    <VField label=" |   t3 " :val="p.motorref[2]" unit="deg/s"/>
                  </div>
                  <div>
                    <VField label="Protocol:    M1 " :val="p.motorcmd[0]" unit="string"/>
                    <VField label="     |   M2 " :val="p.motorcmd[1]" unit="string"/>
                    <VField label="     |   M3 " :val="p.motorcmd[2]" unit="string"/>
                  </div>
                </q-timeline-entry>
                <q-timeline-entry title="Polaris Motors" ></q-timeline-entry>
              </q-timeline>

            </div>
          </div>
        </q-card>



</q-page>
</template>


<script setup lang="ts">

import StatusBanners from 'src/components/StatusBanners.vue'
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { PollingManager } from 'src/utils/polling';
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'src/stores/config';
import { useDeviceStore } from 'src/stores/device';
import PIDStatus from 'src/components/PIDStatus.vue'
import VField from 'src/components/VField.vue'


const p = useStatusStore()
const dev = useDeviceStore()
const cfg = useConfigStore()
const selected = ref([])
const axis = ref<number>(0)
const poll = new PollingManager()

watch(axis, ()=>selected.value=[])

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

const dsp_color = computed(() => (p.tracking ? 'pos' : 'std'))  
const asp_color = computed(() => ((!p.tracking && (p.gotoing || p.slewing)) ? 'pos' : 'std'))  
const rsp_color = computed(() => ((!p.tracking && (p.rotating || p.slewing)) ? 'pos' : 'std'))  


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

const orbital = computed(() => ({
  label: !cfg.advanced_orbitals ? 'Disabled' : p.trackingrate==0? 'None' : trackingLabel.value,
  color: !cfg.advanced_orbitals ? 'haz'      : p.trackingrate==0? 'std'  : p.tracking ? 'pos' : 'std'
}))


</script>

<style lang="scss">
  .terminal {
    font-family: monospace;
    white-space: pre;
  }

  .ok {
    color: $grey-6;
  }

  .off {
    color: $grey-8;
  }

  .neg {
    color: $negative;
  }

  .haz {
    color: $warning;
  }

  .pos {
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