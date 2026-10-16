import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import { HomeAbsencePanel } from '@/components/HomeAbsencePanel';
import { HomeContacts } from '@/components/HomeContacts';
import { HomeTags } from '@/components/HomeTags';
import { HomeTimeline } from '@/components/HomeTimeline';
import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import { PATTERN_KO, SEV, fmtAgo, fmtMinutes, idleBar, secondsSince, tempStatus } from '@/lib/format';
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
        <ActivityIndicator size="large" color={theme.brand} />
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
  const temp = tempStatus(h.temp, h.temp_limit_s, nowMs);
  const idle = idleBar(activity, h.idle_min, h.idle_levels, {
    away: !!h.away,
    lifeKnown: h.life_known !== false,
  });

  return (
    <ScrollView style={styles.flex} contentContainerStyle={styles.pad}>
      <View style={styles.head}>
        <Text style={styles.title}>{h.home}호</Text>
        <HomeTags home={h} />
      </View>
      {h.basis ? <Text style={styles.reason}>{h.basis}</Text> : h.reason ? <Text style={styles.reason}>{h.reason}</Text> : null}
      {idle ? (
        <View style={styles.idle}>
          <Text style={styles.idleBig}>{idle.big}</Text>
          <Text style={styles.idleCap}>{idle.text}</Text>
          <View
            style={styles.track}
            accessibilityRole="progressbar"
            accessibilityLabel={idle.text}
            accessibilityValue={{
              min: 0,
              max: idle.limitMin,
              now: idle.elapsed == null ? undefined : Math.round(idle.elapsed / 60),
            }}
          >
            <View
              style={[
                styles.fill,
                idle.tone === 'urgent'
                  ? styles.fillUrgent
                  : idle.tone === 'watch'
                    ? styles.fillWatch
                    : idle.tone === 'held'
                      ? styles.fillHeld
                      : styles.fillOk,
                { width: idle.ratio == null ? '0%' : `${idle.ratio * 100}%` },
              ]}
            />
          </View>
        </View>
      ) : null}
      <HomeContacts home={h.home} />

      <View style={styles.card}>
        <Row
          label="마지막 통신"
          value={fmtAgo(contact)}
          flag={h.severity === 'CHECK_DEVICE' || h.device_check ? '두절' : undefined}
        />
        <Row
          label="마지막 움직임"
          value={fmtAgo(activity)}
          note={
            h.device_check && h.severity === 'URGENT'
              ? '· 두절 이후는 재판단하지 않음, 기존 긴급 확인 유지'
              : !h.life_known
                ? '(기록 기준) · 통신 두절 이후는 확인 불가'
                : undefined
          }
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
        {temp ? (
          <Row
            label="온도"
            value={temp.text}
            note={temp.silent && temp.when ? `· 마지막 ${temp.when}` : undefined}
          />
        ) : null}
        {h.patterns && h.patterns.length ? (
          <Row label="시간 패턴" value={h.patterns.map((c) => PATTERN_KO[c] || c).join(' · ')} />
        ) : null}
        <Row
          label="판정 시각"
          value={judged != null ? fmtAgo(judged) : '—'}
          flag={judged != null && judged > 30 ? '판정이 갱신되지 않음' : undefined}
        />
      </View>

      <HomeTimeline home={h.home} judgedAt={h.judged_at} />
      <HomeAbsencePanel home={h.home} onChanged={load} />
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
  flex: { flex: 1, backgroundColor: theme.bg },
  pad: { padding: theme.screenPad, paddingBottom: 32 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.bg },
  err: { color: theme.urgent },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: theme.text },
  reason: { marginBottom: 16, lineHeight: 22, color: theme.text2 },
  idle: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: theme.border,
    gap: 6,
  },
  idleBig: { fontSize: 28, fontWeight: '700', color: theme.text, letterSpacing: -0.4 },
  idleCap: { fontSize: 14, lineHeight: 20, color: theme.text2 },
  track: { height: 10, borderRadius: 999, backgroundColor: theme.surface2, overflow: 'hidden', marginTop: 4 },
  fill: { height: '100%', borderRadius: 999 },
  fillOk: { backgroundColor: theme.normal },
  fillWatch: { backgroundColor: theme.watch },
  fillUrgent: { backgroundColor: theme.urgent },
  fillHeld: { backgroundColor: theme.muted },
  card: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    gap: 12,
    borderWidth: 1,
    borderColor: theme.border,
    ...theme.shadowSm,
  },
  row: { gap: 4 },
  dt: { fontSize: 12, color: theme.muted, fontWeight: '600' },
  dd: { fontSize: 16, lineHeight: 22, color: theme.text },
  flag: { color: theme.device, fontWeight: '600' },
  note: { color: theme.muted, fontSize: 13 },
});
