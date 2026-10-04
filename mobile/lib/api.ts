import type { ActionStatus, AlertRecord, CareResponse, EngineStatus } from './types';

export function normalizeApiBase(raw: string): string {
  const t = raw.trim().replace(/\/+$/, '');
  if (!t) throw new Error('API 주소가 비어 있습니다.');
  return t.endsWith('/api') ? t : `${t}/api`;
}

export function defaultApiBase(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_BASE?.trim();
  if (fromEnv) return normalizeApiBase(fromEnv);
  return 'https://onsalpim-api.onrender.com/api';
}

export function createApi(base: string) {
  const BASE = normalizeApiBase(base);

  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...(options.headers as Record<string, string>),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg =
        (data as { errors?: string[]; error?: string }).errors?.join(', ') ||
        (data as { error?: string }).error ||
        `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data as T;
  }

  return {
    base: BASE,
    getEngineStatus: () => request<EngineStatus>('/engine/status'),
    getCare: () => request<CareResponse>('/care'),
    getAlerts: (limit = 50) => request<AlertRecord[]>(`/alerts?limit=${limit}`),
    getHistory: (home: string) =>
      request<{ sev: [string, string, string][]; move: unknown[] }>(
        `/history/${encodeURIComponent(home)}`,
      ),
    async actAlert(id: string, status: ActionStatus, memo = '') {
      const res = await fetch(`${BASE}/alerts/${encodeURIComponent(id)}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, memo }),
      });
      return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] })) as Promise<{
        ok: boolean;
        errors?: string[];
        log?: AlertRecord['log'];
      }>;
    },
  };
}

export type ApiClient = ReturnType<typeof createApi>;
