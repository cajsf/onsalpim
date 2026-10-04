import { useEffect, useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { useSettings } from '@/context/SettingsContext';
import { defaultApiBase } from '@/lib/api';

export default function SettingsScreen() {
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
      setMsg('저장했습니다. 다른 탭으로 이동하면 새 주소로 갱신됩니다.');
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  function resetDefault() {
    setDraft(defaultApiBase());
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>API 서버</Text>
      <Text style={styles.hint}>
        끝에 <Text style={styles.mono}>/api</Text> 가 없으면 자동으로 붙입니다.
      </Text>
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
        <Pressable style={[styles.btn, styles.ghost]} onPress={resetDefault}>
          <Text style={styles.ghostText}>기본값</Text>
        </Pressable>
        <Pressable style={styles.btn} onPress={save}>
          <Text style={styles.btnText}>저장</Text>
        </Pressable>
      </View>
      {err ? <Text style={styles.err}>{err}</Text> : null}
      {msg ? <Text style={styles.ok}>{msg}</Text> : null}
      <Text style={styles.footer}>
        빌드 시 <Text style={styles.mono}>EXPO_PUBLIC_API_BASE</Text> 로 기본 URL 을 고정할 수
        있습니다 (.env).
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#fff' },
  title: { fontSize: 20, fontWeight: '700', marginBottom: 8 },
  hint: { color: '#616161', marginBottom: 12, lineHeight: 20 },
  mono: { fontFamily: 'SpaceMono' },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    marginBottom: 12,
  },
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
  err: { color: '#c62828', marginTop: 12 },
  ok: { color: '#2e7d32', marginTop: 12 },
  footer: { marginTop: 24, color: '#757575', lineHeight: 20, fontSize: 13 },
});
