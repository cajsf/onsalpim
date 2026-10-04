import { useCallback, useMemo, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { AlertListItem } from '@/components/AlertListItem';
import { EngineBanner } from '@/components/EngineBanner';
import { useSettings } from '@/context/SettingsContext';
import { usePolling } from '@/hooks/usePolling';
import type { EngineStatus } from '@/lib/types';

type Filter = 'todo' | 'all';

export default function AlertsScreen() {
  const { api } = useSettings();
  const [filter, setFilter] = useState<Filter>('todo');

  const fetchAll = useCallback(async () => {
    const [engine, alerts] = await Promise.all([
      api.getEngineStatus(),
      api.getAlerts(50),
    ]);
    return { engine, alerts };
  }, [api]);

  const { data, error, loading, refresh } = usePolling(fetchAll, [api.base], 4000);

  const engine: EngineStatus | null = data?.engine ?? null;
  const alerts = data?.alerts ?? [];

  const shown = useMemo(() => {
    if (filter === 'all') return alerts;
    return alerts.filter((a) => ['open', 'ack', 'progress'].includes(a.state ?? ''));
  }, [alerts, filter]);

  return (
    <View style={styles.flex}>
      <EngineBanner engine={engine} care={null} loading={loading} fetchError={error} />
      <View style={styles.filters}>
        <Pressable
          style={[styles.chip, filter === 'todo' && styles.chipOn]}
          onPress={() => setFilter('todo')}>
          <Text style={[styles.chipText, filter === 'todo' && styles.chipTextOn]}>미완료</Text>
        </Pressable>
        <Pressable
          style={[styles.chip, filter === 'all' && styles.chipOn]}
          onPress={() => setFilter('all')}>
          <Text style={[styles.chipText, filter === 'all' && styles.chipTextOn]}>전체</Text>
        </Pressable>
      </View>
      <FlatList
        data={shown}
        keyExtractor={(a) => a.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
        ListEmptyComponent={
          !loading ? <Text style={styles.empty}>알림이 없습니다.</Text> : null
        }
        renderItem={({ item }) => <AlertListItem alert={item} compact />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#fafafa' },
  filters: { flexDirection: 'row', gap: 8, padding: 10, backgroundColor: '#fff' },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#eee',
  },
  chipOn: { backgroundColor: '#1565c0' },
  chipText: { color: '#424242', fontWeight: '600' },
  chipTextOn: { color: '#fff' },
  empty: { textAlign: 'center', color: '#757575', marginTop: 40 },
});
