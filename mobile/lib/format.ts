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

/** 서버 시각('2026-09-17T09:05:06+09:00')부터 nowMs 까지 경과 초. 표기가 없으면 기기 로컬로 읽는다. */
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

/** 경과 시간. '전'을 붙이지 않는다. 1분 미만만 초를 남긴다. */
export function fmtSpan(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec)) return '';
  const s = Math.max(0, Math.floor(sec));
  if (s < 60) return `${s}초`;
  const m = Math.floor(s / 60);
  if (m < 60) return s % 60 ? `${m}분 ${s % 60}초` : `${m}분`;
  const h = Math.floor(m / 60);
  if (h < 24) return m % 60 ? `${h}시간 ${m % 60}분` : `${h}시간`;
  const d = Math.floor(h / 24);
  return h % 24 ? `${d}일 ${h % 24}시간` : `${d}일`;
}

export type IdleBar = {
  limitMin: number;
  elapsed: number | null;
  ratio: number | null;
  over: boolean;
  tone: 'ok' | 'watch' | 'urgent' | 'held' | 'unknown';
  text: string;
  ticks: { at: number; title: string }[];
  big: string;
};

/** 무활동 진행. 기준이 없으면 null. 움직임 시각이 없으면 막대를 0으로 채우지 않는다. */
export function idleBar(
  elapsedS: number | null | undefined,
  idleMin: number | null | undefined,
  idleLevels: { minutes: number; severity: string }[] | null | undefined,
  opts: { away?: boolean; lifeKnown?: boolean } = {},
): IdleBar | null {
  const levels = (Array.isArray(idleLevels) ? idleLevels : [])
    .map((lv) => ({ minutes: Number(lv.minutes), severity: lv.severity }))
    .filter((lv) => Number.isFinite(lv.minutes) && lv.minutes > 0);
  let limitMin = Number(idleMin);
  if (!Number.isFinite(limitMin) || limitMin <= 0) {
    const urgent = levels.find((lv) => lv.severity === 'URGENT');
    limitMin = urgent ? urgent.minutes : levels[0] ? levels[0].minutes : NaN;
  }
  if (!Number.isFinite(limitMin) || limitMin <= 0) return null;

  const away = !!opts.away;
  const silent = opts.lifeKnown === false;
  const known = elapsedS != null && Number.isFinite(Number(elapsedS));
  const elapsed = known ? Math.max(0, Number(elapsedS)) : null;
  const limitS = limitMin * 60;
  const ratio = known && elapsed != null ? Math.min(1, elapsed / limitS) : null;
  const over = known && elapsed != null && elapsed > limitS;
  const passedWatch =
    known &&
    elapsed != null &&
    levels.some((lv) => lv.severity === 'WATCH' && elapsed > lv.minutes * 60 && elapsed <= limitS);
  const tone = away || silent ? 'held' : !known ? 'unknown' : over ? 'urgent' : passedWatch ? 'watch' : 'ok';
  const limitText = fmtMinutes(limitMin);
  const ticks = levels
    .filter((lv) => lv.minutes < limitMin)
    .map((lv) => ({
      at: lv.minutes / limitMin,
      title: `${fmtMinutes(lv.minutes)} ${SEV[lv.severity as keyof typeof SEV]?.ko || ''}`.trim(),
    }));

  let text: string;
  if (!known) text = `${limitText} 기준 · 움직임 기록 없음`;
  else if (away) text = `${limitText} 기준 중 ${fmtSpan(elapsed)} 경과 · 부재 중 판정 보류`;
  else if (over) text = `${limitText} 기준을 ${fmtSpan((elapsed ?? 0) - limitS)} 넘김`;
  else text = `${limitText} 기준 중 ${fmtSpan(elapsed)} 경과`;
  if (silent && known) text += ' · 통신 두절 이후는 확인 불가';

  return {
    limitMin,
    elapsed,
    ratio,
    over,
    tone,
    text,
    ticks,
    big: !known ? '—' : over && !away && !silent ? `${fmtSpan((elapsed ?? 0) - limitS)} 초과` : fmtSpan(elapsed),
  };
}

export function timeOf(iso: string | null | undefined): string {
  return iso ? iso.slice(11, 16) : '—';
}

export function stampOf(iso: string | null | undefined): string {
  return iso ? `${iso.slice(5, 7)}/${iso.slice(8, 10)} ${iso.slice(11, 16)}` : '';
}

/** 온도 한 칸. 보고 주기 × 3 을 넘기면 숫자를 두지 않는다. 주기를 모르면 시각을 붙인다. */
export function tempStatus(
  temp: unknown,
  limitS: number | null | undefined,
  nowMs: number,
): { silent: boolean; text: string; when: string } | null {
  if (!Array.isArray(temp) || temp.length < 2 || temp[1] == null || temp[1] === '') return null;
  const age = secondsSince(String(temp[0] ?? ''), nowMs);
  const n = Number(temp[1]);
  const value = Number.isFinite(n) ? `${n}°C` : String(temp[1]);
  const when = stampOf(typeof temp[0] === 'string' ? temp[0] : '');
  const known = typeof limitS === 'number' && limitS > 0 && age != null;
  if (known && age > limitS) return { silent: true, text: '센서 응답 없음', when };
  if (known) return { silent: false, text: value, when: '' };
  return { silent: false, text: when ? `${value} · ${when}` : value, when: '' };
}

export function fmtDurationSec(s: number): string {
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d) return `${d}일 ${h % 24}시간`;
  if (h) return `${h}시간 ${m % 60}분`;
  return `${m}분`;
}
