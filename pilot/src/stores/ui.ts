// src/stores/ui.ts
import { defineStore } from 'pinia'

export const useUIStore = defineStore('ui', {
  state: () => ({
    coordFrame: parseInt(sessionStorage.getItem('ui.coordFrame') ?? '0') as 0 | 1 | 2,
  }),
  actions: {
    setCoordFrame(val: 0 | 1 | 2) {
      this.coordFrame = val
      sessionStorage.setItem('ui.coordFrame', String(val))
    },
    cycleCoordFrame() {
      const newval = ((this.coordFrame + 1) % 3) as 0 | 1 | 2
      this.coordFrame = newval
      sessionStorage.setItem('ui.coordFrame', String(newval))
    }
  }
})