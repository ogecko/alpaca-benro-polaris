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

const mpaerror = computed(() => p.mpastatus ? p.mpastatus[1] : 0)
const mpacount = computed(() => p.mpastatus ? p.mpastatus[0] : 0)
const statusLabel = computed(() => 
  cfg.advanced_alignment==false ? "Single" :
  mpacount.value==0 ? "add points" :
  mpacount.value==1 ? "1 point" :
  mpacount.value==2 ? "2 points" :
  (mpaerror.value ?? 0) > 5 ? `${mpaerror.value?.toFixed(1)}° residual` :
                      `${mpacount.value} points`
)

const statusColor = computed(() =>
  cfg.advanced_alignment==false ? "primary" :
  (mpacount.value ?? 0) < 3  ? "warning" :
  (mpaerror.value ?? 0) > 5  ? "warning" :
  "positive"
)

const statusOutline = computed(() => (
  cfg.advanced_alignment==false
))

const statusIcon = computed(() => 
  cfg.advanced_alignment==false ? "mdi-star" :
  "mdi-globe-model"
)



</script>

<style scoped>

</style>