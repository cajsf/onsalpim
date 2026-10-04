import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import type { CareResponse, EngineStatus } from '@/lib/types';

type Props = {
  engine: EngineStatus | null;
  care: CareResponse | null;
  loading?: boolean;
  fetchError?: string;
};

export function EngineBanner({ engine, care, loading, fetchError }: Props) {
  if (fetchError) {
    return (
      <View style={[styles.box, styles.err]}>
        <Text style={styles.errText}>서버 연결 실패 — {fetchError}</Text>
        <Text style={styles.hint}>Render Free 는 첫 요청에 30초 정도 걸릴 수 있습니다.</Text>
      </View>
    );
  }

  if (loading && !engine) {
    return (
      <View style={[styles.box, styles.neutral]}>
        <ActivityIndicator />
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
      <View style={[styles.box, styles.ok]}>
        <Text style={styles.okText}>실시간 모니터링 중</Text>
      </View>
    );
  }

  return null;
}

const styles = StyleSheet.create({
  box: { padding: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#ccc' },
  ok: { backgroundColor: '#e8f5e9' },
  okText: { color: '#2e7d32', fontWeight: '600', textAlign: 'center' },
  warn: { backgroundColor: '#fff8e1' },
  warnText: { color: '#e65100', textAlign: 'center' },
  err: { backgroundColor: '#ffebee' },
  errText: { color: '#c62828', fontWeight: '600', textAlign: 'center' },
  hint: { color: '#757575', fontSize: 12, textAlign: 'center', marginTop: 4 },
  neutral: { flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  muted: { color: '#616161' },
});
