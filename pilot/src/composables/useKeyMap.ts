import { ref, type Ref } from 'vue';
import type { KeyMap } from './types';
import axios from 'axios'
/**
 * Owns exactly one piece of client state: the current keymap.
 * No localStorage, no merging logic — that's intentional, as
 * the eventual source of truth will be the Python server. Swap loadKeymap's
 * body for a real fetch when that endpoint exists; nothing else changes.
 */
export function useKeyMap(fallback: KeyMap = defaultKeyMap) {
  const current: Ref<KeyMap> = ref({ ...fallback });
  const loaded = ref(false);
  const error = ref<unknown>(null);

  async function loadKeymap(): Promise<void> {
    error.value = null;
    try {
      const { data } = await axios.get<KeyMap>('/api/keymap');
      current.value = data;
      current.value = { ...fallback };
    } catch (e) {
      error.value = e;
      // keep whatever keymap was already loaded/fallback rather than blanking it
    } finally {
      loaded.value = true;
    }
  }

  function setKeymap(next: KeyMap): void {
    current.value = next;
  }

  return { current, loaded, error, loadKeymap, setKeymap };
}

const defaultKeyMap: KeyMap = {
  'ArrowLeft': 'moveLeft',
  'ArrowRight': 'moveRight',
  'ArrowUp': 'moveUp',
  'ArrowDown': 'moveDown',
  ',': 'moveCCW',
  '.': 'moveCW',
  'a': 'moveLeft',
  'd': 'moveRight',
  'w': 'moveUp',
  's': 'moveDown',
  'q': 'moveCCW',
  'e': 'moveCW',
  '1': 'speedSlow',
  '2': 'speed2',
  '3': 'speed3',
  '4': 'speed4',
  '5': 'speed5',
  '6': 'speed6',
  '7': 'speed7',
  '8': 'speed8',
  '9': 'speedFast',
  'r': 'resetSetPoint',
  't': 'toggleTracking',
  'y': 'syncGuiding',
  'u': 'pulseGuiding',    
  'i': 'togglePEC',
  'o': 'planets',
  'p': 'pidTuning',
  'f': 'referenceFrame',
  'g': 'centerGrid',
  'h': 'findHome',
  'j': 'parkUnPark',
  'k': 'skyConditions',
  'l': 'log',
  'z': 'dashboard',
  'x': 'alignment',
  'c': 'connect',
  'v': 'settings',
  'b': 'brightest',
  'n': 'nearby',
  'm': 'toggleMPA',
  ' ': 'abortSlew',
  'Escape': 'abortSlew',
  'Backspace': 'abortSlew',
  'Home': 'findHome',
  'End': 'parkUnPark',
};