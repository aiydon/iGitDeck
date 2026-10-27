import { useCallback, useEffect, useState } from "react";

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

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    loader()
      .then((result) => {
        if (!active) return;
        setData(result);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(errorMessage(cause));
        setLoading(false);
      });
    return () => {
      active = false;
    };
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
