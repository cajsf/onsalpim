package onsalpim.rules;

/**
 * 세대별 패턴 기준값 — 정책 데이터(승인된 개인 기준)에서 온다. null 이면 그 패턴을 보지 않는다.
 * 시각은 파이썬이 '오늘' 날짜로 계산해 epoch 밀리초로 넘긴다 (Java 가 시간대를 따로 계산하면 어긋난다).
 */
public class Home {
    private final String id;
    private final Double hotC;          // 고온 기준 ℃
    private final Long morningFrom;     // 오전 첫 활동을 기다리기 시작하는 시각
    private final Long morningBy;       // 이때까지 첫 움직임이 없으면 생활 확인
    private final Long nightFrom;       // 새벽 배회를 보는 시간대
    private final Long nightTo;
    private final Integer wanderCount;  // 1시간 안 움직임 감지가 이 횟수 이상이면 배회 의심
    private final Double coldC;         // 저온 기준 ℃
    private final Double humidLo;       // 습도 정상 범위 (%)
    private final Double humidHi;
    private final Long dayFrom;         // 주간 활동 급감을 보는 시간대 (null 이면 안 봄)
    private final Long dayTo;

    public Home(String id, Double hotC, Long morningFrom, Long morningBy,
                Long nightFrom, Long nightTo, Integer wanderCount,
                Double coldC, Double humidLo, Double humidHi, Long dayFrom, Long dayTo) {
        this.id = id;
        this.hotC = hotC;
        this.morningFrom = morningFrom;
        this.morningBy = morningBy;
        this.nightFrom = nightFrom;
        this.nightTo = nightTo;
        this.wanderCount = wanderCount;
        this.coldC = coldC;
        this.humidLo = humidLo;
        this.humidHi = humidHi;
        this.dayFrom = dayFrom;
        this.dayTo = dayTo;
    }

    public String getId() { return id; }
    public Double getHotC() { return hotC; }
    public Long getMorningFrom() { return morningFrom; }
    public Long getMorningBy() { return morningBy; }
    public Long getNightFrom() { return nightFrom; }
    public Long getNightTo() { return nightTo; }
    public Integer getWanderCount() { return wanderCount; }
    public Double getColdC() { return coldC; }
    public Double getHumidLo() { return humidLo; }
    public Double getHumidHi() { return humidHi; }
    public Long getDayFrom() { return dayFrom; }
    public Long getDayTo() { return dayTo; }
}
