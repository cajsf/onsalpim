import { StyleSheet, Text, View } from 'react-native';

import { SEV_COLORS } from '@/constants/severityColors';
import { SEV } from '@/lib/format';
import type { Severity } from '@/lib/types';

export function SeverityTag({ severity, label }: { severity: Severity; label?: string }) {
  const c = SEV_COLORS[severity] ?? SEV_COLORS.NORMAL;
  const ko = label ?? SEV[severity]?.ko ?? severity;
  return (
    <View style={[styles.tag, { backgroundColor: c.bg, borderColor: c.border }]}>
      <Text style={[styles.text, { color: c.text }]}>{ko}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  text: { fontSize: 12, fontWeight: '600' },
});
