import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { useSettings } from '@/context/SettingsContext';
import { FALLBACK_API_BASE } from '@/lib/api';

export function SettingsPanel() {
  const { apiBase, setApiBase, ready } = useSettings();
  const [draft, setDraft] = useState(apiBase);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => {
    setDraft(apiBase);
  }, [apiBase]);

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

  return (
    <View style={styles.card}>
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
        editable={ready}
      />
      <View style={styles.row}>
        <Pressable style={[styles.btn, styles.ghost]} onPress={() => setDraft(FALLBACK_API_BASE)}>
          <Text style={styles.ghostText}>기본값</Text>
        </Pressable>
        <Pressable style={styles.btn} onPress={save}>
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
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 14, gap: 8 },
  title: { fontSize: 17, fontWeight: '700' },
  hint: { color: '#616161', fontSize: 13 },
  current: { fontSize: 12, color: '#424242' },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 10 },
  row: { flexDirection: 'row', gap: 10 },
  btn: {
    flex: 1,
    backgroundColor: '#1565c0',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  btnText: { color: '#fff', fontWeight: '600' },
  ghost: { backgroundColor: '#e3f2fd' },
  ghostText: { color: '#1565c0', fontWeight: '600' },
  fix: { backgroundColor: '#2e7d32' },
  err: { color: '#c62828' },
  ok: { color: '#2e7d32' },
});
