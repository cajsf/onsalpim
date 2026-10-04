import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import { stampOf } from '@/lib/format';
import type { AbsenceRecord } from '@/lib/types';

const REASONS = ['입원', '가족 방문', '외출·여행'];

function toLocalInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

type Props = { home: string; onChanged?: () => void };

export function HomeAbsencePanel({ home, onChanged }: Props) {
  const { api } = useSettings();
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<AbsenceRecord[]>([]);
  const [reason, setReason] = useState('');
  const [start, setStart] = useState(toLocalInput(new Date()));
  const [end, setEnd] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      setList(await api.getAbsences(home));
    } catch {
      setList([]);
    }
  }, [api, home]);

  useEffect(() => {
    load();
  }, [load]);

  function setDays(n: number) {
    const s = start ? new Date(start) : new Date();
    setEnd(toLocalInput(new Date(s.getTime() + n * 86400000)));
  }

  async function submit() {
    if (busy || !reason.trim() || !start || !end) {
      setError('사유·시작·끝을 모두 입력해 주세요.');
      return;
    }
    setBusy(true);
    setError('');
    setNotice('');
    const r = await api.addAbsence({ home, start, end, reason: reason.trim() });
    setBusy(false);
    if (!r.ok) {
      setError((r.errors || []).join(' '));
      return;
    }
    setNotice(`${home}호 부재를 등록했습니다.`);
    setReason('');
    setEnd('');
    await load();
    onChanged?.();
  }

  async function endAbsence(a: AbsenceRecord) {
    if (busy) return;
    setBusy(true);
    setError('');
    const r = await api.endAbsence(a.id);
    setBusy(false);
    if (!r.ok) {
      setError((r.errors || []).join(' '));
      return;
    }
    setNotice('부재를 해제했습니다.');
    await load();
    onChanged?.();
  }

  return (
    <View style={styles.card}>
      <Pressable
        style={styles.headBtn}
        onPress={() => {
          setOpen(!open);
          setError('');
          setNotice('');
        }}>
        <Text style={styles.title}>부재 등록 · 관리</Text>
        <Text style={styles.caret}>{open ? '▾' : '▸'}</Text>
      </Pressable>
      <Text style={styles.hint}>
        기간 중 무활동 알림은 울리지 않습니다. 기기 점검은 계속합니다.
      </Text>

      {list.length > 0 ? (
        <View style={styles.list}>
          {list.slice(0, 5).map((a) => (
            <View key={a.id} style={styles.absRow}>
              <Text style={styles.absText}>
                {a.reason} · {stampOf(a.start)} ~ {stampOf(a.end)}
                {a.ended_at ? ` (해제 ${stampOf(a.ended_at)})` : ''}
              </Text>
              {!a.ended_at && Date.parse(a.end) > Date.now() ? (
                <Pressable onPress={() => endAbsence(a)} disabled={busy}>
                  <Text style={styles.link}>해제</Text>
                </Pressable>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}

      {open ? (
        <View style={styles.form}>
          <Text style={styles.lbl}>사유</Text>
          <View style={styles.chips}>
            {REASONS.map((r) => (
              <Pressable
                key={r}
                style={StyleSheet.flatten([styles.chip, reason === r && styles.chipOn])}
                onPress={() => setReason(r)}>
                <Text style={StyleSheet.flatten([styles.chipText, reason === r && styles.chipTextOn])}>
                  {r}
                </Text>
              </Pressable>
            ))}
          </View>
          <TextInput
            style={styles.input}
            value={reason}
            onChangeText={setReason}
            placeholder="직접 입력"
            placeholderTextColor={theme.muted}
            maxLength={50}
          />
          <Text style={styles.lbl}>시작 (YYYY-MM-DDTHH:mm)</Text>
          <TextInput style={styles.input} value={start} onChangeText={setStart} autoCapitalize="none" />
          <Text style={styles.lbl}>끝</Text>
          <TextInput style={styles.input} value={end} onChangeText={setEnd} autoCapitalize="none" />
          <View style={styles.chips}>
            <Pressable style={styles.chip} onPress={() => setDays(1)}>
              <Text style={styles.chipText}>+1일</Text>
            </Pressable>
            <Pressable style={styles.chip} onPress={() => setDays(3)}>
              <Text style={styles.chipText}>+3일</Text>
            </Pressable>
            <Pressable style={styles.chip} onPress={() => setDays(7)}>
              <Text style={styles.chipText}>+7일</Text>
            </Pressable>
          </View>
          {error ? <Text style={styles.err}>{error}</Text> : null}
          {notice ? <Text style={styles.ok}>{notice}</Text> : null}
          <Pressable style={styles.submit} onPress={submit} disabled={busy}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>등록</Text>}
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    marginTop: 12,
    borderWidth: 1,
    borderColor: theme.border,
    ...theme.shadowSm,
  },
  headBtn: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontSize: 16, fontWeight: '700', color: theme.text },
  caret: { color: theme.muted, fontSize: 16 },
  hint: { color: theme.muted, fontSize: 13, marginTop: 6, lineHeight: 18 },
  list: { marginTop: 10, gap: 6 },
  absRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  absText: { flex: 1, fontSize: 13, color: theme.text2 },
  link: { color: theme.brandDim, fontWeight: '600' },
  form: { marginTop: 12, gap: 8 },
  lbl: { fontSize: 12, fontWeight: '600', color: theme.muted },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
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
  input: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radiusSm,
    padding: 10,
    fontSize: 15,
    backgroundColor: theme.surface,
    color: theme.text,
  },
  err: { color: theme.urgent },
  ok: { color: theme.normal },
  submit: {
    backgroundColor: theme.brand,
    padding: 12,
    borderRadius: theme.radiusSm,
    alignItems: 'center',
    marginTop: 4,
  },
  submitText: { color: '#fff', fontWeight: '600' },
});
