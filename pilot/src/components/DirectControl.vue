<template>
  <div class="mount-controller">
    <div class="control-grid">

      <!-- Row 1 -->
      <q-btn outline size="xl" color="primary" icon="mdi-home" @click="sendCommand('home')" />
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-down-left-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:2, dir: -1})"/>
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-up-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:1, dir: +1})"/>
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-down-right-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:2, dir: +1})"/>

      <!-- Row 2 -->
      <q-btn outline size="xl" color="primary" icon="mdi-parking" @click="sendCommand('park')" />
      <div class="btn-container"> 
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-left-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:0, dir: -1})"/>
        <div  class="text-caption text-grey-8 q-mt-xs">-ve Azimuth</div>
      </div>
        <div class="btn-container"> 
        <q-knob v-model="speed" :min="0" :inner-min="1" :inner-max="9" :max="10" size="80px" show-value color="positive" track-color="grey-7" /> 
        <div  class="text-caption text-positive q-mt-xs">Speed</div>
      </div>
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-right-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:0, dir: +1})"/>


      <!-- Row 3 -->
      <q-btn outline size="xl" color="negative" icon="mdi-stop" @click="sendCommand('stop')" />
      <q-btn outline size="xl" color="secondary" icon="mdi-star-shooting-outline" @click="sendCommand('track')" />
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-down-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:1, dir: -1})"/>
      <q-btn outline size="xl" color="primary" icon="mdi-format-vertical-align-center" @click="sendCommand('level')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MoveButton from 'src/components//MoveButton.vue'

const speed = ref(5)

function onMove(  payload: { isPressed: boolean, axis: number, dir: number }) {
  const velocity = payload.isPressed ? speed.value * payload.dir : 0
  console.log(payload.axis, velocity)
}


function sendCommand(command:string) {
  console.log(command)
  // emit to mount driver
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

.btn-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>