/** IOT/dashboard/src/style.css :root 와 동일 토큰 (돌봄 밝은 테마) */

export const theme = {
  bg: '#f4f7fb',
  surface: '#ffffff',
  surface2: '#f8fafc',
  border: '#e5e9f0',
  borderStrong: '#d7dee8',

  text: '#1f2937',
  text2: '#4b5563',
  muted: '#8a94a6',

  brand: '#2f6bed',
  brandDim: '#1d4ed8',
  brandSoft: '#eaf1fe',

  normal: '#16a34a',
  normalSoft: '#eafaf0',
  watch: '#c2870a',
  watchSoft: '#fdf5e3',
  urgent: '#dc2626',
  urgentSoft: '#fdeeee',
  device: '#5b5bd6',
  deviceSoft: '#eeeefc',

  radius: 14,
  radiusSm: 9,
  shadow: {
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 16,
    elevation: 2,
  },
  shadowSm: {
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 2,
    elevation: 1,
  },

  minTouch: 44,
  listGap: 10,
  screenPad: 16,
} as const;
