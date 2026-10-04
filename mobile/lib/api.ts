import type {
  AbsenceRecord,
  ActionStatus,
  AlertRecord,
  CareResponse,
  DeviceTree,
  EngineStatus,
  MonthlyReportRow,
  PreviewResult,
  RuleRecord,
} from './types';

/** Render Static(care) 와 API(api) 는 호스트가 다르다. 잘못된 env 는 404 로 이어진다. */
export const FALLBACK_API_BASE = 'https://onsalpim-api.onrender.com/api';

export function normalizeApiBase(raw: string): string {
  const t = raw.trim().replace(/\/+$/, '');
  if (!t) throw new Error('API 주소가 비어 있습니다.');
  return t.endsWith('/api') ? t : `${t}/api`;
}

/** http(s) URL 이고 경로가 /api 로 끝나야 한다. 로컬 경로·care URL 등은 거절. */
export function isValidApiBase(raw: string): boolean {
  try {
    const normalized = normalizeApiBase(raw);
    const u = new URL(normalized);
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return false;
    if (!u.pathname.endsWith('/api')) return false;
    if (u.hostname.includes('onsalpim-care')) return false;
    return true;
  } catch {
    return false;
  }
}

export function resolveApiBase(candidate: string | null | undefined): string {
  const c = candidate?.trim();
  if (c && isValidApiBase(c)) return normalizeApiBase(c);
  return FALLBACK_API_BASE;
}

export function defaultApiBase(): string {
  return resolveApiBase(process.env.EXPO_PUBLIC_API_BASE);
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
    getRules: () => request<RuleRecord[]>('/rules'),
    getDevices: (force = false) =>
      request<DeviceTree[]>(`/devices${force ? '?force=1' : ''}`),
    getMonthlyReport: (month: string, minS: number) =>
      request<{ month: string; min_s: number; rows: MonthlyReportRow[] }>(
        `/report/monthly?month=${encodeURIComponent(month)}&min_s=${minS}`,
      ),
    getAbsences: (home: string) =>
      request<AbsenceRecord[]>(`/absences?home=${encodeURIComponent(home)}`),
    async addAbsence(body: { home: string; start: string; end: string; reason: string }) {
      const res = await fetch(`${BASE}/absences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] })) as Promise<{
        ok: boolean;
        errors?: string[];
        absence?: AbsenceRecord;
      }>;
    },
    async endAbsence(id: number) {
      const res = await fetch(`${BASE}/absences/${id}/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] }));
    },
    async previewRule(id: number, value?: string, replace = false, days = 14) {
      const res = await fetch(`${BASE}/rules/${id}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...(value === undefined || value === '' ? {} : { value }),
          replace,
          days,
        }),
      });
      return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] })) as Promise<
        PreviewResult
      >;
    },
    async approveRule(id: number, value?: string, replace = false) {
      const res = await fetch(`${BASE}/rules/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...(value === undefined || value === '' ? {} : { value }),
          replace,
        }),
      });
      return res.json().catch(() => ({})) as Promise<{ ok?: boolean; errors?: string[] }>;
    },
    async rejectRule(id: number) {
      const res = await fetch(`${BASE}/rules/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      return res.json().catch(() => ({})) as Promise<{ ok?: boolean; errors?: string[] }>;
    },
  };
}

export type ApiClient = ReturnType<typeof createApi>;
