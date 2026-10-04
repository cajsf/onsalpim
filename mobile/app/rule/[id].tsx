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
import { SafeAreaView } from 'react-native-safe-area-context';

import { RulePreviewPanel } from '@/components/RulePreviewPanel';
import { theme } from '@/constants/theme';
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
        <ActivityIndicator size="large" color={theme.brand} />
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
    <View style={styles.flex}>
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
            <TextInput
              style={styles.input}
              value={fillValue}
              onChangeText={setFillValue}
              placeholder="8시간"
              placeholderTextColor={theme.muted}
            />
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

        {!isPending ? (
          <Text style={styles.muted}>이 규칙은 이미 승인·적용된 상태입니다.</Text>
        ) : null}
      </ScrollView>

      {isPending ? (
        <SafeAreaView edges={['bottom']} style={styles.footer}>
          <View style={styles.actions}>
            <Pressable
              style={StyleSheet.flatten([styles.btn, styles.ghost, confirmReject && styles.dangerGhost])}
              onPress={reject}
              disabled={busy}>
              <Text style={StyleSheet.flatten([styles.ghostText, confirmReject && styles.dangerText])}>
                {confirmReject ? '한 번 더 누르면 거부' : rule.conflicts?.length ? '기존 유지' : '거부'}
              </Text>
            </Pressable>
            <Pressable
              style={StyleSheet.flatten([styles.btn, styles.primary, blockApprove && styles.disabled])}
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
        </SafeAreaView>
      ) : null}
    </View>
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
  flex: { flex: 1, backgroundColor: theme.bg },
  pad: { padding: theme.screenPad, paddingBottom: 120 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.bg },
  err: { color: theme.urgent, marginTop: 8 },
  sentence: { fontSize: 18, fontWeight: '700', lineHeight: 26, marginBottom: 12, color: theme.text },
  card: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    gap: 10,
    borderWidth: 1,
    borderColor: theme.border,
    ...theme.shadowSm,
  },
  row: { gap: 4 },
  dt: { fontSize: 12, color: theme.muted, fontWeight: '600' },
  dd: { fontSize: 15, lineHeight: 22, color: theme.text2 },
  clarify: { color: theme.brandDim, marginTop: 10, lineHeight: 20 },
  warn: { color: theme.watch, marginTop: 8, lineHeight: 20, fontSize: 13 },
  lbl: { marginTop: 12, fontWeight: '600', color: theme.text },
  input: {
    borderWidth: 1,
    borderColor: theme.borderStrong,
    borderRadius: theme.radiusSm,
    padding: 12,
    marginTop: 6,
    backgroundColor: theme.surface,
    fontSize: 16,
  },
  muted: { color: theme.muted, marginTop: 16 },
  footer: {
    backgroundColor: theme.surface,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    paddingHorizontal: theme.screenPad,
    paddingTop: 10,
    ...theme.shadow,
  },
  actions: { flexDirection: 'row', gap: 10, paddingBottom: 8 },
  btn: {
    flex: 1,
    minHeight: theme.minTouch,
    justifyContent: 'center',
    padding: 14,
    borderRadius: theme.radiusSm,
    alignItems: 'center',
  },
  primary: { backgroundColor: theme.brand },
  btnText: { color: '#fff', fontWeight: '700' },
  ghost: { backgroundColor: theme.brandSoft },
  ghostText: { color: theme.brandDim, fontWeight: '600' },
  dangerGhost: { backgroundColor: theme.urgentSoft },
  dangerText: { color: theme.urgent },
  disabled: { opacity: 0.45 },
});
