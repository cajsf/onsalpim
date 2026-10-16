package onsalpim.rules;

/**
 * 시간 패턴 판정용 이벤트 하나. patterns.drl 이 @role(event) @timestamp(ts) 로 선언한다.
 *
 *   motion  움직임 감지            (home, ts)
 *   temp    온도 측정              (home, ts, value=℃)
 *   humid   습도 측정              (home, ts, value=%)
 *   slot    관측된 10분 칸         (home, ts=칸 시작, value 1=활동 0=무활동) — 관측 안 된 칸은 넣지 않는다
 *   window  오전 평가 시각         (home, ts=평가 시각, value=개인 θ)
 *   day     하루 활동 비율         (home, ts=그날 0시, value=비율) — 관측 90% 이상인 지난 날만
 *   routine 승인된 생활 일정       (home, ts=시작, value=끝(epoch ms), ref=이름)
 *   alert   대응이 필요한 알림      (home, ts, ref=알림 id)
 *   action  그 알림에 대한 대응     (home, ts, ref=알림 id)
 *   tick    판정 시각 — 요청마다 하나. "지금으로부터 30분 안" 같은 조건이 이걸 기준으로 잰다
 */
public class Ev {
    private final String home;
    private final String type;
    private final long ts;          // epoch 밀리초
    private final Double value;
    private final String ref;

    public Ev(String home, String type, long ts, Double value, String ref) {
        this.home = home;
        this.type = type;
        this.ts = ts;
        this.value = value;
        this.ref = ref;
    }

    public String getHome() { return home; }
    public String getType() { return type; }
    public long getTs() { return ts; }
    public Double getValue() { return value; }
    public String getRef() { return ref; }
}
