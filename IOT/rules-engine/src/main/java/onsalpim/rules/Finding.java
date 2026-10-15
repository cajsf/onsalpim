package onsalpim.rules;

/** 시간 패턴이 찾은 것 — 세대·패턴마다 하나. 파이썬이 위험도·문장·통지로 바꾼다. */
public class Finding {
    private final String home;
    private final String code;
    private final Long since;     // 패턴이 시작된 시각 (epoch 밀리초) — 화면의 "몇 분째"
    private final String ref;     // 재통지면 알림 id

    public Finding(String home, String code, Long since, String ref) {
        this.home = home;
        this.code = code;
        this.since = since;
        this.ref = ref;
    }

    public String getHome() { return home; }
    public String getCode() { return code; }
    public Long getSince() { return since; }
    public String getRef() { return ref; }
}
