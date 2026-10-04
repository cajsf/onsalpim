import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { createApi, defaultApiBase, normalizeApiBase, type ApiClient } from '@/lib/api';

const STORAGE_KEY = '@onsalpim/apiBase';

type SettingsContextValue = {
  apiBase: string;
  api: ApiClient;
  ready: boolean;
  setApiBase: (raw: string) => Promise<void>;
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [apiBase, setApiBaseState] = useState(defaultApiBase());
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const saved = await AsyncStorage.getItem(STORAGE_KEY);
        if (saved) setApiBaseState(normalizeApiBase(saved));
      } catch {
        /* 저장소 불가면 env/기본값 */
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const setApiBase = useCallback(async (raw: string) => {
    const next = normalizeApiBase(raw);
    setApiBaseState(next);
    await AsyncStorage.setItem(STORAGE_KEY, next);
  }, []);

  const api = useMemo(() => createApi(apiBase), [apiBase]);

  const value = useMemo(
    () => ({ apiBase, api, ready, setApiBase }),
    [apiBase, api, ready, setApiBase],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
