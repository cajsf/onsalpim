import { useCallback, useEffect, useRef, useState } from 'react';

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  deps: unknown[],
  intervalMs = 4000,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const fetchRef = useRef(fetchFn);
  fetchRef.current = fetchFn;

  const refresh = useCallback(async () => {
    try {
      const next = await fetchRef.current();
      setData(next);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function tick() {
      try {
        const next = await fetchRef.current();
        if (!cancelled) {
          setData(next);
          setError('');
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps are caller-controlled keys
  }, [intervalMs, refresh, ...deps]);

  return { data, error, loading, refresh };
}
