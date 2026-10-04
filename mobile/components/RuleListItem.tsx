import { Link } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { ListCard } from '@/components/ListCard';
import { theme } from '@/constants/theme';
import { condText } from '@/lib/ruleText';
import type { RuleRecord } from '@/lib/types';

type Props = { rule: RuleRecord; pending?: boolean };

export function RuleListItem({ rule: r, pending }: Props) {
  const bar = pending ? theme.watch : theme.normal;

  return (
    <Link href={{ pathname: '/rule/[id]', params: { id: String(r.id) } }} asChild>
      <ListCard barColor={bar} highlight={pending}>
        <View style={styles.head}>
          {pending ? (
            <View style={styles.badgePending}>
              <Text style={styles.badgePendingText}>승인 대기</Text>
            </View>
          ) : (
            <View style={styles.badgeActive}>
              <Text style={styles.badgeActiveText}>적용 중</Text>
            </View>
          )}
          <Text style={styles.id}>#{r.id}</Text>
        </View>
        <Text style={styles.sentence} numberOfLines={2}>
          "{r.sentence}"
        </Text>
        <Text style={styles.meta} numberOfLines={2}>
          {condText(r.rule as Parameters<typeof condText>[0])}
        </Text>
      </ListCard>
    </Link>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  badgePending: { backgroundColor: theme.watchSoft, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  badgePendingText: { fontSize: 11, fontWeight: '700', color: theme.watch },
  badgeActive: { backgroundColor: theme.normalSoft, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  badgeActiveText: { fontSize: 11, fontWeight: '700', color: theme.normal },
  id: { color: theme.muted, fontSize: 12 },
  sentence: { fontWeight: '600', marginBottom: 4, lineHeight: 20, color: theme.text },
  meta: { color: theme.text2, fontSize: 13 },
});
