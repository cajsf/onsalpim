import { useCallback } from 'react';

import { useSettings } from '@/context/SettingsContext';
import { usePolling } from '@/hooks/usePolling';

/** 하단 탭 배지 — 미완료 알림·승인 대기 규칙 (시연용) */
export function useTabBadges(intervalMs = 5000) {
  const { api } = useSettings();

  const fetchCounts = useCallback(async () => {
    const [alerts, rules] = await Promise.all([api.getAlerts(50), api.getRules()]);
    const todo = alerts.filter((a) =>
      ['open', 'ack', 'progress'].includes(a.state ?? ''),
    ).length;
    const open = alerts.filter((a) => a.state === 'open').length;
    const pending = rules.filter((r) => r.status === 'pending').length;
    return { todo, open, pending };
  }, [api]);

  const { data } = usePolling(fetchCounts, [api.base], intervalMs);

  return {
    todoAlertCount: data?.todo ?? 0,
    openAlertCount: data?.open ?? 0,
    pendingRuleCount: data?.pending ?? 0,
  };
}

export function badgeText(n: number): string | undefined {
  if (n <= 0) return undefined;
  return n > 99 ? '99+' : String(n);
}
