<template>
  <div class="fullscreen dark-page text-white text-center q-pa-md flex flex-center">
    <div>
      <div class="flash" style="font-size: 20vb">404</div>

      <div class="text-h3" style="opacity: 0.4">Oops. Nothing here...</div>

      <q-btn
        class="q-mt-xl"
        color="primary"
        unelevated
        to="/"
        label="Go Home"
        no-caps
      />
    </div>
  </div>
</template>

<script setup lang="ts">
//
</script>

<style lang="scss">
.flash {
  animation: flash .6s;
}

</style>