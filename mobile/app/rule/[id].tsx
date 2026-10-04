import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { RulePreviewPanel } from '@/components/RulePreviewPanel';
import { useSettings } from '@/context/SettingsContext';
import {
  actText,
  condText,
  previewEnabled,
  previewReplace,
  scopeText,
} from '@/lib/ruleText';
import type { RuleRecord } from '@/lib/types';

export default function RuleDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { api } = useSettings();
  const [rule, setRule] = useState<RuleRecord | null>(null);
  const [fillValue, setFillValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmReject, setConfirmReject] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const rid = parseInt(String(id), 10);
    if (!Number.isFinite(rid)) return;
    setLoading(true);
    try {
      const rules = await api.getRules();
      const found = rules.find((r) => r.id === rid);
      if (!found) setError('규칙을 찾을 수 없습니다.');
      else {
        setRule(found);
        setError('');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    load();
  }, [load]);

  const body = rule?.rule as Parameters<typeof condText>[0];
  const isPending = rule?.status === 'pending';
  const needsFill = Boolean(rule?.questions?.length);
  const fill = useMemo(() => {
    const w = body?.when;
    if (String(w?.value ?? '').trim()) return '';
    return fillValue.trim();
  }, [body, fillValue]);

  const replace = previewReplace(rule?.conflicts);
  const canPreview = previewEnabled(body, fill);

  async function approve() {
    if (!rule || busy) return;
    setBusy(true);
    setError('');
    const res = await api.approveRule(rule.id, fill || undefined, replace);
    setBusy(false);
    if (!res.ok) {
      setError(res.errors?.join(' ') || '승인에 실패했습니다.');
      return;
    }
    router.back();
  }

  async function reject() {
    if (!rule || busy) return;
    if (!confirmReject) {
      setConfirmReject(true);
      setTimeout(() => setConfirmReject(false), 4000);
      return;
    }
    setBusy(true);
    setError('');
    const res = await api.rejectRule(rule.id);
    setBusy(false);
    if (!res.ok) {
      setError(res.errors?.join(' ') || '거부에 실패했습니다.');
      return;
    }
    router.back();
  }

  if (loading && !rule) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error && !rule) {
    return (
      <View style={styles.center}>
        <Text style={styles.err}>{error}</Text>
      </View>
    );
  }

  if (!rule) return null;

  const blockApprove = (rule.conflicts || []).some((c) => !c.covers_all);

  return (
    <ScrollView style={styles.flex} contentContainerStyle={styles.pad}>
      <Text style={styles.sentence}>"{rule.sentence}"</Text>
      <View style={styles.card}>
        <Row label="조건" value={condText(body)} />
        <Row label="동작" value={actText(body)} />
        <Row label="적용 대상" value={scopeText(body)} />
      </View>

      {(rule.questions || []).map((q) => (
        <Text key={q} style={styles.clarify}>
          {q}
        </Text>
      ))}

      {(rule.conflicts || []).map((c) => (
        <Text key={c.id} style={styles.warn}>
          ⚠ 규칙 #{c.id}({c.summary})과 {c.homes.join(', ')}호에서 겹칩니다.
          {c.covers_all ? ' 승인 시 기존 규칙을 끕니다.' : ' 일부 세대만 겹쳐 대체할 수 없습니다.'}
        </Text>
      ))}

      {isPending && needsFill ? (
        <>
          <Text style={styles.lbl}>기준값 (예: 8시간, 480)</Text>
          <TextInput style={styles.input} value={fillValue} onChangeText={setFillValue} />
        </>
      ) : null}

      {isPending ? (
        <RulePreviewPanel
          ruleId={rule.id}
          fillValue={fill}
          replace={replace}
          enabled={canPreview}
        />
      ) : null}

      {error ? <Text style={styles.err}>{error}</Text> : null}

      {isPending ? (
        <View style={styles.actions}>
          <Pressable
            style={StyleSheet.flatten([styles.btn, styles.ghost, confirmReject && styles.danger])}
            onPress={reject}
            disabled={busy}>
            <Text style={styles.ghostText}>
              {confirmReject ? '한 번 더 누르면 거부' : rule.conflicts?.length ? '기존 규칙 유지' : '거부'}
            </Text>
          </Pressable>
          <Pressable
            style={StyleSheet.flatten([styles.btn, blockApprove && styles.disabled])}
            onPress={approve}
            disabled={busy || blockApprove}>
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.btnText}>
                {rule.conflicts?.length ? '새 규칙 적용' : '승인하기'}
              </Text>
            )}
          </Pressable>
        </View>
      ) : (
        <Text style={styles.muted}>이 규칙은 이미 승인·적용된 상태입니다.</Text>
      )}
    </ScrollView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.dt}>{label}</Text>
      <Text style={styles.dd}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#fafafa' },
  pad: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  err: { color: '#c62828', marginTop: 8 },
  sentence: { fontSize: 18, fontWeight: '700', lineHeight: 26, marginBottom: 12 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 14, gap: 10 },
  row: { gap: 4 },
  dt: { fontSize: 12, color: '#757575', fontWeight: '600' },
  dd: { fontSize: 15, lineHeight: 22 },
  clarify: { color: '#1565c0', marginTop: 10, lineHeight: 20 },
  warn: { color: '#e65100', marginTop: 8, lineHeight: 20, fontSize: 13 },
  lbl: { marginTop: 12, fontWeight: '600' },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 10, marginTop: 6 },
  muted: { color: '#757575', marginTop: 16 },
  actions: { flexDirection: 'row', gap: 10, marginTop: 16 },
  btn: {
    flex: 1,
    backgroundColor: '#1565c0',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  btnText: { color: '#fff', fontWeight: '700' },
  ghost: { backgroundColor: '#e3f2fd' },
  ghostText: { color: '#1565c0', fontWeight: '600' },
  danger: { backgroundColor: '#ffebee' },
  disabled: { opacity: 0.45 },
});
