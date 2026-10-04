import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ALERT_STATE, timeOf } from '@/lib/format';
import type { AlertRecord } from '@/lib/types';
import type { ApiClient } from '@/lib/api';

type Props = {
  alert: AlertRecord;
  api: ApiClient;
  onUpdated: (log: AlertRecord['log'], state: string | null) => void;
};

export function AlertActions({ alert: a, api, onUpdated }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [memoOpen, setMemoOpen] = useState(false);
  const [memo, setMemo] = useState('');

  const actionable = ['open', 'ack', 'progress'].includes(a.state ?? '');

  async function act(status: 'ack' | 'progress' | 'done' | 'late' | 'edit') {
    if (busy) return;
    if (status === 'done' && !memoOpen) {
      setMemoOpen(true);
      return;
    }
    setBusy(true);
    setError('');
    const withMemo = status === 'done' || status === 'edit';
    const r = await api.actAlert(a.id, status, withMemo ? memo : '');
    setBusy(false);
    if (!r.ok) {
      setError((r.errors || []).join(' '));
      return;
    }
    setMemoOpen(false);
    setMemo('');
    const log = r.log ?? a.log;
    const statusKey = [...log].reverse().find((l) => l.status !== 'edit')?.status ?? a.state;
    onUpdated(log, statusKey ?? null);
  }

  return (
    <View style={styles.wrap}>
      {a.log.length > 0 ? (
        <View style={styles.logBox}>
          <Text style={styles.logTitle}>대응 기록</Text>
          {a.log.map((l, i) => (
            <Text key={i} style={styles.logLine}>
              {timeOf(l.at)} · {ALERT_STATE[l.status]?.ko ?? l.status} · {l.by}
              {l.memo ? ` — ${l.memo}` : ''}
            </Text>
          ))}
        </View>
      ) : null}

      {error ? <Text style={styles.err}>{error}</Text> : null}

      {a.state === 'missed' ? (
        <Pressable style={styles.btn} onPress={() => act('late')} disabled={busy}>
          {busy ? <ActivityIndicator /> : <Text style={styles.btnText}>뒤늦게 확인</Text>}
        </Pressable>
      ) : null}

      {actionable ? (
        <View style={styles.row}>
          <Pressable style={[styles.btn, styles.ghost]} onPress={() => act('ack')} disabled={busy}>
            <Text style={styles.btnText}>확인</Text>
          </Pressable>
          <Pressable style={[styles.btn, styles.ghost]} onPress={() => act('progress')} disabled={busy}>
            <Text style={styles.btnText}>방문·연락 중</Text>
          </Pressable>
          <Pressable style={styles.btn} onPress={() => act('done')} disabled={busy}>
            <Text style={styles.btnTextDark}>조치 완료</Text>
          </Pressable>
        </View>
      ) : null}

      {memoOpen ? (
        <View style={styles.memoBox}>
          <Text style={styles.memoLabel}>무엇을 했는지 적어 주세요 (필수)</Text>
          <TextInput
            style={styles.input}
            multiline
            value={memo}
            onChangeText={setMemo}
            placeholder="예: 전화로 안부 확인, 내일 방문 예정"
          />
          <View style={styles.row}>
            <Pressable style={[styles.btn, styles.ghost]} onPress={() => setMemoOpen(false)}>
              <Text style={styles.btnText}>취소</Text>
            </Pressable>
            <Pressable style={styles.btn} onPress={() => act('done')} disabled={busy || !memo.trim()}>
              <Text style={styles.btnTextDark}>저장</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12, padding: 16 },
  logBox: { backgroundColor: '#f5f5f5', padding: 12, borderRadius: 8 },
  logTitle: { fontWeight: '600', marginBottom: 6 },
  logLine: { color: '#424242', marginBottom: 4, lineHeight: 18 },
  err: { color: '#c62828' },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  btn: {
    backgroundColor: '#1565c0',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
    minWidth: 88,
    alignItems: 'center',
  },
  ghost: { backgroundColor: '#e3f2fd' },
  btnText: { color: '#1565c0', fontWeight: '600' },
  btnTextDark: { color: '#fff', fontWeight: '600' },
  memoBox: { gap: 8 },
  memoLabel: { fontWeight: '600' },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 10,
    minHeight: 80,
    textAlignVertical: 'top',
    backgroundColor: '#fff',
  },
});
