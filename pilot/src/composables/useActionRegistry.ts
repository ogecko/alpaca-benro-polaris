import type { ActionRegistry } from './types';
import { useDeviceStore } from 'src/stores/device'
import { useStatusStore } from 'src/stores/status'

let registry: ActionRegistry | null = null;

/**
 * The fixed set of actions this app exposes — to keyboard, on-screen
 * buttons, or anything else. Built once and memoized: it never changes
 * at runtime, only what's *bound* to it (the keymap) does.
 *
 * Must be called the first time from within an active Pinia context
 * (a component's setup()), since it constructs useMountStore(). After
 * that first call the cached object is returned everywhere, so it's
 * safe to call from as many components as you like — e.g. useKeyHandler
 * and an on-screen "N" button both call useActionRegistry() and get the
 * same slewNorth action.
 */
export function useActionRegistry(): ActionRegistry {
  if (registry) return registry;

  const dev = useDeviceStore()
  const p = useStatusStore()

  registry = {
    slewNorth: {
      type: 'momentary',
      onStart: () => console.log('mount: start slew N'),
      onStop: () => console.log('mount: stop slew N'),
    },
    slewSouth: {
      type: 'momentary',
      onStart: () => console.log('mount: start slew S'),
      onStop: () => console.log('mount: stop slew S'),
    },
    toggleTracking: {
      type: 'toggle',
      getState: () => p.tracking,
      onToggle: async (next) => { await dev.alpacaTracking(next); },
    },
    syncHere: {
      type: 'trigger',
      onFire: () => console.log('mount: sync'),
    },

    // Add more actions here as the app grows — this is the one place
    // to look for "what can be bound to a key or a button".
  };

  return registry;
}