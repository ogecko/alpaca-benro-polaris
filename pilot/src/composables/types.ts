/**
 * Three action shapes cover almost everything a hardware control UI needs:
 *
 * - momentary: active only while the key is held (e.g. slew north).
 *              Needs onStart/onStop and real keydown/keyup edge detection.
 * - toggle:    flips a boolean state on each press (e.g. tracking on/off).
 * - trigger:   fires once per press, ignores OS key-repeat (e.g. sync here).
 *
 * Callbacks may be sync or async (e.g. an awaited call to the mount driver
 * API) — the `void | Promise<void>` return type makes that explicit so
 * @typescript-eslint/no-misused-promises doesn't flag async handlers.
 */

export interface MomentaryAction {
  type: 'momentary';
  onStart: () => void | Promise<void>;
  onStop: () => void | Promise<void>;
}

export interface ToggleAction {
  type: 'toggle';
  /** Source of truth for current state — typically a Pinia getter/storeToRefs value. */
  getState: () => boolean;
  onToggle: (next: boolean) => void | Promise<void>;
}

export interface TriggerAction {
  type: 'trigger';
  onFire: () => void | Promise<void>;
}

export type ActionDef = MomentaryAction | ToggleAction | TriggerAction;

/** actionId -> action definition. Registered once, independent of keys. */
export type ActionRegistry = Record<string, ActionDef>;

/**
 * KeyboardEvent.key -> actionId.
 * Deliberately plain data (no functions) so it can be JSON-serialized,
 * sent to/from a server, and edited by a rebinding UI.
 */
export type KeyMap = Record<string, string>;