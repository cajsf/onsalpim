import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { Screen } from '@/components/Screen';
import { SettingsPanel } from '@/components/SettingsPanel';
import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import { devName, fmtDurationSec, stampOf } from '@/lib/format';
import type { MonthlyReportRow } from '@/lib/types';

type DeviceRow = { path: string; kind: string; type: string; desc: string };

const REPORT_LIMITS = [
  { s: 5 * 86400, label: '5일 이상 (보고)' },
  { s: 60, label: '1분 (시연)' },
];

function thisMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export default function MoreScreen() {
  const { api } = useSettings();
  const [section, setSection] = useState<'menu' | 'report' | 'devices'>('menu');

  const [month, setMonth] = useState(thisMonth());
  const [minS, setMinS] = useState(REPORT_LIMITS[0].s);
  const [rows, setRows] = useState<MonthlyReportRow[]>([]);
  const [reportErr, setReportErr] = useState('');
  const [reportLoading, setReportLoading] = useState(false);

  const [devices, setDevices] = useState<DeviceRow[]>([]);
  const [devLoading, setDevLoading] = useState(false);
  const [devErr, setDevErr] = useState('');

  const loadReport = useCallback(async () => {
    setReportLoading(true);
    setReportErr('');
    try {
      const r = await api.getMonthlyReport(month, minS);
      setRows(r.rows);
    } catch (e) {
      setReportErr(e instanceof Error ? e.message : String(e));
    } finally {
      setReportLoading(false);
    }
  }, [api, month, minS]);

  const loadDevices = useCallback(async (force = false) => {
    setDevLoading(true);
    setDevErr('');
    try {
      const tree = await api.getDevices(force);
      const list = Array.isArray(tree) ? tree : [];
      setDevices(
        list.map((d: { path?: string; meta?: { kind?: string; type?: string; desc?: string } }) => ({
          path: d.path || '',
          kind: d.meta?.kind || '?',
          type: d.meta?.type || '?',
          desc: d.meta?.desc || devName(d.path),
        })),
      );
    } catch (e) {
      setDevErr(e instanceof Error ? e.message : String(e));
    } finally {
      setDevLoading(false);
    }
  }, [api]);

  if (section === 'menu') {
    return (
      <Screen>
        <ScrollView style={styles.flex} contentContainerStyle={styles.pad}>
          <Text style={styles.h1}>더보기</Text>
          <Pressable style={styles.menuItem} onPress={() => { setSection('report'); loadReport(); }}>
            <Text style={styles.menuTitle}>📋 월간 보고 초안</Text>
            <Text style={styles.menuSub}>5일 이상 미감지·두절 등 명단</Text>
          </Pressable>
          <Pressable style={styles.menuItem} onPress={() => { setSection('devices'); loadDevices(); }}>
            <Text style={styles.menuTitle}>🔌 기기 목록</Text>
            <Text style={styles.menuSub}>공용 서버에서 읽은 장치 트리</Text>
          </Pressable>
          <View style={styles.spacer} />
          <SettingsPanel />
        </ScrollView>
      </Screen>
    );
  }

  if (section === 'report') {
    return (
      <Screen>
        <Pressable style={styles.back} onPress={() => setSection('menu')}>
          <Text style={styles.backText}>← 더보기</Text>
        </Pressable>
        <ScrollView style={styles.flex} contentContainerStyle={styles.pad}>
          <Text style={styles.h1}>월간 보고</Text>
          <Text style={styles.lbl}>월 (YYYY-MM)</Text>
          <TextInput style={styles.input} value={month} onChangeText={setMonth} autoCapitalize="none" />
          <View style={styles.chips}>
            {REPORT_LIMITS.map((l) => (
              <Pressable
                key={l.s}
                style={StyleSheet.flatten([styles.chip, minS === l.s && styles.chipOn])}
                onPress={() => setMinS(l.s)}>
                <Text style={StyleSheet.flatten([styles.chipText, minS === l.s && styles.chipTextOn])}>
                  {l.label}
                </Text>
              </Pressable>
            ))}
          </View>
          <Pressable style={styles.loadBtn} onPress={loadReport}>
            <Text style={styles.loadBtnText}>불러오기</Text>
          </Pressable>
          {reportLoading ? <ActivityIndicator style={{ marginTop: 16 }} /> : null}
          {reportErr ? <Text style={styles.err}>{reportErr}</Text> : null}
          {rows.map((r, i) => (
            <View key={`${r.home}-${r.start}-${i}`} style={styles.card}>
              <Text style={styles.cardTitle}>
                {r.home}호 · {r.kind}
              </Text>
              <Text style={styles.cardBody}>
                {stampOf(r.start)} ~ {r.end ? stampOf(r.end) : '진행 중'} · {fmtDurationSec(r.duration_s)}
              </Text>
              <Text style={styles.cardDraft}>{r.draft}</Text>
            </View>
          ))}
          {!reportLoading && !rows.length && !reportErr ? (
            <Text style={styles.muted}>해당 조건에 맞는 항목이 없습니다.</Text>
          ) : null}
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen>
      <Pressable style={styles.back} onPress={() => setSection('menu')}>
        <Text style={styles.backText}>← 더보기</Text>
      </Pressable>
      <FlatList
        style={styles.flex}
        data={devices}
        keyExtractor={(d) => d.path}
        refreshControl={
          <RefreshControl refreshing={devLoading} onRefresh={() => loadDevices(true)} />
        }
        ListHeaderComponent={
          <View style={styles.pad}>
            <Text style={styles.h1}>기기</Text>
            <Pressable style={styles.loadBtn} onPress={() => loadDevices(true)}>
              <Text style={styles.loadBtnText}>강제 새로고침</Text>
            </Pressable>
            {devErr ? <Text style={styles.err}>{devErr}</Text> : null}
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.devRow}>
            <Text style={styles.devPath}>{devName(item.path)}</Text>
            <Text style={styles.devMeta}>
              {item.kind} · {item.type} {item.desc ? `· ${item.desc}` : ''}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          !devLoading ? <Text style={[styles.muted, styles.pad]}>장치가 없습니다.</Text> : null
        }
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  pad: { padding: theme.screenPad, paddingBottom: 32 },
  h1: { fontSize: 22, fontWeight: '700', marginBottom: 12, color: theme.text },
  menuItem: {
    backgroundColor: theme.surface,
    padding: 16,
    borderRadius: theme.radius,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: theme.border,
    ...theme.shadowSm,
  },
  menuTitle: { fontSize: 17, fontWeight: '600', color: theme.text },
  menuSub: { color: theme.muted, marginTop: 4, fontSize: 13 },
  spacer: { height: 20 },
  back: {
    padding: 12,
    backgroundColor: theme.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.border,
  },
  backText: { color: theme.brandDim, fontWeight: '600' },
  lbl: { fontSize: 12, fontWeight: '600', color: theme.muted, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radiusSm,
    padding: 10,
    marginBottom: 10,
    backgroundColor: theme.surface,
    color: theme.text,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 10 },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: theme.surface2,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.border,
  },
  chipOn: { backgroundColor: theme.brandSoft, borderColor: theme.brand },
  chipText: { fontSize: 13, color: theme.text2 },
  chipTextOn: { color: theme.brandDim, fontWeight: '600' },
  loadBtn: {
    backgroundColor: theme.brand,
    padding: 12,
    borderRadius: theme.radiusSm,
    alignItems: 'center',
    marginBottom: 12,
  },
  loadBtnText: { color: '#fff', fontWeight: '600' },
  err: { color: theme.urgent, marginBottom: 8 },
  muted: { color: theme.muted, textAlign: 'center', marginTop: 20 },
  card: {
    backgroundColor: theme.surface,
    padding: 12,
    borderRadius: theme.radiusSm,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: theme.border,
    ...theme.shadowSm,
  },
  cardTitle: { fontWeight: '700', color: theme.text },
  cardBody: { color: theme.muted, marginTop: 4, fontSize: 13 },
  cardDraft: { marginTop: 6, lineHeight: 20, color: theme.text2 },
  devRow: {
    paddingHorizontal: theme.screenPad,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.border,
    backgroundColor: theme.surface,
  },
  devPath: { fontWeight: '600', color: theme.text },
  devMeta: { color: theme.muted, fontSize: 13, marginTop: 2 },
});
