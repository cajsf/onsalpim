import { useCallback, useMemo } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { EngineBanner } from '@/components/EngineBanner';
import { HomeListItem } from '@/components/HomeListItem';
import { Screen } from '@/components/Screen';
import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import { SEV_ORDER, stampOf } from '@/lib/format';
import type { CareHome } from '@/lib/types';
import { useNow } from '@/hooks/useNow';
import { usePolling } from '@/hooks/usePolling';

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

  const fetchAll = useCallback(async () => {
    const [engine, care] = await Promise.all([api.getEngineStatus(), api.getCare()]);
    return { engine, care };
  }, [api]);

  const { data, error, loading, refresh } = usePolling(fetchAll, [api.base], 4000);

  const engine = data?.engine ?? null;
  const care = data?.care ?? null;
  const homes = useMemo(() => sortHomes(care?.homes ?? []), [care]);
  const updatedHint = care?.updated ? `판정 ${stampOf(care.updated)}` : null;

  return (
    <Screen>
      <View style={styles.flex}>
        <EngineBanner
          engine={engine}
          care={care}
          loading={loading}
          fetchError={error}
          updatedHint={updatedHint}
        />
        <FlatList
          data={homes}
          keyExtractor={(h) => h.home}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} tintColor={theme.brand} />}
          ListEmptyComponent={
            !loading ? <Text style={styles.empty}>표시할 세대가 없습니다.</Text> : null
          }
          renderItem={({ item }) => <HomeListItem home={item} nowMs={nowMs} />}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  listContent: { paddingTop: 8, paddingBottom: 24 },
  empty: { textAlign: 'center', color: theme.muted, marginTop: 40 },
});
