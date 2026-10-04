import type { Severity } from '@/lib/types';

export const SEV_COLORS: Record<
  Severity,
  { bg: string; text: string; border: string }
> = {
  NORMAL: { bg: '#e8f5e9', text: '#2e7d32', border: '#a5d6a7' },
  WATCH: { bg: '#fff8e1', text: '#f57f17', border: '#ffe082' },
  URGENT: { bg: '#ffebee', text: '#c62828', border: '#ef9a9a' },
  CHECK_DEVICE: { bg: '#e3f2fd', text: '#1565c0', border: '#90caf9' },
};

export const STATE_COLORS: Record<string, { bg: string; text: string }> = {
  urgent: { bg: '#ffebee', text: '#c62828' },
  watch: { bg: '#fff8e1', text: '#f57f17' },
  normal: { bg: '#e8f5e9', text: '#2e7d32' },
  muted: { bg: '#f5f5f5', text: '#616161' },
};
