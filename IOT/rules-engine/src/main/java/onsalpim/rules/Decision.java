package onsalpim.rules;

/** 규칙이 내린 결정 — 세대마다 하나. code 는 파이썬이 화면 문장으로 바꾼다. */
public class Decision {
    private final int caseId;
    private final String code;
    private final Double minutes;     // 넘은 무활동 단계(분). 해당 없으면 null

    public Decision(int caseId, String code, Double minutes) {
        this.caseId = caseId;
        this.code = code;
        this.minutes = minutes;
    }

    public int getCaseId() { return caseId; }
    public String getCode() { return code; }
    public Double getMinutes() { return minutes; }
}
