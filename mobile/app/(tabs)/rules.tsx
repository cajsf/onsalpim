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
import { Screen } from '@/components/Screen';
import { theme } from '@/constants/theme';
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
    <Screen>
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
        {filter === 'pending' && !pending.length && !loading ? (
          <Text style={styles.hint}>승인 대기가 없습니다. 웹 대시보드에서 규칙을 만들면 여기에 표시됩니다.</Text>
        ) : null}
        <FlatList
          data={shown}
          keyExtractor={(r) => String(r.id)}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={theme.brand} />}
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
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  filters: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    padding: 10,
    paddingHorizontal: theme.screenPad,
    backgroundColor: theme.surface,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  chip: {
    minHeight: theme.minTouch,
    justifyContent: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: theme.surface2,
    borderWidth: 1,
    borderColor: theme.border,
  },
  chipOn: { backgroundColor: theme.brandSoft, borderColor: theme.brand },
  chipText: { color: theme.text2, fontWeight: '600', fontSize: 13 },
  chipTextOn: { color: theme.brandDim },
  hint: {
    color: theme.muted,
    fontSize: 13,
    paddingHorizontal: theme.screenPad,
    paddingTop: 12,
    lineHeight: 18,
  },
  listContent: { paddingTop: 8, paddingBottom: 24 },
  empty: { textAlign: 'center', color: theme.muted, marginTop: 40, paddingHorizontal: 16 },
});
