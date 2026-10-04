/** 대시보드 format.js 와 같은 키·표기 — 화면이 서로 다르게 보이지 않는다. */

export const SEV = {
  NORMAL: { ko: '정상', cls: 'normal' as const },
  WATCH: { ko: '주의', cls: 'watch' as const },
  URGENT: { ko: '긴급 확인', cls: 'urgent' as const },
  CHECK_DEVICE: { ko: '점검 필요', cls: 'device' as const },
};

export const ALERT_STATE: Record<
  string,
  { ko: string; cls: 'urgent' | 'watch' | 'normal' | 'muted' }
> = {
  open: { ko: '대응 필요', cls: 'urgent' },
  missed: { ko: '응답 없이 지나감', cls: 'muted' },
  ack: { ko: '확인', cls: 'watch' },
  progress: { ko: '방문·연락 중', cls: 'watch' },
  done: { ko: '조치 완료', cls: 'normal' },
  late: { ko: '뒤늦게 확인', cls: 'muted' },
  edit: { ko: '메모 수정', cls: 'muted' },
};

export const SEV_ORDER = ['URGENT', 'CHECK_DEVICE', 'WATCH', 'NORMAL'] as const;

export const TYPE_KO: Record<string, string> = {
  motion: '움직임',
  temperature: '온도',
  humidity: '습도',
  battery: '배터리',
  light: '조명',
  window: '창문',
  card: '카드',
};

export function typeKo(t: string | undefined): string {
  return TYPE_KO[t || ''] || t || '?';
}

export function devName(path: string | undefined): string {
  return (path || '').split('/').slice(2).join('/') || path || '';
}

export function secondsSince(iso: string | null | undefined, nowMs: number): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? Math.max(0, (nowMs - t) / 1000) : null;
}

export function fmtAgo(sec: number | null | undefined): string {
  if (sec == null) return '기록 없음';
  const s = Math.floor(sec);
  if (s < 60) return `${s}초 전`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}분 ${s % 60}초 전`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}시간 ${m % 60}분 전` : `${Math.floor(h / 24)}일 ${h % 24}시간 전`;
}

export function fmtMinutes(v: number | string | null | undefined): string {
  const m = parseInt(String(v), 10);
  if (!Number.isFinite(m)) return '?';
  if (m < 60) return `${m}분`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return mm ? `${h}시간 ${mm}분` : `${h}시간`;
}

export function timeOf(iso: string | null | undefined): string {
  return iso ? iso.slice(11, 16) : '—';
}

export function stampOf(iso: string | null | undefined): string {
  return iso ? `${iso.slice(5, 7)}/${iso.slice(8, 10)} ${iso.slice(11, 16)}` : '';
}

export function fmtDurationSec(s: number): string {
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d) return `${d}일 ${h % 24}시간`;
  if (h) return `${h}시간 ${m % 60}분`;
  return `${m}분`;
}
