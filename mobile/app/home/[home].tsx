import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import { SeverityTag } from '@/components/SeverityTag';
import { useSettings } from '@/context/SettingsContext';
import { fmtAgo, fmtMinutes, secondsSince, SEV } from '@/lib/format';
import type { CareHome } from '@/lib/types';
import { useNow } from '@/hooks/useNow';

export default function HomeDetailScreen() {
  const { home: homeId } = useLocalSearchParams<{ home: string }>();
  const { api } = useSettings();
  const nowMs = useNow();
  const [home, setHome] = useState<CareHome | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!homeId) return;
    setLoading(true);
    try {
      const care = await api.getCare();
      const found = care.homes.find((h) => h.home === homeId);
      if (!found) setError(`${homeId}호를 찾을 수 없습니다.`);
      else {
        setHome(found);
        setError('');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [api, homeId]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && !home) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error || !home) {
    return (
      <View style={styles.center}>
        <Text style={styles.err}>{error || '세대 없음'}</Text>
      </View>
    );
  }

  const h = home;
  const contact = secondsSince(h.last_contact_at, nowMs) ?? h.silent_s ?? null;
  const activity = secondsSince(h.last_activity_at, nowMs) ?? h.idle_s ?? null;
  const judged = secondsSince(h.judged_at, nowMs);

  return (
    <ScrollView style={styles.flex} contentContainerStyle={styles.pad}>
      <View style={styles.head}>
        <Text style={styles.title}>{h.home}호</Text>
        {h.welfare_check ? (
          <SeverityTag severity="CHECK_DEVICE" label="안부 확인" />
        ) : (
          <SeverityTag severity={h.severity} />
        )}
      </View>
      {h.reason ? <Text style={styles.reason}>{h.reason}</Text> : null}

      <View style={styles.card}>
        <Row label="마지막 통신" value={fmtAgo(contact)} flag={h.severity === 'CHECK_DEVICE' ? '두절' : undefined} />
        <Row
          label="마지막 움직임"
          value={fmtAgo(activity)}
          note={!h.life_known ? '(기록 기준) · 통신 두절 이후는 확인 불가' : undefined}
        />
        {h.idle_levels && h.idle_levels.length > 1 ? (
          <Row
            label="무활동 기준"
            value={h.idle_levels
              .map((lv) => `${fmtMinutes(lv.minutes)} → ${SEV[lv.severity]?.ko}`)
              .join(' · ')}
          />
        ) : h.idle_min != null ? (
          <Row label="무활동 기준" value={`${fmtMinutes(h.idle_min)} → ${SEV.URGENT.ko}`} />
        ) : null}
        {h.away ? (
          <Row
            label="부재"
            value={`${h.away.until.slice(5, 16).replace('T', ' ')}까지 · ${h.away.reason}`}
          />
        ) : null}
        {h.battery != null ? <Row label="배터리" value={`${Math.round(h.battery)}%`} /> : null}
        <Row label="판정 시각" value={judged != null ? fmtAgo(judged) : '—'} />
      </View>
    </ScrollView>
  );
}

function Row({
  label,
  value,
  flag,
  note,
}: {
  label: string;
  value: string;
  flag?: string;
  note?: string;
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.dt}>{label}</Text>
      <Text style={styles.dd}>
        {value}
        {flag ? <Text style={styles.flag}> · {flag}</Text> : null}
        {note ? <Text style={styles.note}> {note}</Text> : null}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#fafafa' },
  pad: { padding: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  err: { color: '#c62828' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  title: { fontSize: 24, fontWeight: '700' },
  reason: { marginBottom: 16, lineHeight: 22, color: '#333' },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 14, gap: 12 },
  row: { gap: 4 },
  dt: { fontSize: 12, color: '#757575', fontWeight: '600' },
  dd: { fontSize: 16, lineHeight: 22 },
  flag: { color: '#1565c0', fontWeight: '600' },
  note: { color: '#757575', fontSize: 13 },
});
