import { Link } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { ListCard } from '@/components/ListCard';
import { SeverityTag } from '@/components/SeverityTag';
import { severityBarColor } from '@/constants/severityColors';
import { theme } from '@/constants/theme';
import { fmtAgo, secondsSince } from '@/lib/format';
import type { CareHome } from '@/lib/types';

type Props = { home: CareHome; nowMs: number };

export function HomeListItem({ home, nowMs }: Props) {
  const contact = secondsSince(home.last_contact_at, nowMs) ?? home.silent_s ?? null;
  const activity = secondsSince(home.last_activity_at, nowMs) ?? home.idle_s ?? null;
  const bar = severityBarColor(home.severity, home.welfare_check);
  const urgent = home.severity === 'URGENT' || home.welfare_check;

  return (
    <Link href={`/home/${home.home}`} asChild>
      <ListCard barColor={bar} highlight={urgent}>
        <View style={styles.head}>
          <Text style={styles.title}>{home.home}호</Text>
          {home.welfare_check ? (
            <SeverityTag severity="CHECK_DEVICE" label="안부 확인" />
          ) : (
            <SeverityTag severity={home.severity} />
          )}
        </View>
        {home.reason ? (
          <Text style={styles.reason} numberOfLines={2}>
            {home.reason}
          </Text>
        ) : null}
        <Text style={styles.meta}>
          통신 {fmtAgo(contact)} · 움직임 {fmtAgo(activity)}
        </Text>
      </ListCard>
    </Link>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' },
  title: { fontSize: 17, fontWeight: '700', color: theme.text },
  reason: { color: theme.text2, marginBottom: 4, lineHeight: 20, fontSize: 14 },
  meta: { color: theme.muted, fontSize: 13 },
});
