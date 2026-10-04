import { Link } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { ListCard } from '@/components/ListCard';
import { SeverityTag } from '@/components/SeverityTag';
import { STATE_COLORS, severityBarColor } from '@/constants/severityColors';
import { theme } from '@/constants/theme';
import { ALERT_STATE, SEV, timeOf } from '@/lib/format';
import type { AlertRecord, Severity } from '@/lib/types';

type Props = { alert: AlertRecord; compact?: boolean };

export function AlertListItem({ alert: a, compact }: Props) {
  const st = a.state ? ALERT_STATE[a.state] : null;
  const stateColor = st ? STATE_COLORS[st.cls] : null;
  const bar = a.welfare ? severityBarColor('URGENT', true) : severityBarColor(a.to as Severity);
  const line =
    `${a.home}호 ` +
    (!a.welfare && a.from ? `${SEV[a.from]?.ko ?? a.from} → ` : '') +
    `${SEV[a.to]?.ko ?? a.to} · ${a.reason}`;

  return (
    <Link href={`/alert/${encodeURIComponent(a.id)}`} asChild>
      <ListCard barColor={bar} highlight={a.state === 'open'}>
        <View style={styles.head}>
          {a.welfare ? (
            <SeverityTag severity="URGENT" label="안부 확인" />
          ) : (
            <SeverityTag severity={a.to} />
          )}
          {st && stateColor ? (
            <View style={StyleSheet.flatten([styles.state, { backgroundColor: stateColor.bg }])}>
              <Text style={{ color: stateColor.text, fontSize: 11, fontWeight: '600' }}>{st.ko}</Text>
            </View>
          ) : null}
          <Text style={styles.time}>{compact ? timeOf(a.ts) : a.ts.slice(5, 16).replace('T', ' ')}</Text>
        </View>
        <Text style={styles.body} numberOfLines={3}>
          {line}
        </Text>
      </ListCard>
    </Link>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 6 },
  state: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: theme.radiusSm },
  time: { marginLeft: 'auto', color: theme.muted, fontSize: 12 },
  body: { color: theme.text2, lineHeight: 20, fontSize: 14 },
});
