package onsalpim.rules;

/** 세대에 걸린 무활동 단계 하나 — 승인된 규칙에서 나온 데이터 (예: 480분 긴급). */
public class Level {
    private final int caseId;
    private final double minutes;
    private final String severity;

    public Level(int caseId, double minutes, String severity) {
        this.caseId = caseId;
        this.minutes = minutes;
        this.severity = severity;
    }

    public int getCaseId() { return caseId; }
    public double getMinutes() { return minutes; }
    public String getSeverity() { return severity; }
}
