import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { theme } from '@/constants/theme';
import type { CareResponse, EngineStatus } from '@/lib/types';

type Props = {
  engine: EngineStatus | null;
  care: CareResponse | null;
  loading?: boolean;
  fetchError?: string;
  updatedHint?: string | null;
};

export function EngineBanner({ engine, care, loading, fetchError, updatedHint }: Props) {
  if (fetchError) {
    return (
      <View style={[styles.box, styles.err]}>
        <Text style={styles.errText}>서버 연결 실패 — {fetchError}</Text>
        {fetchError.includes('404') ? (
          <Text style={styles.hint}>
            API 는 onsalpim-api …/api 입니다. 더보기 → API 설정을 확인하세요.
          </Text>
        ) : (
          <Text style={styles.hint}>Render Free 는 첫 요청에 30초 정도 걸릴 수 있습니다.</Text>
        )}
      </View>
    );
  }

  if (loading && !engine) {
    return (
      <View style={[styles.box, styles.neutral]}>
        <ActivityIndicator color={theme.brand} />
        <Text style={styles.muted}>서버에 연결하는 중…</Text>
      </View>
    );
  }

  if (engine && !engine.running) {
    return (
      <View style={[styles.box, styles.warn]}>
        <Text style={styles.warnText}>{engine.message}</Text>
      </View>
    );
  }

  if (engine?.platform_error) {
    return (
      <View style={[styles.box, styles.warn]}>
        <Text style={styles.warnText}>공용 서버 응답 없음 — {engine.platform_error}</Text>
      </View>
    );
  }

  if (care?.stale) {
    return (
      <View style={[styles.box, styles.warn]}>
        <Text style={styles.warnText}>
          {care.message || '판정이 멈춘 것 같습니다. 숫자를 최신으로 보지 마세요.'}
        </Text>
      </View>
    );
  }

  if (engine?.running) {
    return (
      <View style={styles.compactRow}>
        <View style={styles.chipOn}>
          <Text style={styles.chipOnText}>● 실시간 모니터링 중</Text>
        </View>
        {updatedHint ? <Text style={styles.updated}>{updatedHint}</Text> : null}
      </View>
    );
  }

  return null;
}

const styles = StyleSheet.create({
  box: { padding: 12, borderBottomWidth: 1, borderBottomColor: theme.border },
  compactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: theme.screenPad,
    paddingVertical: 8,
    backgroundColor: theme.surface,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  chipOn: {
    backgroundColor: theme.normalSoft,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  chipOnText: { color: theme.normal, fontWeight: '600', fontSize: 13 },
  updated: { fontSize: 11, color: theme.muted },
  warn: { backgroundColor: theme.watchSoft },
  warnText: { color: theme.watch, textAlign: 'center', fontSize: 13, lineHeight: 18 },
  err: { backgroundColor: theme.urgentSoft },
  errText: { color: theme.urgent, fontWeight: '600', textAlign: 'center', fontSize: 13 },
  hint: { color: theme.muted, fontSize: 12, textAlign: 'center', marginTop: 4 },
  neutral: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  muted: { color: theme.text2 },
});
