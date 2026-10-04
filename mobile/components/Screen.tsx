import { Platform, SafeAreaView, StyleSheet, View } from 'react-native';

import { theme } from '@/constants/theme';

type Props = { children: React.ReactNode; edges?: boolean };

/** 웹 시연: max 480px 가운데 — 대시보드 모바일 폭과 비슷하게 */
export function Screen({ children }: Props) {
  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.frame}>{children}</View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
  frame: {
    flex: 1,
    width: '100%',
    maxWidth: Platform.OS === 'web' ? 480 : undefined,
    alignSelf: 'center',
  },
});
