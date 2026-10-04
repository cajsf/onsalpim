import { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useSettings } from '@/context/SettingsContext';
import { theme } from '@/constants/theme';
import { SEV, timeOf } from '@/lib/format';
import type { Severity } from '@/lib/types';
import { useNow } from '@/hooks/useNow';

const WINDOWS = [
  { h: 0.25, label: '15분' },
  { h: 1, label: '1시간' },
  { h: 24, label: '24시간' },
] as const;

type Props = { home: string; judgedAt?: string | null };

export function HomeTimeline({ home, judgedAt }: Props) {
  const { api } = useSettings();
  const nowMs = useNow();
  const [hours, setHours] = useState(1);
  const [sev, setSev] = useState<[string, string, string][]>([]);
  const [move, setMove] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const h = await api.getHistory(home);
      setSev(h.sev || []);
      setMove((h.move || []).map(String));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [api, home]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const start = nowMs - hours * 3600e3;
  const end = nowMs;

  const events = useMemo(() => {
    const out: { at: number; kind: 'sev' | 'move'; label: string }[] = [];
    for (const [at, to] of sev) {
      const ms = Date.parse(at);
      if (ms >= start && ms <= end) {
        out.push({
          at: ms,
          kind: 'sev',
          label: `판정 → ${SEV[to as Severity]?.ko ?? to}`,
        });
      }
    }
    for (const at of move) {
      const ms = Date.parse(at);
      if (ms >= start && ms <= end) {
        out.push({ at: ms, kind: 'move', label: '움직임 관측' });
      }
    }
    out.sort((a, b) => b.at - a.at);
    return out.slice(0, 40);
  }, [sev, move, start, end]);

  const summary = useMemo(() => {
    const moves = events.filter((e) => e.kind === 'move').length;
    const urgent = events.filter((e) => e.label.includes('긴급')).length;
    const parts = [`움직임 ${moves}회`];
    if (urgent) parts.push(`긴급 판정 ${urgent}회`);
    if (judgedAt) parts.push(`최근 판정 ${timeOf(judgedAt)}`);
    return parts.join(' · ');
  }, [events, judgedAt]);

  return (
    <View style={styles.card}>
      <Text style={styles.title}>타임라인</Text>
      <Text style={styles.muted}>{failed ? '불러오지 못했습니다' : summary}</Text>
      <View style={styles.seg}>
        {WINDOWS.map((w) => (
          <Pressable
            key={w.h}
            style={StyleSheet.flatten([styles.chip, hours === w.h && styles.chipOn])}
            onPress={() => setHours(w.h)}>
            <Text style={StyleSheet.flatten([styles.chipText, hours === w.h && styles.chipTextOn])}>
              {w.label}
            </Text>
          </Pressable>
        ))}
      </View>
      {events.length === 0 ? (
        <Text style={styles.muted}>이 구간에 기록이 없습니다.</Text>
      ) : (
        events.map((e) => (
          <View key={`${e.kind}-${e.at}`} style={styles.row}>
            <Text style={styles.time}>{timeOf(new Date(e.at).toISOString().slice(0, 19))}</Text>
            <Text style={e.kind === 'move' ? styles.move : styles.sev}>{e.label}</Text>
          </View>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    marginTop: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: theme.border,
    ...theme.shadowSm,
  },
  title: { fontSize: 16, fontWeight: '700', color: theme.text },
  muted: { color: theme.muted, fontSize: 13, lineHeight: 18 },
  seg: { flexDirection: 'row', gap: 8, marginVertical: 4 },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    backgroundColor: theme.surface2,
    borderWidth: 1,
    borderColor: theme.border,
  },
  chipOn: { backgroundColor: theme.brandSoft, borderColor: theme.brand },
  chipText: { fontSize: 13, color: theme.text2, fontWeight: '600' },
  chipTextOn: { color: theme.brandDim },
  row: { flexDirection: 'row', gap: 10, paddingVertical: 4 },
  time: { width: 48, fontFamily: 'SpaceMono', fontSize: 12, color: theme.muted },
  move: { flex: 1, color: theme.normal },
  sev: { flex: 1, color: theme.text2 },
});
