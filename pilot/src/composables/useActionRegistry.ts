import type { ActionRegistry } from './types';
import { useDeviceStore } from 'src/stores/device';
import { useStatusStore } from 'src/stores/status';
import { useUIStore } from 'src/stores/ui';
import { useConfigStore } from 'src/stores/config';
import { computed } from 'vue';
import { useRouter } from 'vue-router';

let registry: ActionRegistry | undefined;

const axisMap: Record<number, string> = {
  0: 'Azimuth',
  1: 'Altitude',
  2: 'Roll',
  3: 'Right Ascension',
  4: 'Declination',
  5: 'Position Angle',
  6: 'Galactic Lon',
  7: 'Galactic Lat',
  8: 'Galactic PA',
};

function getAxisName(axis: number): string {
  return axisMap[axis] ?? 'Azimuth';
}

/**
 * The fixed set of actions this app exposes — to keyboard, on-screen
 * buttons, or anything else. Built once and memoized: it never changes
 * at runtime, only what's *bound* to it (the keymap) does.
 *
 * Everything that needs an active Vue/Pinia/Router context (stores,
 * useRouter, computed) is created *inside* this function, on first call,
 * not at module scope
 */
export function useActionRegistry(): ActionRegistry {
  if (!registry) {
    const dev = useDeviceStore();
    const p = useStatusStore();
    const ui = useUIStore();
    const cfg = useConfigStore();
    const router = useRouter();

    const centerPanel = computed(() => Math.floor((cfg.rows * cfg.cols + 1) / 2));

    async function moveAxis(axistriad: number, direction: number): Promise<void> {
      const axis = (axistriad % 3) + (ui.coordFrame ?? 0) * 3;
      const axisName = getAxisName(axis);
      const maxScale = axis !== 3 ? 200 : 12;
      const scale = ui.getScaleRange(axisName, maxScale);
      const rate = (direction * scale / maxScale) * 9;
      if (axis >= 0 && axis <= 8) {
        await dev.apiAction('Polaris:MoveAxis', `{"axis":${axis},"rate":${rate}}`);
      }
    }

    function setMoveSpeed(speed: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9): void {
      for (let axistriad = 0; axistriad < 3; axistriad++) {
        const axis = (axistriad % 3) + (ui.coordFrame ?? 0) * 3;
        const axisName = getAxisName(axis);
        const maxScale = axis !== 3 ? 200 : 12;
        const minScale = axis !== 3 ? 2 / 60 : 1 / 60;
        const t = (speed - 1) / (9 - 1); // 0..1
        const range = minScale * Math.pow(maxScale / minScale, t);
        ui.setScaleRange(axisName, range);
      }
    }

    registry = {
        referenceFrame: {
        type: 'trigger',
        onFire: () => ui.cycleCoordFrame(),
      },
      resetSP: {
        type: 'trigger',
        onFire: async () => { await dev.alpacaResetSP(); },
      },
      findHome: {
        type: 'trigger',
        onFire: async () => { await dev.alpacaFindHome(); },
      },
      togglePark: {
        type: 'trigger',
        onFire: async () => {
          if (p.atpark) { await dev.alpacaUnPark(); } else { await dev.alpacaPark(); }
        },
      },
      abortSlew: {
        type: 'trigger',
        onFire: async () => { await dev.alpacaAbortSlew(); },
      },
      toggleTracking: {
        type: 'toggle',
        getState: () => p.tracking,
        onToggle: async (next) => { await dev.alpacaTracking(next); },
      },
      centerGrid: {
        type: 'trigger',
        onFire: async () => {
          await dev.alpacaPanoGrid(`{"anchor":0, "ref_action":"update", "panel": ${centerPanel.value}}`);
        },
      },
      moveLeft: {
        type: 'momentary',
        onStart: async () => moveAxis(0, -1),
        onStop: async () => moveAxis(0, 0),
      },
      moveRight: {
        type: 'momentary',
        onStart: async () => moveAxis(0, 1),
        onStop: async () => moveAxis(0, 0),
      },
      moveUp: {
        type: 'momentary',
        onStart: async () => moveAxis(1, 1),
        onStop: async () => moveAxis(1, 0),
      },
      moveDown: {
        type: 'momentary',
        onStart: async () => moveAxis(1, -1),
        onStop: async () => moveAxis(1, 0),
      },
      moveCW: {
        type: 'momentary',
        onStart: async () => moveAxis(2, 1),
        onStop: async () => moveAxis(2, 0),
      },
      moveCCW: {
        type: 'momentary',
        onStart: async () => moveAxis(2, -1),
        onStop: async () => moveAxis(2, 0),
      },
      speed1: { type: 'trigger', onFire: () => setMoveSpeed(1) },
      speed2: { type: 'trigger', onFire: () => setMoveSpeed(2) },
      speed3: { type: 'trigger', onFire: () => setMoveSpeed(3) },
      speed4: { type: 'trigger', onFire: () => setMoveSpeed(4) },
      speed5: { type: 'trigger', onFire: () => setMoveSpeed(5) },
      speed6: { type: 'trigger', onFire: () => setMoveSpeed(6) },
      speed7: { type: 'trigger', onFire: () => setMoveSpeed(7) },
      speed8: { type: 'trigger', onFire: () => setMoveSpeed(8) },
      speed9: { type: 'trigger', onFire: () => setMoveSpeed(9) },
      dashboard: {
        type: 'trigger',
        onFire: async () => { await router.push('/dashboard'); },
      },
      connect: {
        type: 'trigger',
        onFire: async () => { await router.push('/connect'); },
      },
      settings: {
        type: 'trigger',
        onFire: async () => { await router.push('/config'); },
      },
      alignment: {
        type: 'trigger',
        onFire: async () => { await router.push('/sync'); },
      },
      log: {
        type: 'trigger',
        onFire: async () => { await router.push({ path: '/log' }); },
      },
      nearby: {
        type: 'trigger',
        onFire: async () => { await router.push({ path: '/catalog', query: { sort: 'Proximity' } }); },
      },

      // Add more actions here as the app grows — this is the one place
      // to look for "what can be bound to a key or a button".
    };
  }

  return registry;
}