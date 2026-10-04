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
import { Screen } from '@/components/Screen';
import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import { usePolling } from '@/hooks/usePolling';
import type { AlertRecord, EngineStatus } from '@/lib/types';

type Filter = 'todo' | 'all';

const STATE_ORDER: Record<string, number> = { open: 0, ack: 1, progress: 2 };

function sortAlerts(list: AlertRecord[]): AlertRecord[] {
  return [...list].sort((a, b) => {
    const oa = STATE_ORDER[a.state ?? ''] ?? 9;
    const ob = STATE_ORDER[b.state ?? ''] ?? 9;
    if (oa !== ob) return oa - ob;
    return b.ts.localeCompare(a.ts);
  });
}

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

  const openCount = useMemo(
    () => alerts.filter((a) => a.state === 'open').length,
    [alerts],
  );

  const shown = useMemo(() => {
    const base =
      filter === 'all'
        ? alerts
        : alerts.filter((a) => ['open', 'ack', 'progress'].includes(a.state ?? ''));
    return sortAlerts(base);
  }, [alerts, filter]);

  return (
    <Screen>
      <View style={styles.flex}>
        <EngineBanner engine={engine} care={null} loading={loading} fetchError={error} />
        {openCount > 0 ? (
          <View style={styles.openBanner}>
            <Text style={styles.openBannerTitle}>대응 필요 {openCount}건</Text>
            <Text style={styles.openBannerSub}>아직 확인하지 않은 알림입니다.</Text>
          </View>
        ) : null}
        <View style={styles.filters}>
          <Pressable
            style={StyleSheet.flatten([styles.chip, filter === 'todo' && styles.chipOn])}
            onPress={() => setFilter('todo')}>
            <Text style={StyleSheet.flatten([styles.chipText, filter === 'todo' && styles.chipTextOn])}>
              미완료
            </Text>
          </Pressable>
          <Pressable
            style={StyleSheet.flatten([styles.chip, filter === 'all' && styles.chipOn])}
            onPress={() => setFilter('all')}>
            <Text style={StyleSheet.flatten([styles.chipText, filter === 'all' && styles.chipTextOn])}>
              전체
            </Text>
          </Pressable>
        </View>
        <FlatList
          data={shown}
          keyExtractor={(a) => a.id}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={theme.brand} />}
          ListEmptyComponent={
            !loading ? <Text style={styles.empty}>알림이 없습니다.</Text> : null
          }
          renderItem={({ item }) => <AlertListItem alert={item} compact />}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  openBanner: {
    backgroundColor: theme.urgentSoft,
    paddingHorizontal: theme.screenPad,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  openBannerTitle: { color: theme.urgent, fontWeight: '700', fontSize: 15 },
  openBannerSub: { color: theme.urgent, fontSize: 13, marginTop: 2, opacity: 0.85 },
  filters: {
    flexDirection: 'row',
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
  chipText: { color: theme.text2, fontWeight: '600' },
  chipTextOn: { color: theme.brandDim },
  listContent: { paddingTop: 8, paddingBottom: 24 },
  empty: { textAlign: 'center', color: theme.muted, marginTop: 40 },
});
