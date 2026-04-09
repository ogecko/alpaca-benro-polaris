<template>
  <span class="terminal std"><span class="ok">{{label}}</span><span :class="fmt.color">{{fmt.Fn(val)}}</span></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { deg2dms } from 'src/utils/angles'
import type { UnitKey } from 'src/utils/angles'


const props = defineProps<{
  label: string
  val: number | string | undefined  
  unit: string
}>()

function toNumber(x: unknown, fallback = 0): number {
  if (typeof x === 'number') return x
  if (typeof x === 'string') {
    const n = Number(x)
    return isNaN(n) ? fallback : n
  }
  return fallback
}

function toStringSafe(x: unknown): string {
  if (typeof x === 'string') return x
  if (typeof x === 'number' || typeof x === 'boolean' || typeof x === 'bigint')
    return String(x)
  if (x == null) return ''
  return ''   // do NOT stringify objects
}

function fmt_deg(x: unknown, unit:UnitKey="deg"): string {
  const n = toNumber(x)
  const s = deg2dms(n, 1, unit)
  return `${s.sign}${s.degreestr}${s.minutestr}${s.secondstr}`
}
function fmt_hr(x: unknown, unit:UnitKey="hr"): string {
  const n = toNumber(x)
  return fmt_deg(n, unit)
}
function fmt_deg2hr(x: unknown, unit:UnitKey="hr"): string {
  const n = toNumber(x)  
  return fmt_deg(n / 15, unit)
}

function fmt_deg_s(x: unknown, unit:UnitKey="deg"): string {
  const velocity = toNumber(x)
  const str = fmt_deg(velocity, unit).replace(/^[+-]/, '')
  const sign = (velocity>0.5/3600) ? '▲' : (velocity<-0.5/3600) ? '▼' : ' '
  const signed_str = sign + str + '/s'
  return signed_str
}
function fmt_hr_s(x: unknown, unit:UnitKey="hr"): string {
  const n = toNumber(x)
  return fmt_deg_s(n, unit)
}

function fmt_number(x: unknown, decimals:number=7): string {
  const n = toNumber(x)
  const sign = n < 0 ? '-' : '+';
  const nstr = Math.abs(n).toFixed(decimals)
  return sign+nstr
}

function fmt_string(x: unknown): string {
  return toStringSafe(x)
}

const BELOW_ZERO = -0.5/3600
const ABOVE_ZERO = +0.5/3600
function col_deviation(v:number) {
  return v<BELOW_ZERO ? 'haz' : v>ABOVE_ZERO ? 'pos' : 'off'
}

const fmt = computed(() => {
  const v = toNumber(props.val)
  return (
    props.unit=="string"    ? { color: 'std', Fn: fmt_string } : 
    props.unit=="number"    ? { color: 'std', Fn: fmt_number } : 
    props.unit=="deg"       ? { color: 'std', Fn: fmt_deg } : 
    props.unit=="deg2hr"    ? { color: 'std', Fn: fmt_deg2hr } : 
    props.unit=="hr"        ? { color: 'std', Fn: fmt_hr } : 
    props.unit=="deg/s"     ? { color: col_deviation(v), Fn: fmt_deg_s } : 
    props.unit=="hr/s"      ? { color: col_deviation(v), Fn: fmt_hr_s } : 
    props.unit=="deg_ofst"  ? { color: col_deviation(v), Fn: fmt_deg } : 
    props.unit=="hr_ofst"   ? { color: col_deviation(v), Fn: fmt_hr } : 
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