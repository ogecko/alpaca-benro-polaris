<template>
  <q-btn
    dense push size="lg" style="opacity:0.4" 
    :icon="icon"
    :class="{ isPressed }"
    :text-color="isPressed? 'white' : 'positive'"
    :color="isPressed? 'positive' : ''"
    :style="isPressed? 'opacity: 1' : 'opacity: 0.4'"
    @mousedown="onDown"
    @mouseup="onUp"
    @mouseleave="onUp"
    @touchstart="onDown"
    @touchend="onUp"
    class="q-mx-xs"
  />
</template>

<script setup lang="ts">
import { ref, defineProps, defineEmits } from 'vue'

defineProps({
  icon: { type: String, default: 'mdi-plus-circle' },
})

const isPressed = ref(false)

// events that can be emitted
type PushEvents = {
  (e: 'push', payload: { isPressed: boolean }): void
}
const emit = defineEmits<PushEvents>()


function onDown() {
  isPressed.value = true
  emit('push', { isPressed: true})
}

function onUp() {
  if (isPressed.value) {
    isPressed.value = false
    emit('push', { isPressed: false})
  }
}
</script>

<style lang="scss" scoped>

</style>