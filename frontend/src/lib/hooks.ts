import { useCallback, useEffect, useRef, useState } from "react";

import { errorMessage } from "./format";

export interface RequestState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useRequest<T>(
  loader: () => Promise<T>,
  deps: readonly unknown[],
): RequestState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const hasData = useRef(false);
  const requestId = useRef(0);

  useEffect(() => {
    // Responses may resolve out of order during polling; only the newest wins.
    requestId.current += 1;
    const current = requestId.current;
    setLoading(!hasData.current);
    setError(null);
    loader()
      .then((result) => {
        if (current !== requestId.current) return;
        hasData.current = true;
        setData(result);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (current !== requestId.current) return;
        setError(errorMessage(cause));
        setLoading(false);
      });
    // The caller owns the dependency list; loader is intentionally not included.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const refresh = useCallback(() => setVersion((value) => value + 1), []);
  return { data, loading, error, refresh };
}

export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export interface LiveRefreshOptions {
  fastIntervalMs?: number;
  slowIntervalMs?: number;
  slowAfterMs?: number;
}

/**
 * Poll only while `enabled` and the tab is visible.
 *
 * Long syncs (multi-GB clones) would otherwise keep hitting the API in a
 * background tab forever, flooding access logs for nothing.
 */
export function useLiveRefresh(
  enabled: boolean,
  refresh: () => void,
  {
    fastIntervalMs = 4000,
    slowIntervalMs = 10000,
    slowAfterMs = 60000,
  }: LiveRefreshOptions = {},
): void {
  useEffect(() => {
    if (!enabled) return;
    const startedAt = Date.now();
    let timer = 0;

    const schedule = () => {
      const elapsed = Date.now() - startedAt;
      const interval = elapsed < slowAfterMs ? fastIntervalMs : slowIntervalMs;
      timer = window.setTimeout(tick, interval);
    };

    const tick = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
      schedule();
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };

    schedule();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [enabled, refresh, fastIntervalMs, slowIntervalMs, slowAfterMs]);
}


/** Re-render on an interval so relative times stay fresh. */
export function useNow(intervalMs = 15_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}
