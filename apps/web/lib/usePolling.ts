"use client";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/** Load data once, then re-load every `intervalMs` while `shouldPoll(data)` is true. */
export function usePolling<T>(load: () => Promise<T>, intervalMs: number, shouldPoll: (d: T) => boolean) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadRef = useRef(load);
  const pollRef = useRef(shouldPoll);
  useLayoutEffect(() => {
    // keep the latest callbacks without restarting the polling loop
    loadRef.current = load;
    pollRef.current = shouldPoll;
  });

  const refresh = useCallback(async () => {
    try {
      const d = await loadRef.current();
      setData(d);
      setError(null);
      return d;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, []);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    const tick = async () => {
      const d = await refresh();
      if (alive && (d === null || pollRef.current(d))) timer = setTimeout(tick, intervalMs);
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [refresh, intervalMs]);

  return { data, error, refresh, setData };
}
