<template>
        <q-chip :color="statusColor" :outline="statusOutline" :icon="statusIcon" class="q-pa-md">
        {{statusLabel}}
      </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStatusStore } from 'src/stores/status'
import { useConfigStore } from 'stores/config';

const p = useStatusStore()
const cfg = useConfigStore()

function toNumber(x: unknown, fallback = 0): number {
  if (typeof x === 'number') return x
  if (typeof x === 'string') {
    const n = Number(x)
    return isNaN(n) ? fallback : n
  }
  return fallback
}

function fmt_r2(x: unknown, decimals:number=3): string {
  const n = toNumber(x)
  return (n == 0)  ? 'Idle' :
         (n == -1) ? 'Valid' :
         (n == -2) ? 'Warmup' :
         (n == -3) ? 'Adapt' :
         (n == -4) ? 'RMSE' :
         (n == -5) ? 'R² Low' :
                     `R² ${n.toFixed(decimals)}`
}

function col_r2(r2ra: unknown, r2dec: unknown) {
  const v = Math.min(toNumber(r2ra), toNumber(r2dec))
  return v == 0 ? 'primary' : 
         v < 0 ? 'warning' :
         v > 0.5 ? 'positive' :
         'primary'
}


const statusLabel = computed(() =>  
   cfg.advanced_pec==false ? "Disabled" : 
            p.pec[2] == 0 && p.pec[3] == 0 ? 'Idle' :
           p.pec[2] == -2 && p.pec[3] == -2 ? 'Warmup' :
                            `${fmt_r2(p.pec[2])} | ${fmt_r2(p.pec[3])}`
)

const statusColor = computed(() =>
    cfg.advanced_pec==false ? "grey-8" : 
                              col_r2(p.pec[2], p.pec[3])
)

const statusOutline = computed(() => 
           cfg.advanced_pec==false ? true :
    p.pec[2] == 0 && p.pec[3] == 0 ? true :
                                     false
)

const statusIcon = computed(() => "mdi-sine-wave")



</script>

<style scoped>

</style>