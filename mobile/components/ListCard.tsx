import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { theme } from '@/constants/theme';

type Props = {
  barColor: string;
  highlight?: boolean;
  children: React.ReactNode;
};

/** Link asChild 와 함께 쓸 때 ref 가 Pressable 로 전달되도록 forwardRef */
export const ListCard = React.forwardRef<React.ComponentRef<typeof Pressable>, Props>(function ListCard(
  { barColor, highlight, children },
  ref,
) {
  return (
    <Pressable
      ref={ref}
      style={({ pressed }) =>
        StyleSheet.flatten([styles.card, highlight && styles.highlight, pressed && styles.pressed])
      }>
      <View style={[styles.bar, { backgroundColor: barColor }]} />
      <View style={styles.body}>{children}</View>
      <Text style={styles.chevron} accessibilityLabel="상세">
        ›
      </Text>
    </Pressable>
  );
});

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.surface,
    borderRadius: theme.radiusSm,
    borderWidth: 1,
    borderColor: theme.border,
    marginHorizontal: theme.screenPad,
    marginBottom: theme.listGap,
    minHeight: theme.minTouch,
    ...theme.shadowSm,
  },
  highlight: { borderColor: theme.urgent, backgroundColor: theme.urgentSoft },
  pressed: { opacity: 0.92 },
  bar: {
    width: 4,
    alignSelf: 'stretch',
    borderTopLeftRadius: theme.radiusSm,
    borderBottomLeftRadius: theme.radiusSm,
  },
  body: { flex: 1, paddingVertical: 12, paddingHorizontal: 12 },
  chevron: { fontSize: 22, color: theme.muted, paddingRight: 12, fontWeight: '300' },
});
