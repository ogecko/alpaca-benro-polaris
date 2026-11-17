<template>
  <div class="mount-controller">
    <div class="control-grid">

      <!-- Row 1 -->
      <q-btn outline size="xl" color="primary" icon="mdi-arrow-all" @click="sendCommand('coord')" />
      <q-btn outline size="xl" color="primary" icon="mdi-telescope" @click="sendCommand('coord')" />
      <q-btn outline split size="xl" color="secondary" icon="mdi-star-shooting-outline" @click="sendCommand('track')" />
      <q-btn outline size="xl" color="primary" icon="mdi-home" @click="sendCommand('home')" />
      <q-btn outline size="xl" color="primary" icon="mdi-stop" @click="sendCommand('stop')" />
      <!-- Row 2 -->
      <q-btn outline size="xl" color="primary" icon="mdi-move-resize-variant" @click="sendCommand('Goto')" />
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-down-left-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:2, dir: -1})"/>
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-up-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:1, dir: +1})"/>
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-down-right-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:2, dir: +1})"/>
      <q-btn outline size="xl" color="primary" icon="mdi-parking" @click="sendCommand('park')" />

      <!-- Row 3 -->
      <div class="btn-container"> 
        <q-btn outline split size="xl" color="green" icon="mdi-sync" @click="sendCommand('sync')" />
        <div  class="text-caption text-positive q-mt-xs">Artares</div>
      </div>
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-left-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:0, dir: -1})"/>
      <div class="btn-container"> 
        <q-knob v-model="speed" :min="0" :inner-min="1" :inner-max="9" :max="10" size="80px" show-value color="positive" track-color="grey-7" /> 
        <div  class="text-caption text-positive q-mt-xs">Speed</div>
      </div>
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-right-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:0, dir: +1})"/>
      <q-btn outline size="xl" color="primary" icon="mdi-cryengine" @click="sendCommand('glat0')" />

      <!-- Row 4 -->
      <q-btn outline size="xl" color="primary" icon="mdi-globe-model" @click="sendCommand('mpa')" />
      <q-btn outline size="xl" color="primary" icon="mdi-format-align-middle" @click="sendCommand('level')" />
      <MoveButton rounded size="xl" :opacity="0.8" icon="mdi-arrow-down-bold" color="positive" upcolor="primary" iupcolor="white" @push="e=>onMove({...e, axis:1, dir: -1})"/>
      <q-btn outline split size="xl" color="primary"  label="RA-2" @click="sendCommand('ram2')" />
      <q-btn outline split size="xl" color="primary"  label="RA+2" @click="sendCommand('rap2')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MoveButton from 'src/components/MoveButton.vue'

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
  grid-template-columns: repeat(5, 100px);
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