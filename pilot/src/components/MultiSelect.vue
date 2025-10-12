<template>
  <q-select :label="props.label" dense multiple  filled map-options :style="{width:size}" 
    @update:modelValue="val => emit('update:modelValue', val)"
    v-model="localModel" :options="props.options">
      <template v-slot:option="scope">
        <q-item dense clickable @click="scope.toggleOption(scope.opt.value)">
          <q-item-section>{{ scope.opt.label }}</q-item-section>
        </q-item>
      </template>
      <template v-slot:selected-item="scope">
        <q-chip :color='enrichedColor(scope.opt.value)' class="text-caption" dense removable @remove="scope.removeAtIndex(scope.index)">
          {{ scope.opt.label }}
        </q-chip>
      </template>
  </q-select>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

type SelectOption = { label: string; value: number }

// ------ Props and Events
const props = withDefaults(defineProps<{
  label: string
  size?: string 
  color?: string
  modelValue: number[] | undefined
  options: SelectOption[]
}>(), {
  size: '180px'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number[]): void
}>()

// ----- Refs
const localModel = ref<number[]>(props.modelValue ?? [])


// ----- Watches

watch(() => props.modelValue, val => {
  localModel.value = val ?? []
})

watch(localModel, val => {
  emit('update:modelValue', val)
})

// ----- helpers
function enrichedColor(val:number) {
  // Special case for Altitude chips
  if (props.label == 'Altitude') {
    if (val == 0) return 'negative'
    if (val == 1) return 'warning'
    if (val == 6) return 'negative'
  }

  return props.color;
}



</script>
