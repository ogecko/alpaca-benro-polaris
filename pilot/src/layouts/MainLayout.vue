<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated>
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="Menu" to="/connect" />

        <q-toolbar-title> Alpaca Pilot </q-toolbar-title>

        <div>Pilot v2.0.0</div>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">

// function toggleLeftDrawer() {
//   // Nothing yet  
// }

</script>
