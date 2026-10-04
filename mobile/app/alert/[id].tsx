import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import { AlertActions } from '@/components/AlertActions';
import { SeverityTag } from '@/components/SeverityTag';
import { useSettings } from '@/context/SettingsContext';
import { SEV, stampOf } from '@/lib/format';
import type { AlertRecord } from '@/lib/types';

export default function AlertDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { api } = useSettings();
  const [alert, setAlert] = useState<AlertRecord | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const list = await api.getAlerts(100);
      const found = list.find((a) => a.id === id);
      if (!found) setError('알림을 찾을 수 없습니다.');
      else {
        setAlert(found);
        setError('');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !alert) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error || !alert) {
    return (
      <View style={styles.center}>
        <Text style={styles.err}>{error || '알림 없음'}</Text>
      </View>
    );
  }

  const a = alert;

  return (
    <ScrollView style={styles.flex}>
      <View style={styles.header}>
        <Text style={styles.ts}>{stampOf(a.ts)}</Text>
        <Text style={styles.home}>{a.home}호</Text>
        <View style={styles.tags}>
          {a.welfare ? (
            <SeverityTag severity="URGENT" label="안부 확인" />
          ) : (
            <SeverityTag severity={a.to} />
          )}
        </View>
        <Text style={styles.reason}>
          {!a.welfare && a.from ? `${SEV[a.from]?.ko ?? a.from} → ` : ''}
          {SEV[a.to]?.ko ?? a.to} · {a.reason}
        </Text>
      </View>
      <AlertActions
        alert={a}
        api={api}
        onUpdated={(log, state) => {
          setAlert({ ...a, log, state });
        }}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#fafafa' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  err: { color: '#c62828' },
  header: { padding: 16, backgroundColor: '#fff', borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#ddd' },
  ts: { color: '#757575', marginBottom: 4 },
  home: { fontSize: 22, fontWeight: '700', marginBottom: 8 },
  tags: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  reason: { lineHeight: 22, color: '#333' },
});
