import { useCallback, useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { EngineBanner } from '@/components/EngineBanner';
import { HomeListItem } from '@/components/HomeListItem';
import { Screen } from '@/components/Screen';
import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import { SEV_ORDER, stampOf } from '@/lib/format';
import type { CareHome } from '@/lib/types';
import { useNow } from '@/hooks/useNow';
import { usePolling } from '@/hooks/usePolling';

type HomeFilter = 'all' | 'urgent' | 'life' | 'device' | 'battery';

function sortHomes(homes: CareHome[]): CareHome[] {
  return [...homes].sort((a, b) => {
    const ia = SEV_ORDER.indexOf(a.severity as (typeof SEV_ORDER)[number]);
    const ib = SEV_ORDER.indexOf(b.severity as (typeof SEV_ORDER)[number]);
    if (ia !== ib) return ia - ib;
    return a.home.localeCompare(b.home, 'ko');
  });
}

export default function CareScreen() {
  const { api } = useSettings();
  const nowMs = useNow();
  const [filter, setFilter] = useState<HomeFilter>('all');

  const fetchAll = useCallback(async () => {
    const [engine, care] = await Promise.all([api.getEngineStatus(), api.getCare()]);
    return { engine, care };
  }, [api]);

  const { data, error, loading, refresh, okAt } = usePolling(fetchAll, [api.base], 4000);

  const engine = data?.engine ?? null;
  const care = data?.care ?? null;
  const homes = useMemo(() => {
    const all = care?.homes ?? [];
    const picked =
      filter === 'urgent'
        ? all.filter((h) => h.severity === 'URGENT')
        : filter === 'life'
          ? all.filter((h) => h.life_check)
          : filter === 'device'
            ? all.filter((h) => h.severity === 'CHECK_DEVICE' || h.device_check)
            : filter === 'battery'
              ? all.filter((h) => h.battery != null && h.battery < 20)
              : all;
    return sortHomes(picked);
  }, [care, filter]);
  const chips = useMemo(() => {
    const all = care?.homes ?? [];
    return [
      { id: 'all' as const, label: '전체', n: all.length },
      { id: 'urgent' as const, label: '긴급', n: all.filter((h) => h.severity === 'URGENT').length },
      { id: 'life' as const, label: '생활 확인', n: all.filter((h) => h.life_check).length },
      {
        id: 'device' as const,
        label: '장치 점검',
        n: all.filter((h) => h.severity === 'CHECK_DEVICE' || h.device_check).length,
      },
      {
        id: 'battery' as const,
        label: '배터리',
        n: all.filter((h) => h.battery != null && h.battery < 20).length,
      },
    ];
  }, [care]);
  const known = care != null;
  const updatedHint = care?.updated ? `판정 ${stampOf(care.updated)}` : null;
  const lastOkText = okAt
    ? new Date(okAt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
    : null;

  return (
    <Screen>
      <View style={styles.flex}>
        <EngineBanner
          engine={engine}
          care={care}
          loading={loading}
          fetchError={error}
          updatedHint={updatedHint}
          lastOkText={error ? lastOkText : null}
        />
        <View style={styles.filters}>
          {chips.map((c) => (
            <Pressable
              key={c.id}
              style={StyleSheet.flatten([
                styles.chip,
                filter === c.id && styles.chipOn,
                !!error && styles.chipDim,
              ])}
              onPress={() => setFilter(c.id)}
            >
              <Text style={StyleSheet.flatten([styles.chipText, filter === c.id && styles.chipTextOn])}>
                {c.label} {known ? c.n : '—'}
              </Text>
            </Pressable>
          ))}
        </View>
        <FlatList
          data={homes}
          keyExtractor={(h) => h.home}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={theme.brand} />}
          ListEmptyComponent={
            !known
              ? loading
                ? null
                : <Text style={styles.empty}>판정을 아직 받지 못했습니다.</Text>
              : !homes.length
                ? <Text style={styles.empty}>표시할 세대가 없습니다.</Text>
                : null
          }
          renderItem={({ item }) => <HomeListItem home={item} nowMs={nowMs} />}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: theme.screenPad, paddingBottom: 4 },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
  chipOn: { backgroundColor: theme.brandSoft, borderColor: theme.brand },
  chipText: { color: theme.text2, fontSize: 13, fontWeight: '600' },
  chipTextOn: { color: theme.brandDim },
  chipDim: { opacity: 0.45 },
  listContent: { paddingTop: 8, paddingBottom: 24 },
  empty: { textAlign: 'center', color: theme.muted, marginTop: 40 },
});
