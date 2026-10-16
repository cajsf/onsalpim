/** 대시보드 format.js 와 같은 키·표기 — 화면이 서로 다르게 보이지 않는다. */

export const SEV = {
  NORMAL: { ko: '정상', cls: 'normal' as const },
  WATCH: { ko: '주의', cls: 'watch' as const },
  URGENT: { ko: '긴급 확인', cls: 'urgent' as const },
  CHECK_DEVICE: { ko: '장치 점검', cls: 'device' as const },
};

export const ALERT_STATE: Record<
  string,
  { ko: string; cls: 'urgent' | 'watch' | 'normal' | 'muted' | 'life' }
> = {
  open: { ko: '대응 필요', cls: 'urgent' },
  missed: { ko: '응답 없이 지나감', cls: 'muted' },
  assign: { ko: '배정', cls: 'life' },
  ack: { ko: '확인', cls: 'watch' },
  progress: { ko: '방문·연락 중', cls: 'watch' },
  done: { ko: '조치 완료', cls: 'normal' },
  late: { ko: '뒤늦게 확인', cls: 'muted' },
  edit: { ko: '메모 수정', cls: 'muted' },
};

export const SEV_ORDER = ['URGENT', 'CHECK_DEVICE', 'WATCH', 'NORMAL'] as const;

/** 조치 완료 결과 — 서버 engine.OUTCOMES 와 같은 키 */
export const OUTCOMES = [
  { id: 'outing', ko: '외출' },
  { id: 'ok', ko: '정상 확인' },
  { id: 'device', ko: '장치 문제' },
  { id: 'visit', ko: '방문 필요' },
] as const;

export function outcomeKo(id: string | null | undefined): string {
  return OUTCOMES.find((o) => o.id === id)?.ko || '';
}

export const PATTERN_KO: Record<string, string> = {
  HOT_IDLE: '고온 지속 + 활동 저하',
  MORNING_NONE: '아침 활동 부재',
  NIGHT_WANDER: '야간 활동 변화',
  MORNING_LOW: '아침 활동 부재 (개인 기준)',
  COLD_IDLE: '저온 지속 + 활동 저하',
  HUMID_IDLE: '습도 이상 + 활동 감소',
  DAY_DROP: '주간 활동 급감',
  DAILY_DECLINE: '반복 활동 감소',
  ROUTINE_OVERDUE: '외출·수면 뒤 추가 확인',
  ROUTINE_HOLD: '생활 일정 중 (주의 보류)',
  SENSOR_STUCK: '센서값 고정·범위 밖',
};

export const FOLLOW_KO: Record<string, string> = {
  RENOTIFY: '재통지',
  ESCALATE: '다음 담당자에게 이관',
};

type SevHome = { severity?: keyof typeof SEV; life_check?: boolean };

/** 생활 쪽 낮은 위험은 생활 확인. 배터리 주의는 주의로 남긴다. */
export function sevKo(h: SevHome | null | undefined): string {
  if (h?.life_check) return '생활 확인';
  return (h?.severity && SEV[h.severity]?.ko) || '';
}

type SevAlert = {
  welfare?: boolean;
  device_check?: boolean;
  life_check?: boolean;
  follow?: string | null;
  outage?: boolean;
  from?: keyof typeof SEV | null;
  to?: keyof typeof SEV;
};

/** 알림 한 줄의 위험 이름. 생활 확인은 배터리 주의와 같은 주의로 적지 않는다. */
export function alertKo(a: SevAlert | null | undefined): string {
  if (a?.outage) return '망 점검';
  if (a?.follow && FOLLOW_KO[a.follow]) return FOLLOW_KO[a.follow];
  if (a?.welfare) return '안부 확인';
  if (a?.device_check && a.from === a.to) return '장치 점검';
  if (a?.life_check && a.to === 'WATCH') return '생활 확인';
  return (a?.to && SEV[a.to]?.ko) || '';
}

/** 알림 문장 앞의 '이전 → 지금'. 화면에 보이는 이름이 같을 때는 빈 문자열. */
export function alertChange(a: SevAlert | null | undefined): string {
  if (!a || a.outage || a.welfare) return '';
  const to = alertKo(a);
  const from = a.from ? (SEV[a.from]?.ko ?? a.from) : '첫 판정';
  if (!to || from === to) return '';
  return `${from} → ${to} · `;
}

export function alertIsLife(a: SevAlert | null | undefined): boolean {
  return !a?.welfare && !(a?.device_check && a.from === a.to) && !!a?.life_check && a.to === 'WATCH';
}

export function alertSeverity(a: SevAlert | null | undefined): keyof typeof SEV {
  if (a?.welfare) return 'URGENT';
  if (a?.device_check && a.from === a.to) return 'CHECK_DEVICE';
  return a?.to || 'NORMAL';
}

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
