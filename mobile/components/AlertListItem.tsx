import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';

import { SeverityTag } from '@/components/SeverityTag';
import { STATE_COLORS } from '@/constants/severityColors';
import { ALERT_STATE, SEV, timeOf } from '@/lib/format';
import type { AlertRecord } from '@/lib/types';

type Props = { alert: AlertRecord; compact?: boolean };

export function AlertListItem({ alert: a, compact }: Props) {
  const st = a.state ? ALERT_STATE[a.state] : null;
  const stateColor = st ? STATE_COLORS[st.cls] : null;
  const line =
    `${a.home}호 ` +
    (!a.welfare && a.from ? `${SEV[a.from]?.ko ?? a.from} → ` : '') +
    `${SEV[a.to]?.ko ?? a.to} · ${a.reason}`;

  return (
    <Link href={`/alert/${encodeURIComponent(a.id)}`} asChild>
      {/* RN Web: Link+asChild 는 자식 style 배열을 CSS에 못 넣어 크래시 — flatten 필수 (#31352) */}
      <Pressable style={StyleSheet.flatten([styles.row, a.state === 'open' && styles.open])}>
        <View style={styles.head}>
          {a.welfare ? (
            <SeverityTag severity="URGENT" label="안부 확인" />
          ) : (
            <SeverityTag severity={a.to} />
          )}
          {st && stateColor ? (
            <View
              style={StyleSheet.flatten([styles.state, { backgroundColor: stateColor.bg }])}>
              <Text style={{ color: stateColor.text, fontSize: 11, fontWeight: '600' }}>
                {st.ko}
              </Text>
            </View>
          ) : null}
          <Text style={styles.time}>{compact ? timeOf(a.ts) : a.ts.slice(5, 16).replace('T', ' ')}</Text>
        </View>
        <Text style={styles.body}>{line}</Text>
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
  open: { backgroundColor: '#fff5f5' },
  head: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 6 },
  state: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  time: { marginLeft: 'auto', color: '#757575', fontSize: 12, fontFamily: 'SpaceMono' },
  body: { color: '#333', lineHeight: 20 },
});
