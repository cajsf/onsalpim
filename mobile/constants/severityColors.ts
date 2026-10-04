import { theme } from '@/constants/theme';
import type { Severity } from '@/lib/types';

/** 대시보드 .tag-normal / .tag-watch / .tag-urgent / .tag-device */
export const SEV_COLORS: Record<
  Severity,
  { bg: string; text: string; border: string; bar: string }
> = {
  NORMAL: { bg: theme.normalSoft, text: theme.normal, border: theme.normalSoft, bar: theme.normal },
  WATCH: { bg: theme.watchSoft, text: theme.watch, border: theme.watchSoft, bar: theme.watch },
  URGENT: { bg: theme.urgentSoft, text: theme.urgent, border: theme.urgentSoft, bar: theme.urgent },
  CHECK_DEVICE: {
    bg: theme.deviceSoft,
    text: theme.device,
    border: theme.deviceSoft,
    bar: theme.device,
  },
};

export const STATE_COLORS: Record<string, { bg: string; text: string }> = {
  urgent: { bg: theme.urgentSoft, text: theme.urgent },
  watch: { bg: theme.watchSoft, text: theme.watch },
  normal: { bg: theme.normalSoft, text: theme.normal },
  muted: { bg: theme.surface2, text: theme.muted },
};

export function severityBarColor(severity: Severity, welfare?: boolean): string {
  if (welfare) return theme.urgent;
  return SEV_COLORS[severity]?.bar ?? theme.border;
}
