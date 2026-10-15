package onsalpim.rules;

/** 판정할 세대 한 건. 경과 시간(초)은 파이썬이 계산해 넣는다. null = 기록 없음. */
public class Case {
    private final int id;
    private final Double silentS;     // 마지막 생존 신호 이후 초
    private final double periodS;     // 보고 주기(초) — 장치 라벨에서
    private final Double idleS;       // 마지막 움직임 이후 초
    private final Double battery;     // %
    private final boolean away;       // 부재 등록 중
    private final boolean priorUrgent; // 통신 정상일 때 긴급 확인으로 확정된 적 있음

    public Case(int id, Double silentS, double periodS, Double idleS, Double battery, boolean away,
                boolean priorUrgent) {
        this.id = id;
        this.silentS = silentS;
        this.periodS = periodS;
        this.idleS = idleS;
        this.battery = battery;
        this.away = away;
        this.priorUrgent = priorUrgent;
    }

    public int getId() { return id; }
    public Double getSilentS() { return silentS; }
    public double getPeriodS() { return periodS; }
    public Double getIdleS() { return idleS; }
    public Double getBattery() { return battery; }
    public boolean isAway() { return away; }
    public boolean isPriorUrgent() { return priorUrgent; }
}
