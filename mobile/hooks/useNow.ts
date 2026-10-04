import { useEffect, useState } from 'react';

/** "N분 전" 은 서버 숫자가 아니라 시각 기준으로 매초 다시 계산한다 (format.js 와 같음). */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
