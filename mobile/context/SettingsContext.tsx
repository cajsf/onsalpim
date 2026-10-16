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
const TOKEN_KEY = '@onsalpim/staffToken';

type SettingsContextValue = {
  apiBase: string;
  api: ApiClient;
  ready: boolean;
  worker: string;
  staffToken: string;
  setApiBase: (raw: string) => Promise<void>;
  setWorker: (raw: string) => Promise<void>;
  loginStaff: (code: string) => Promise<string>;
  logoutStaff: () => Promise<void>;
};

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [apiBase, setApiBaseState] = useState(defaultApiBase());
  const [worker, setWorkerState] = useState('복지사');
  const [staffToken, setStaffTokenState] = useState('');
  const [ready, setReady] = useState(false);

  const logoutStaff = useCallback(async () => {
    const current = staffToken;
    setStaffTokenState('');
    try {
      await AsyncStorage.removeItem(TOKEN_KEY);
    } catch {
      /* 저장소 불가면 이번 실행만 끊긴다 */
    }
    if (current) {
      try {
        await createApi(apiBase, current).logoutStaff();
      } catch {
        /* 서버 세션은 시간이 지나면 사라진다 */
      }
    }
  }, [apiBase, staffToken]);

  useEffect(() => {
    (async () => {
      try {
        const [saved, savedWorker, savedToken] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEY),
          AsyncStorage.getItem(WORKER_KEY),
          AsyncStorage.getItem(TOKEN_KEY),
        ]);
        if (saved) setApiBaseState(resolveApiBase(saved));
        if (savedWorker?.trim()) setWorkerState(savedWorker.trim().slice(0, 40));
        if (savedToken) setStaffTokenState(savedToken);
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

  const api = useMemo(
    () => createApi(apiBase, staffToken, () => { void logoutStaff(); }),
    [apiBase, staffToken, logoutStaff],
  );

  const loginStaff = useCallback(async (code: string) => {
    const client = createApi(apiBase);
    const r = await client.loginStaff(code);
    if (r.required && !r.token) throw new Error('접속 코드가 맞지 않습니다.');
    const next = r.token || '';
    setStaffTokenState(next);
    if (next) await AsyncStorage.setItem(TOKEN_KEY, next);
    else await AsyncStorage.removeItem(TOKEN_KEY);
    return next ? '접속했습니다.' : '이 서버는 접속 코드 없이 열려 있습니다.';
  }, [apiBase]);

  const value = useMemo(
    () => ({ apiBase, api, ready, worker, staffToken, setApiBase, setWorker, loginStaff, logoutStaff }),
    [apiBase, api, ready, worker, staffToken, setApiBase, setWorker, loginStaff, logoutStaff],
  );

  return (
    <SettingsContext.Provider value={value}>
      {ready ? children : null}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
