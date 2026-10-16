import { View } from 'react-native';

import { SeverityTag } from '@/components/SeverityTag';
import { FOLLOW_KO, sevKo } from '@/lib/format';
import type { CareHome } from '@/lib/types';

/** 대시보드 세대 행과 같은 태그. 생활 확인과 배터리 주의를 나누고, 긴급 중 두절은 장치 점검을 곁에 붙인다. */
export function HomeTags({ home }: { home: CareHome }) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
      <SeverityTag
        severity={home.life_check ? 'WATCH' : home.severity}
        label={sevKo(home)}
        tone={home.life_check ? 'life' : undefined}
      />
      {home.followup ? (
        <SeverityTag severity="WATCH" label={FOLLOW_KO[home.followup.code] || home.followup.code} />
      ) : null}
      {home.device_check && home.severity !== 'CHECK_DEVICE' ? (
        <SeverityTag severity="CHECK_DEVICE" />
      ) : null}
      {home.welfare_check ? <SeverityTag severity="URGENT" label="안부 확인" /> : null}
    </View>
  );
}
