import { devName, fmtMinutes, typeKo } from './format';
import type { RuleRecord } from './types';

type RuleBody = {
  when?: { op?: string; type?: string; path?: string; value?: unknown };
  then?: { severity?: string; path?: string; value?: unknown }[];
  scope?: { homes?: string };
};

export function condText(rule: RuleBody | undefined): string {
  const w = rule?.when || {};
  if (w.op === 'idle_over_m') {
    return `${typeKo(w.type as string)}이 ${fmtMinutes(w.value as number)} 이상 없음 (${w.type || '?'} 센서 기준)`;
  }
  const target = w.type ? typeKo(w.type as string) : devName(w.path as string);
  return `${target} ${w.op} ${w.value}`;
}

export function actText(rule: RuleBody | undefined): string {
  const acts = rule?.then || [];
  const sev = acts.find((a) => a.severity)?.severity;
  if (sev) return `위험도 ${sev}`;
  return acts.map((a) => `${devName(a.path as string)} → ${a.value}`).join(', ') || '—';
}

export function scopeText(rule: RuleBody | undefined): string {
  const s = rule?.scope?.homes;
  if (!s) return '장치 직접 지정';
  if (String(s).toUpperCase() === 'ALL') return '전체 세대';
  return `${s}호`;
}

export function previewEnabled(rule: RuleBody | undefined, fillValue: string): boolean {
  const w = rule?.when || {};
  if (w.op !== 'idle_over_m') return false;
  const v = String(w.value ?? '').trim();
  if (v) return true;
  return Boolean(fillValue.trim());
}

export function previewReplace(conflicts: RuleRecord['conflicts']): boolean {
  const cs = conflicts || [];
  return cs.length > 0 && cs.every((c) => c.covers_all);
}
