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
  ArrowUp: 'slewNorth',
  ArrowDown: 'slewSouth',
  t: 'toggleTracking',
  s: 'syncHere',
};