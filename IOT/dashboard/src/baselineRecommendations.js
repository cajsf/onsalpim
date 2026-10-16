// AIHub 5가구 앞 14일 통계로 만든 오전 활동 비율 추천.
// 출처: five_household_analysis_report.md, five_household_comparison.csv (2026-10-14).
// 임계값은 해당 시간창 활동 비율 중앙값의 0.5배. 0.5와 연속 0 30분은 실험값이다.
// 이 모듈은 화면 검토용이다. care_profiles.json 과 판정 엔진은 읽지 않는다.

export const HOURS = ['08:00', '09:00', '10:00', '11:00']

export const COMMON_THETA = [0.29166666666666663, 0.29166666666666663, 0.25, 0.25]

export const HOUSEHOLDS = [
  {
    id: 'E002',
    type: '아침 활동형',
    representative: true,
    hold: false,
    baseline: '2023-05-01 ~ 2023-05-14',
    validation: '2023-05-15 ~ 2023-05-28',
    coverage: 99.9752,
    morningMedian: 0.875,
    dayMedian: 0.6132,
    theta: [0.3333333333333333, 0.4166666666666667, 0.4166666666666667, 0.5],
    commonDays: 0,
    personalDays: 1,
    zeroQ90: 30,
    au: [8, 23.5, 82, 216.5],
    note: '2023-05-15 09:00 직전 1시간 활동 비율 33.33%, 연속 0은 40분. 공통 29.17%에서는 비후보고, 개인 41.67%에서는 후보 1일이다.',
  },
  {
    id: 'E016',
    type: '오전 저활동형',
    representative: false,
    hold: true,
    baseline: '2024-06-20 ~ 2024-07-03',
    validation: '2024-07-04 ~ 2024-07-17',
    coverage: 100,
    morningMedian: 0.0208,
    dayMedian: 0.3056,
    theta: [0, 0, 0, 0],
    commonDays: 14,
    personalDays: 0,
    zeroQ90: 240,
    au: [0, 0, 0, 0],
    note: '개인 임계값 4개가 0이다. 활동 비율 < 0 은 성립하지 않아 공통 14일이 개인 0일이 되었다. 운영 추천은 보류한다.',
  },
  {
    id: 'E007',
    type: '전반적 저활동형',
    representative: false,
    hold: false,
    baseline: '2023-05-01 ~ 2023-05-14',
    validation: '2023-05-15 ~ 2023-05-28',
    coverage: 99.9752,
    morningMedian: 0.3333,
    dayMedian: 0.1493,
    theta: [0.16666666666666666, 0.16666666666666666, 0.125, 0.125],
    commonDays: 12,
    personalDays: 10,
    zeroQ90: 127,
    au: [0, 0, 12, 27.5],
    note: '검증 14일에서 공통 12일·23창, 개인 10일·14창. 후보가 준 것은 정확도 향상이 아니다.',
  },
  {
    id: 'E012',
    type: '활동 변동형',
    representative: false,
    hold: false,
    baseline: '2023-05-01 ~ 2023-05-14',
    validation: '2023-05-15 ~ 2023-05-28',
    coverage: 99.8264,
    morningMedian: 0.7292,
    dayMedian: 0.5104,
    theta: [0.4166666666666667, 0.4166666666666667, 0.375, 0.25],
    commonDays: 8,
    personalDays: 8,
    zeroQ90: 101,
    au: [0, 40.5, 115.5, 179],
    note: '후보 일수는 둘 다 8일이다. 2023-05-17 11:00 창은 관측이 부족해 검증 불가다.',
  },
  {
    id: 'E004',
    type: '온습도 변화형',
    representative: false,
    hold: false,
    baseline: '2023-05-01 ~ 2023-05-14',
    validation: '2023-05-15 ~ 2023-05-28',
    coverage: 99.9752,
    morningMedian: 0.4792,
    dayMedian: 0.3021,
    theta: [0.3333333333333333, 0.25, 0.25, 0.20833333333333331],
    commonDays: 11,
    personalDays: 11,
    zeroQ90: 80,
    au: [0, 0, 24, 55.5],
    note: '유형은 일평균 습도 범위 15.1%p로 골랐다. 오전 창에서 30°C가 60분 이어진 복합 후보는 0창이다.',
  },
]

const KEY = 'onsalpim.baselineReview.v1'

export function freshDecisions() {
  const out = {}
  for (const h of HOUSEHOLDS) {
    out[h.id] = { status: h.hold ? 'held' : 'pending', theta: h.theta.slice() }
  }
  return out
}

export function loadDecisions() {
  const base = freshDecisions()
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (!raw || typeof raw !== 'object') return base
    for (const h of HOUSEHOLDS) {
      const saved = raw[h.id]
      if (!saved) continue
      if (h.hold) continue
      const theta = Array.isArray(saved.theta) && saved.theta.length === 4
        ? saved.theta.map(Number)
        : h.theta.slice()
      if (theta.some((n) => !Number.isFinite(n) || n < 0 || n > 1)) continue
      const status = ['pending', 'modified', 'approved', 'rejected'].includes(saved.status)
        ? saved.status
        : 'pending'
      base[h.id] = { status, theta }
    }
  } catch {
    /* 저장값이 깨져 있으면 원본 추천으로 돌아간다 */
  }
  return base
}

export function saveDecisions(decisions) {
  const slim = {}
  for (const h of HOUSEHOLDS) {
    if (h.hold) continue
    slim[h.id] = decisions[h.id]
  }
  localStorage.setItem(KEY, JSON.stringify(slim))
}

export function pendingCount(decisions) {
  return HOUSEHOLDS.filter((h) => {
    const status = decisions[h.id]?.status
    return status === 'pending' || status === 'modified'
  }).length
}

export function pct(v) {
  return `${(Number(v) * 100).toFixed(2)}%`
}
