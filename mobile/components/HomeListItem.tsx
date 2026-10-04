import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';

import { SeverityTag } from '@/components/SeverityTag';
import { fmtAgo, secondsSince } from '@/lib/format';
import type { CareHome } from '@/lib/types';

type Props = { home: CareHome; nowMs: number };

export function HomeListItem({ home, nowMs }: Props) {
  const contact = secondsSince(home.last_contact_at, nowMs) ?? home.silent_s ?? null;
  const activity = secondsSince(home.last_activity_at, nowMs) ?? home.idle_s ?? null;

  return (
    <Link href={`/home/${home.home}`} asChild>
      <Pressable style={styles.row}>
        <View style={styles.head}>
          <Text style={styles.title}>{home.home}호</Text>
          {home.welfare_check ? (
            <SeverityTag severity="CHECK_DEVICE" label="안부 확인" />
          ) : (
            <SeverityTag severity={home.severity} />
          )}
        </View>
        {home.reason ? <Text style={styles.reason}>{home.reason}</Text> : null}
        <Text style={styles.meta}>
          통신 {fmtAgo(contact)} · 움직임 {fmtAgo(activity)}
        </Text>
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  row: {
    padding: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#ddd',
    backgroundColor: '#fff',
  },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  title: { fontSize: 17, fontWeight: '700' },
  reason: { color: '#333', marginBottom: 4 },
  meta: { color: '#757575', fontSize: 13 },
});
