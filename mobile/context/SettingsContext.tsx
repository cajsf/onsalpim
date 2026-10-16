import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import {
  createApi,
  defaultApiBase,
  isValidApiBase,
  normalizeApiBase,
  resolveApiBase,
  type ApiClient,
} from '@/lib/api';

const STORAGE_KEY = '@onsalpim/apiBase';
const WORKER_KEY = '@onsalpim/worker';

type SettingsContextValue = {
  apiBase: string;
  api: ApiClient;
  ready: boolean;
  worker: string;
  setApiBase: (raw: string) => Promise<void>;
  setWorker: (raw: string) => Promise<void>;
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [apiBase, setApiBaseState] = useState(defaultApiBase());
  const [worker, setWorkerState] = useState('복지사');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [saved, savedWorker] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEY),
          AsyncStorage.getItem(WORKER_KEY),
        ]);
        if (saved) setApiBaseState(resolveApiBase(saved));
        if (savedWorker?.trim()) setWorkerState(savedWorker.trim().slice(0, 40));
      } catch {
        /* 저장소 불가면 env/기본값 */
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const setApiBase = useCallback(async (raw: string) => {
    if (!isValidApiBase(raw)) {
      throw new Error(
        'https://onsalpim-api.onrender.com/api 처럼 API 서버 주소를 넣어 주세요. (care·dashboard URL 은 안 됩니다)',
      );
    }
    const next = normalizeApiBase(raw);
    setApiBaseState(next);
    await AsyncStorage.setItem(STORAGE_KEY, next);
  }, []);

  const setWorker = useCallback(async (raw: string) => {
    const next = raw.trim().slice(0, 40) || '복지사';
    setWorkerState(next);
    await AsyncStorage.setItem(WORKER_KEY, next);
  }, []);

  const api = useMemo(() => createApi(apiBase), [apiBase]);

  const value = useMemo(
    () => ({ apiBase, api, ready, worker, setApiBase, setWorker }),
    [apiBase, api, ready, worker, setApiBase, setWorker],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
