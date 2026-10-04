import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';

import type { RuleRecord } from '@/lib/types';
import { condText } from '@/lib/ruleText';

type Props = { rule: RuleRecord; pending?: boolean };

export function RuleListItem({ rule: r, pending }: Props) {
  const line = `"${r.sentence}"`;

  return (
    <Link href={{ pathname: '/rule/[id]', params: { id: String(r.id) } }} asChild>
      <Pressable style={StyleSheet.flatten([styles.row, pending && styles.pending])}>
        <View style={styles.head}>
          {pending ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>승인 대기</Text>
            </View>
          ) : (
            <View style={[styles.badge, styles.active]}>
              <Text style={styles.badgeTextActive}>적용 중</Text>
            </View>
          )}
          <Text style={styles.id}>#{r.id}</Text>
        </View>
        <Text style={styles.sentence}>{line}</Text>
        <Text style={styles.meta} numberOfLines={2}>
          {condText(r.rule as Parameters<typeof condText>[0])}
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
  pending: { backgroundColor: '#fffde7' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  badge: { backgroundColor: '#ffe082', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  badgeText: { fontSize: 11, fontWeight: '700', color: '#f57f17' },
  active: { backgroundColor: '#e8f5e9' },
  badgeTextActive: { fontSize: 11, fontWeight: '700', color: '#2e7d32' },
  id: { color: '#757575', fontSize: 12 },
  sentence: { fontWeight: '600', marginBottom: 4, lineHeight: 20 },
  meta: { color: '#616161', fontSize: 13 },
});
