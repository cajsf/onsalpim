import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import { FALLBACK_API_BASE } from '@/lib/api';

export function SettingsPanel() {
  const { apiBase, setApiBase, ready, worker, setWorker } = useSettings();
  const [draft, setDraft] = useState(apiBase);
  const [workerDraft, setWorkerDraft] = useState(worker);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => {
    setDraft(apiBase);
  }, [apiBase]);

  useEffect(() => {
    setWorkerDraft(worker);
  }, [worker]);

  async function save() {
    setErr('');
    setMsg('');
    try {
      await setApiBase(draft);
      setMsg('저장했습니다.');
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function clearSavedAndUseDefault() {
    setErr('');
    setMsg('');
    try {
      await setApiBase(FALLBACK_API_BASE);
      setDraft(FALLBACK_API_BASE);
      setMsg('API 주소를 기본값으로 맞췄습니다.');
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function saveWorker() {
    setErr('');
    setMsg('');
    try {
      await setWorker(workerDraft);
      setMsg('담당자 이름을 저장했습니다. 이 이름으로 알림을 맡습니다.');
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>담당자 이름</Text>
      <Text style={styles.hint}>알림을 맡는 이름입니다. 다른 이름은 같은 알림을 받을 수 없습니다.</Text>
      <TextInput
        style={styles.input}
        value={workerDraft}
        onChangeText={setWorkerDraft}
        maxLength={40}
        placeholder="복지사"
        placeholderTextColor={theme.muted}
        editable={ready}
      />
      <Pressable style={[styles.btn, styles.primary]} onPress={saveWorker}>
        <Text style={styles.btnText}>이름 저장</Text>
      </Pressable>
      <Text style={styles.title}>API 서버</Text>
      <Text style={styles.hint}>끝에 /api 가 없으면 자동으로 붙습니다.</Text>
      <Text style={styles.current}>현재: {apiBase}</Text>
      <TextInput
        style={styles.input}
        value={draft}
        onChangeText={setDraft}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="https://onsalpim-api.onrender.com/api"
        placeholderTextColor={theme.muted}
        editable={ready}
      />
      <View style={styles.row}>
        <Pressable style={[styles.btn, styles.ghost]} onPress={() => setDraft(FALLBACK_API_BASE)}>
          <Text style={styles.ghostText}>기본값</Text>
        </Pressable>
        <Pressable style={[styles.btn, styles.primary]} onPress={save}>
          <Text style={styles.btnText}>저장</Text>
        </Pressable>
      </View>
      <Pressable style={[styles.btn, styles.fix]} onPress={clearSavedAndUseDefault}>
        <Text style={styles.btnText}>API 주소 초기화</Text>
      </Pressable>
      {err ? <Text style={styles.err}>{err}</Text> : null}
      {msg ? <Text style={styles.ok}>{msg}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    gap: 8,
    borderWidth: 1,
    borderColor: theme.border,
    ...theme.shadowSm,
  },
  title: { fontSize: 17, fontWeight: '700', color: theme.text },
  hint: { color: theme.muted, fontSize: 13 },
  current: { fontSize: 12, color: theme.text2 },
  input: {
    borderWidth: 1,
    borderColor: theme.borderStrong,
    borderRadius: theme.radiusSm,
    padding: 12,
    fontSize: 15,
    backgroundColor: theme.surface,
  },
  row: { flexDirection: 'row', gap: 10 },
  btn: {
    flex: 1,
    minHeight: theme.minTouch,
    justifyContent: 'center',
    padding: 12,
    borderRadius: theme.radiusSm,
    alignItems: 'center',
  },
  primary: { backgroundColor: theme.brand },
  btnText: { color: '#fff', fontWeight: '600' },
  ghost: { backgroundColor: theme.brandSoft },
  ghostText: { color: theme.brandDim, fontWeight: '600' },
  fix: { backgroundColor: theme.normal, marginTop: 4 },
  err: { color: theme.urgent },
  ok: { color: theme.normal },
});
