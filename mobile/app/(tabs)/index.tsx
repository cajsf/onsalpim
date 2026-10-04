import { useCallback, useMemo } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { EngineBanner } from '@/components/EngineBanner';
import { HomeListItem } from '@/components/HomeListItem';
import { useSettings } from '@/context/SettingsContext';
import { SEV_ORDER } from '@/lib/format';
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

  return (
    <View style={styles.flex}>
      <EngineBanner
        engine={engine}
        care={care}
        loading={loading}
        fetchError={error}
      />
      <FlatList
        data={homes}
        keyExtractor={(h) => h.home}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
        ListEmptyComponent={
          !loading ? (
            <Text style={styles.empty}>표시할 세대가 없습니다.</Text>
          ) : null
        }
        renderItem={({ item }) => <HomeListItem home={item} nowMs={nowMs} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#fafafa' },
  empty: { textAlign: 'center', color: '#757575', marginTop: 40 },
});
