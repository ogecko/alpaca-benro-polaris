<template>
  <q-fab class="move-fab" push padding="xs"  direction="up" 
        v-model="isOpen" :icon="icon" 
    :text-color="isOpen? 'white' : 'dark'"
    :color="isOpen? 'positive' : 'positive'"
    :style="isOpen? 'opacity: 1' : 'opacity: 0.4'"

>
        <slot />
</q-fab>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps({
  icon: { type: String, default: 'mdi-plus-circle' },
})


const isOpen = ref(false)
</script>

<style scoped>
.move-fab {
  transition: opacity 0.3s ease;
}


</style>
