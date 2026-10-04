import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { useSettings } from '@/context/SettingsContext';
import type { PreviewResult } from '@/lib/types';

type Props = {
  ruleId: number;
  fillValue: string;
  replace: boolean;
  enabled: boolean;
};

export function RulePreviewPanel({ ruleId, fillValue, replace, enabled }: Props) {
  const { api } = useSettings();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PreviewResult | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!enabled || !ruleId) {
      setData(null);
      setErr('');
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr('');
      try {
        const r = await api.previewRule(
          ruleId,
          fillValue.trim() || undefined,
          replace,
        );
        if (!cancelled) {
          setData(r);
          if (!r.ok && r.errors?.length) setErr(r.errors.join(' '));
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, ruleId, fillValue, replace, enabled]);

  if (!enabled) {
    return (
      <Text style={styles.muted}>무활동 규칙(기준값 필요)만 2주 미리보기를 지원합니다.</Text>
    );
  }

  return (
    <View style={styles.box}>
      <Text style={styles.title}>2주 미리보기 (승인 전)</Text>
      {loading ? (
        <ActivityIndicator />
      ) : err ? (
        <Text style={styles.warn}>{err}</Text>
      ) : data?.supported === false ? (
        <Text style={styles.muted}>{data.reason}</Text>
      ) : data?.ok ? (
        <>
          <View style={styles.kpi}>
            <Text style={styles.k}>이 규칙 적용 시 추정 알림</Text>
            <Text style={StyleSheet.flatten([styles.v, (data.total ?? 0) >= 20 && styles.hot])}>
              {data.total}건
            </Text>
            <Text style={styles.k}>지금 규칙 그대로였다면</Text>
            <Text style={styles.v}>{data.baseline_total}건</Text>
          </View>
          {(data.homes || [])
            .filter((h) => h.alerts > 0)
            .slice(0, 6)
            .map((h) => (
              <Text key={h.home} style={styles.row}>
                {h.home}호 · +{h.alerts - h.baseline}건 (합 {h.alerts})
              </Text>
            ))}
          {data.sparse_data ? (
            <Text style={styles.muted}>움직임 기록이 적어 추정이 거칠 수 있습니다.</Text>
          ) : null}
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { backgroundColor: '#f5f5f5', borderRadius: 8, padding: 12, gap: 6, marginTop: 8 },
  title: { fontWeight: '700', fontSize: 14 },
  muted: { color: '#757575', fontSize: 13, lineHeight: 18 },
  warn: { color: '#e65100', fontSize: 13 },
  kpi: { gap: 2 },
  k: { fontSize: 12, color: '#616161' },
  v: { fontSize: 18, fontWeight: '700', marginBottom: 6 },
  hot: { color: '#c62828' },
  row: { fontSize: 13, color: '#333' },
});
