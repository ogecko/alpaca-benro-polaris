<template>
  <div class="mount-controller">
    <div class="control-grid">

      <!-- Row 1 -->
      <q-btn outline size="xl" color="primary" icon="mdi-home" @click="sendCommand('home')" />
      <q-btn rounded size="xl" color="primary" icon="mdi-arrow-down-left-bold" @mousedown="startMove('ccw')" @mouseup="stopMove" @mouseleave="stopMove" />
      <q-btn rounded size="xl" color="primary" icon="mdi-arrow-up-bold" @mousedown="startMove('north')" @mouseup="stopMove" @mouseleave="stopMove" />
      <q-btn rounded size="xl" color="primary" icon="mdi-arrow-down-right-bold" @mousedown="startMove('cw')" @mouseup="stopMove" @mouseleave="stopMove" />

      <!-- Row 2 -->
      <q-btn outline size="xl" color="primary" icon="mdi-parking" @click="sendCommand('park')" />
      <q-btn rounded size="xl" color="primary" icon="mdi-arrow-left-bold" @mousedown="startMove('west')" @mouseup="stopMove" @mouseleave="stopMove" />
      <div class="knob-container"> 
        <q-knob v-model="speed" :min="0" :inner-min="1" :inner-max="9" :max="10" size="80px" show-value color="positive" track-color="grey-7" /> 
        <div  class="text-caption text-positive q-mt-xs">Speed</div>
      </div>
      <q-btn rounded size="xl" color="primary" icon="mdi-arrow-right-bold" @mousedown="startMove('east')" @mouseup="stopMove" @mouseleave="stopMove" />


      <!-- Row 3 -->
      <q-btn outline size="xl" color="negative" icon="mdi-stop" @click="sendCommand('stop')" />
      <q-btn outline size="xl" color="secondary" icon="mdi-star-shooting-outline" @click="sendCommand('track')" />
      <q-btn rounded size="xl" color="primary" icon="mdi-arrow-down-bold" @mousedown="startMove('south')" @mouseup="stopMove" @mouseleave="stopMove" />
      <q-btn outline size="xl" color="primary" icon="mdi-format-vertical-align-center" @click="sendCommand('level')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const speed = ref(5)

function sendCommand(command:string) {
  console.log(command)
  // emit to mount driver
}

function startMove(direction:string) {
  console.log('move', direction, 'speed', speed.value)
  // start slew
}

function stopMove() {
  console.log('stop movement')
  // stop slew
}
</script>

<style scoped>
.mount-controller {
  display: flex;
  justify-content: center;
  padding: 16px;
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(4, 100px);
  grid-template-rows: repeat(3, 100px);
  gap: 6px;
  align-items: center;
  justify-items: center;
}

.knob-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>