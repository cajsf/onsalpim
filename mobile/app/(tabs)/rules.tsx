import { useCallback, useMemo, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { EngineBanner } from '@/components/EngineBanner';
import { RuleListItem } from '@/components/RuleListItem';
import { useSettings } from '@/context/SettingsContext';
import { usePolling } from '@/hooks/usePolling';
import type { EngineStatus } from '@/lib/types';

type Filter = 'pending' | 'active';

export default function RulesScreen() {
  const { api } = useSettings();
  const [filter, setFilter] = useState<Filter>('pending');

  const fetchAll = useCallback(async () => {
    const [engine, rules] = await Promise.all([api.getEngineStatus(), api.getRules()]);
    return { engine, rules };
  }, [api]);

  const { data, error, loading, refresh } = usePolling(fetchAll, [api.base], 5000);

  const engine: EngineStatus | null = data?.engine ?? null;
  const rules = data?.rules ?? [];

  const pending = useMemo(() => rules.filter((r) => r.status === 'pending'), [rules]);
  const active = useMemo(() => rules.filter((r) => r.status !== 'pending'), [rules]);
  const shown = filter === 'pending' ? pending : active;

  return (
    <View style={styles.flex}>
      <EngineBanner engine={engine} care={null} loading={loading} fetchError={error} />
      <View style={styles.filters}>
        <Pressable
          style={StyleSheet.flatten([styles.chip, filter === 'pending' && styles.chipOn])}
          onPress={() => setFilter('pending')}>
          <Text style={StyleSheet.flatten([styles.chipText, filter === 'pending' && styles.chipTextOn])}>
            승인 대기 {pending.length ? `(${pending.length})` : ''}
          </Text>
        </Pressable>
        <Pressable
          style={StyleSheet.flatten([styles.chip, filter === 'active' && styles.chipOn])}
          onPress={() => setFilter('active')}>
          <Text style={StyleSheet.flatten([styles.chipText, filter === 'active' && styles.chipTextOn])}>
            적용 중
          </Text>
        </Pressable>
      </View>
      <FlatList
        data={shown}
        keyExtractor={(r) => String(r.id)}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
        ListEmptyComponent={
          !loading ? (
            <Text style={styles.empty}>
              {filter === 'pending' ? '승인 대기 규칙이 없습니다.' : '적용 중인 규칙이 없습니다.'}
            </Text>
          ) : null
        }
        renderItem={({ item }) => (
          <RuleListItem rule={item} pending={item.status === 'pending'} />
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#fafafa' },
  filters: { flexDirection: 'row', gap: 8, padding: 10, backgroundColor: '#fff' },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#eee' },
  chipOn: { backgroundColor: '#1565c0' },
  chipText: { color: '#424242', fontWeight: '600', fontSize: 13 },
  chipTextOn: { color: '#fff' },
  empty: { textAlign: 'center', color: '#757575', marginTop: 40, paddingHorizontal: 16 },
});
