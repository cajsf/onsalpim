import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';

import { SettingsPanel } from '@/components/SettingsPanel';
import { theme } from '@/constants/theme';

export default function SettingsScreen() {
  return (
    <ScrollView style={styles.flex} contentContainerStyle={styles.pad}>
      <Pressable onPress={() => router.back()} style={styles.back}>
        <Text style={styles.backText}>← 더보기</Text>
      </Pressable>
      <SettingsPanel />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: theme.bg },
  pad: { padding: theme.screenPad, paddingBottom: 32, gap: 12 },
  back: { alignSelf: 'flex-start', minHeight: theme.minTouch, justifyContent: 'center' },
  backText: { color: theme.brandDim, fontWeight: '600' },
});
