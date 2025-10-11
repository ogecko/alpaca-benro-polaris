<template>
  <q-select :label="props.label" dense multiple  filled map-options  :style="{width:size}" 
    @update:modelValue="val => emit('update:modelValue', val)"
    v-model="localModel" :options="props.options">
      <template v-slot:option="scope">
        <q-item dense clickable @click="scope.toggleOption(scope.opt.value)">
          <q-item-section>{{ scope.opt.label }}</q-item-section>
        </q-item>
      </template>
      <template v-slot:selected-item="scope">
        <q-chip dense removable @remove="scope.removeAtIndex(scope.index)">
          {{ scope.opt.label }}
        </q-chip>
      </template>
  </q-select>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

type SelectOption = { label: string; value: number }

// Props
const props = withDefaults(defineProps<{
  label: string
  size?: string 
  modelValue: number[] | undefined
  options: SelectOption[]
}>(), {
  size: '140px'
})


// Refs
const localModel = ref<number[]>(props.modelValue ?? [])

const emit = defineEmits<{
  (e: 'update:modelValue', value: number[]): void
}>()

watch(() => props.modelValue, val => {
  if (val !== undefined) localModel.value = val
})

watch(localModel, val => {
  emit('update:modelValue', val)
})

</script>
