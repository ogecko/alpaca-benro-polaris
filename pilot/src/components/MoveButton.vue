<template>
  <q-btn
     push size="lg" style="opacity:opacity" 
    :class="{ isPressed }"
    :text-color="isPressed? icolor : iupcolor"
    :color="isPressed? color : upcolor"
    :style="isPressed? 'opacity: 1' : `opacity: ${opacity}`"
    @pointerdown="onDown"
    @pointerup="onUp"
    @pointerleave="onUp"
    class="q-mx-xs"
  >
    <q-icon v-if="icon!=''" :name="icon" />
    <div v-if="label!=''"> {{ label }} </div>
  </q-btn>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps({
  icon: { type: String, default: 'mdi-plus-circle' },
  opacity: { type: Number, default: 0.4 },
  label: { type: String, default: '' },
  color: { type: String, default: 'positive' },
  upcolor: { type: String, default: '' },
  icolor: { type: String, default: 'white' },
  iupcolor: { type: String, default: 'positive' }
})

const isPressed = ref(false)

type PushEvents = {
  (e: 'push', payload: { isPressed: boolean }): void
}
const emit = defineEmits<PushEvents>()

function onDown(e: PointerEvent) {
  e.preventDefault() // optional: prevents unwanted text selection on long-press
  isPressed.value = true
  emit('push', { isPressed: true })
}

function onUp() {
  if (isPressed.value) {
    isPressed.value = false
    emit('push', { isPressed: false })
  }
}
</script>

<style lang="scss" scoped>

</style>