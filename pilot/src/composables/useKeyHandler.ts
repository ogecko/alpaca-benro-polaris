import { onBeforeUnmount, onMounted, type Ref } from 'vue';
import { useMagicKeys } from '@vueuse/core';
import type { ActionRegistry, KeyMap } from './types';

function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable;
}

const MODIFIER_KEYS = new Set(['Control', 'Alt', 'Shift', 'Meta']);

/**
 * Builds the keymap lookup id for an event, e.g. "Shift+ArrowUp" or
 * plain "ArrowUp" when no modifiers are held. Order is fixed
 * (Control, Alt, Shift, Meta) so keymap entries are unambiguous —
 * always write combos in that order, e.g. "Control+Shift+S".
 *
 * Single-character keys are lowercased before appending, so a keymap
 * entry only ever needs "Shift+s" (not "Shift+S") — otherwise Shift+S
 * would produce e.key === "S" and silently fail to match "s" combos.
 */
function getKeyId(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey) parts.push('Control');
  if (e.altKey) parts.push('Alt');
  if (e.shiftKey) parts.push('Shift');
  if (e.metaKey) parts.push('Meta');
  if (!MODIFIER_KEYS.has(e.key)) {
    const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    parts.push(key);
  }
  return parts.join('+');
}

/**
 * Action callbacks may be async (e.g. an awaited driver call). We don't
 * await them here — key dispatch has to stay synchronous — but a
 * rejected promise would otherwise vanish as an unhandled rejection.
 * This wraps every call so failures at least reach the console; swap
 * the catch body for a toast/notify call if you want it surfaced in the UI.
 */
function safeCall(fn: () => void | Promise<void>, label: string): void {
  try {
    const result = fn();
    if (result instanceof Promise) {
      result.catch((err: unknown) => {
        console.error(`[useKeyHandler] ${label} failed:`, err);
      });
    }
  } catch (err) {
    console.error(`[useKeyHandler] ${label} failed:`, err);
  }
}

/**
 * Dispatches raw keyboard events against a (possibly reactive/rebindable)
 * keymap and an action registry. Uses useMagicKeys' onEventFired hook
 * rather than per-key watchers, since the keymap is data and can change
 * at runtime (e.g. after loading from the server, or after a rebind).
 *
 * macOS note: avoid binding Meta/Cmd combos to `momentary` actions.
 * Chrome/Safari on macOS suppress keyup events for non-modifier keys
 * while Cmd is held, so a "Meta+ArrowUp" momentary binding can get
 * stuck active if the user releases the arrow key before Cmd. Meta
 * combos are fine for `trigger`/`toggle` actions (no held-state to lose).
 */
export function useKeyHandler(registry: ActionRegistry, keymap: Ref<KeyMap>) {
  // Keyed by e.code (physical key), not the modifier-aware id, so a
  // momentary key still releases correctly even if the user lets go of
  // a modifier (e.g. Shift) before releasing the main key.
  const activeKeys = new Map<string, string>(); // e.code -> actionId

  function releaseAll(): void {
    for (const actionId of activeKeys.values()) {
      const action = registry[actionId];
      if (action?.type === 'momentary') safeCall(action.onStop, `${actionId}.onStop`);
    }
    activeKeys.clear();
  }

  function handleVisibility(): void {
    if (document.hidden) releaseAll();
  }

  useMagicKeys({
    passive: false,
    onEventFired(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return;

      const keyId = getKeyId(e);
      const actionId = keymap.value[keyId];
      if (!actionId) return;
      const action = registry[actionId];
      if (!action) return;

      if (e.type === 'keydown') {
        e.preventDefault();

        if (action.type === 'momentary') {
          if (!activeKeys.has(e.code)) {
            activeKeys.set(e.code, actionId);
            safeCall(action.onStart, `${actionId}.onStart`);
          }
        } else if (action.type === 'trigger') {
          if (!e.repeat) safeCall(action.onFire, `${actionId}.onFire`);
        } else if (action.type === 'toggle') {
          if (!e.repeat) {
            const next = !action.getState();
            safeCall(() => action.onToggle(next), `${actionId}.onToggle`);
          }
        }
      } else if (e.type === 'keyup') {
        const activeActionId = activeKeys.get(e.code);
        if (activeActionId) {
          const activeAction = registry[activeActionId];
          if (activeAction?.type === 'momentary') {
            safeCall(activeAction.onStop, `${activeActionId}.onStop`);
          }
          activeKeys.delete(e.code);
        }
      }
    },
  });

  // Safety net: if the tab loses focus while a key is held (alt-tab, e.g.),
  // we never get the keyup — force-release so the mount doesn't slew forever.
  onMounted(() => {
    window.addEventListener('blur', releaseAll);
    document.addEventListener('visibilitychange', handleVisibility);
  });

  onBeforeUnmount(() => {
    releaseAll();
    window.removeEventListener('blur', releaseAll);
    document.removeEventListener('visibilitychange', handleVisibility);
  });

  return { releaseAll };
}