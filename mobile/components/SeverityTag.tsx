import { StyleSheet, Text, View } from 'react-native';

import { LIFE_COLORS, SEV_COLORS } from '@/constants/severityColors';
import { theme } from '@/constants/theme';
import { SEV } from '@/lib/format';
import type { Severity } from '@/lib/types';

export function SeverityTag({
  severity,
  label,
  tone,
}: {
  severity: Severity;
  label?: string;
  tone?: 'life';
}) {
  const c = tone === 'life' ? LIFE_COLORS : (SEV_COLORS[severity] ?? SEV_COLORS.NORMAL);
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
    borderRadius: theme.radiusSm,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  text: { fontSize: 12, fontWeight: '600' },
});
