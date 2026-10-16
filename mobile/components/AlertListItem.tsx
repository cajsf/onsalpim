import { Link } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { ListCard } from '@/components/ListCard';
import { SeverityTag } from '@/components/SeverityTag';
import { STATE_COLORS, severityBarColor } from '@/constants/severityColors';
import { theme } from '@/constants/theme';
import { ALERT_STATE, SEV, alertIsLife, alertKo, alertSeverity, timeOf } from '@/lib/format';
import type { AlertRecord } from '@/lib/types';

type Props = { alert: AlertRecord; compact?: boolean };

export function AlertListItem({ alert: a, compact }: Props) {
  const st = a.state ? ALERT_STATE[a.state] : null;
  const stateColor = st ? STATE_COLORS[st.cls] : null;
  const life = alertIsLife(a);
  const bar = severityBarColor(alertSeverity(a), { welfare: a.welfare, life });
  const name = alertKo(a);
  const sameDevice = a.device_check && a.from === a.to;
  const fromKo = a.from ? (SEV[a.from]?.ko ?? a.from) : '';
  const arrow = !a.welfare && !sameDevice && fromKo ? `${fromKo} → ${name} · ` : '';

  return (
    <Link href={`/alert/${encodeURIComponent(a.id)}`} asChild>
      <ListCard barColor={bar} highlight={a.state === 'open' || a.state === 'assign'}>
        <View style={styles.head}>
          <SeverityTag severity={alertSeverity(a)} label={name} tone={life ? 'life' : undefined} />
          {a.assignee ? (
            <View style={styles.who}>
              <Text style={styles.whoText}>{a.assignee}</Text>
            </View>
          ) : null}
          {st && stateColor ? (
            <View style={StyleSheet.flatten([styles.state, { backgroundColor: stateColor.bg }])}>
              <Text style={{ color: stateColor.text, fontSize: 11, fontWeight: '600' }}>{st.ko}</Text>
            </View>
          ) : null}
          <Text style={styles.time}>{compact ? timeOf(a.ts) : a.ts.slice(5, 16).replace('T', ' ')}</Text>
        </View>
        <Text style={styles.body} numberOfLines={3}>
          {a.outage ? '전체 ' : `${a.home}호 `}
          {arrow}
          {a.reason}
        </Text>
      </ListCard>
    </Link>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 6 },
  who: { backgroundColor: theme.lifeSoft, paddingHorizontal: 6, paddingVertical: 2, borderRadius: theme.radiusSm },
  whoText: { color: theme.life, fontSize: 11, fontWeight: '600' },
  state: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: theme.radiusSm },
  time: { marginLeft: 'auto', color: theme.muted, fontSize: 12 },
  body: { color: theme.text2, lineHeight: 20, fontSize: 14 },
});
