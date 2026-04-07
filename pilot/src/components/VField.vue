<template>
  <span class="terminal std"><span class="ok">{{label}}</span><span :class="fmt.color">{{fmt.Fn(val)}}</span></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { deg2dms } from 'src/utils/angles'
import type { UnitKey } from 'src/utils/angles'


const props = defineProps<{
  label: string
  val: number | undefined  
  unit: string
}>()


function fmt_deg(x:number|undefined, unit:UnitKey="deg"): string {
  const s = deg2dms(x ?? 0, 1, unit)
  return `${s.sign}${s.degreestr}${s.minutestr}${s.secondstr}`
}
function fmt_hr(x:number|undefined, unit:UnitKey="hr"): string {
    return fmt_deg(x ?? 0 / 15, unit)
}

const BELOW_ZERO = -0.5/3600
const ABOVE_ZERO = +0.5/3600

function fmt_deg_s(x:number|undefined, unit:UnitKey="deg"): string {
  const velocity = x ?? 0
  const str = fmt_deg(velocity, unit).replace(/^[+-]/, '')
  const sign = (velocity>0.5/3600) ? '▲' : (velocity<-0.5/3600) ? '▼' : ' '
  const signed_str = sign + str + '/s'
  return signed_str
}
function fmt_hr_s(x:number|undefined, unit:UnitKey="hr"): string {
    return fmt_deg_s(x ?? 0 / 15, unit)
}

function fmt_number(x:number|undefined, decimals:number=7): string {
  const n = x??0
  const sign = n < 0 ? '-' : '+';
  const nstr = Math.abs(n).toFixed(decimals)
  return sign+nstr
}


const fmt = computed(() => {
  const v = props.val ?? 0  // ← unwrap once here
  return (
    props.unit=="number"    ? { color: 'std', Fn: fmt_number } : 
    props.unit=="deg"       ? { color: 'std', Fn: fmt_deg } : 
    props.unit=="hr"        ? { color: 'std', Fn: fmt_hr } : 
    props.unit=="deg/s"     ? { color: v<BELOW_ZERO ? 'haz' : v>ABOVE_ZERO ? 'pos' : 'off', Fn: fmt_deg_s } : 
    props.unit=="hr/s"      ? { color: v<BELOW_ZERO ? 'haz' : v>ABOVE_ZERO ? 'pos' : 'off', Fn: fmt_hr_s } : 
    props.unit=="deg_ofst"  ? { color: v<BELOW_ZERO ? 'haz' : v>ABOVE_ZERO ? 'pos' : 'off', Fn: fmt_deg } : 
    props.unit=="hr_ofst"   ? { color: v<BELOW_ZERO ? 'haz' : v>ABOVE_ZERO ? 'pos' : 'off', Fn: fmt_hr } : 
                              { color: 'std', Fn: fmt_deg }
  )
})

</script>

<style lang="scss">
  .terminal {
    font-family: monospace;
    white-space: pre;
  }

  .std {
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
</style>