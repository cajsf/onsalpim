import { useCallback, useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { theme } from '@/constants/theme';
import { useSettings } from '@/context/SettingsContext';
import type { HomeContacts as Book } from '@/lib/types';

const ROWS = [
  { role: 'guardian' as const, label: '보호자' },
  { role: 'staff' as const, label: '담당자' },
];

type Form = {
  guardianName: string;
  guardianPhone: string;
  staffName: string;
  staffPhone: string;
};

function emptyForm(): Form {
  return { guardianName: '', guardianPhone: '', staffName: '', staffPhone: '' };
}

function digitsOf(phone: string): string {
  return phone.replace(/\D/g, '');
}

export function HomeContacts({ home }: { home: string }) {
  const { api } = useSettings();
  const [book, setBook] = useState<Book>({ home, guardian: null, staff: null });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Form>(emptyForm());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setBook(await api.getContacts(home));
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [api, home]);

  useEffect(() => {
    setEditing(false);
    setForm(emptyForm());
    load();
  }, [load]);

  function startEdit() {
    setForm({
      guardianName: book.guardian?.name || '',
      guardianPhone: book.guardian?.phone || '',
      staffName: book.staff?.name || '',
      staffPhone: book.staff?.phone || '',
    });
    setEditing(true);
    setError('');
  }

  async function save() {
    if (busy) return;
    setBusy(true);
    setError('');
    const r = await api.saveContacts(home, {
      guardian: { name: form.guardianName, phone: form.guardianPhone },
      staff: { name: form.staffName, phone: form.staffPhone },
    });
    setBusy(false);
    if (!r.ok || !r.contacts) {
      setError((r.errors || []).join(' ') || '저장하지 못했습니다.');
      return;
    }
    setBook(r.contacts);
    setEditing(false);
  }

  async function call(phone: string) {
    const digits = digitsOf(phone);
    if (!digits) return;
    await Linking.openURL(`tel:${digits}`);
  }

  const anyPhone = ROWS.some((row) => book[row.role]?.phone);

  return (
    <View style={styles.card}>
      <View style={styles.head}>
        <Text style={styles.title}>연락</Text>
        {!editing ? (
          <Pressable onPress={startEdit} hitSlop={8}>
            <Text style={styles.link}>{anyPhone ? '수정' : '연락처 등록'}</Text>
          </Pressable>
        ) : null}
      </View>
      {error ? <Text style={styles.err}>{error}</Text> : null}
      {!editing && !anyPhone ? (
        <Text style={styles.muted}>등록된 보호자·담당자 번호가 없습니다.</Text>
      ) : null}
      {!editing
        ? ROWS.map((row) => {
            const item = book[row.role];
            if (!item?.phone) return null;
            const who = item.name ? `${row.label} ${item.name}` : row.label;
            return (
              <Pressable key={row.role} style={styles.call} onPress={() => call(item.phone)}>
                <Text style={styles.callText}>
                  {who} · {item.phone}
                </Text>
              </Pressable>
            );
          })
        : null}
      {editing ? (
        <View style={styles.form}>
          {ROWS.map((row) => (
            <View key={row.role} style={styles.pair}>
              <Text style={styles.role}>{row.label}</Text>
              <TextInput
                style={styles.input}
                value={form[`${row.role}Name`]}
                onChangeText={(v) => setForm((f) => ({ ...f, [`${row.role}Name`]: v }))}
                placeholder={`${row.label} 이름`}
                placeholderTextColor={theme.muted}
                maxLength={30}
              />
              <TextInput
                style={styles.input}
                value={form[`${row.role}Phone`]}
                onChangeText={(v) => setForm((f) => ({ ...f, [`${row.role}Phone`]: v }))}
                placeholder={`${row.label} 전화`}
                placeholderTextColor={theme.muted}
                keyboardType="phone-pad"
                maxLength={20}
              />
            </View>
          ))}
          <Text style={styles.muted}>번호를 비우고 저장하면 그 연락처는 지워집니다.</Text>
          <View style={styles.acts}>
            <Pressable onPress={() => setEditing(false)} disabled={busy}>
              <Text style={styles.link}>취소</Text>
            </Pressable>
            <Pressable style={styles.save} onPress={save} disabled={busy}>
              <Text style={styles.saveText}>{busy ? '저장 중…' : '저장'}</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: 14,
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 14,
    gap: 10,
    borderWidth: 1,
    borderColor: theme.border,
  },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontSize: 15, fontWeight: '700', color: theme.text },
  link: { color: theme.brand, fontWeight: '600', fontSize: 14 },
  muted: { color: theme.muted, fontSize: 13, lineHeight: 18 },
  err: { color: theme.urgent, fontSize: 13 },
  call: {
    backgroundColor: theme.brandSoft,
    borderRadius: theme.radiusSm,
    paddingVertical: 12,
    paddingHorizontal: 12,
  },
  callText: { color: theme.brandDim, fontWeight: '700', fontSize: 15 },
  form: { gap: 8 },
  pair: { gap: 6 },
  role: { fontSize: 12, fontWeight: '700', color: theme.muted },
  input: {
    borderWidth: 1,
    borderColor: theme.borderStrong,
    borderRadius: theme.radiusSm,
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: theme.text,
    fontSize: 15,
  },
  acts: { flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: 16, marginTop: 4 },
  save: { backgroundColor: theme.brand, borderRadius: theme.radiusSm, paddingVertical: 8, paddingHorizontal: 14 },
  saveText: { color: '#fff', fontWeight: '700' },
});
