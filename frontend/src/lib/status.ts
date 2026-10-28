const EVENT = "igideck:status";

/** Tell the shell that repository counts may have changed. */
export function notifyStatusChanged(): void {
  window.dispatchEvent(new Event(EVENT));
}

export function onStatusChanged(handler: () => void): () => void {
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
