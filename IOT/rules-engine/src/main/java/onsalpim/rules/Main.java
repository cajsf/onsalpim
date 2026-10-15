package onsalpim.rules;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.kie.api.KieBase;
import org.kie.api.KieServices;
import org.kie.api.conf.EventProcessingOption;
import org.kie.api.io.ResourceType;
import org.kie.api.runtime.KieSession;
import org.kie.api.runtime.KieSessionConfiguration;
import org.kie.api.runtime.conf.ClockTypeOption;
import org.kie.api.time.SessionPseudoClock;
import org.kie.internal.utils.KieHelper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * 표준 입출력으로 판정 요청을 받는다. 한 줄 = 한 요청(JSON), 한 줄 = 한 응답(JSON).
 *
 *   요청 {"params": {"stale_factor", "battery_low"},
 *        "cases": [{"silent_s", "period_s", "idle_s", "levels": [{"minutes", "severity"}], "battery", "away"}]}
 *   응답 {"decisions": [{"code", "minutes"}]}   (cases 와 같은 순서)   또는 {"error": "..."}
 *
 *   시간 패턴 요청 {"patterns": {"now": epoch ms, "homes": [{"id", "hot_c", "morning_from", "morning_by",
 *                                "night_from", "night_to", "wander_count"}],
 *                     "events": [{"home", "type", "ts", "value", "ref"}]}}
 *   응답 {"findings": [{"home", "code", "since", "ref"}]}
 *
 * 세션은 요청마다 새로 만든다 — 엔진 안에 상태를 남기지 않아 재시작해도 결과가 같다.
 */
public final class Main {
    private static final ObjectMapper JSON = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        KieBase kb = new KieHelper()
                .addResource(org.kie.internal.io.ResourceFactory.newClassPathResource("onsalpim/rules/judge.drl"),
                        ResourceType.DRL)
                .build();
        KieBase patterns = new KieHelper()
                .addResource(org.kie.internal.io.ResourceFactory.newClassPathResource("onsalpim/rules/patterns.drl"),
                        ResourceType.DRL)
                .build(EventProcessingOption.STREAM);
        out.println("READY");
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = in.readLine()) != null) {
            if (line.isBlank()) continue;
            try {
                JsonNode req = JSON.readTree(line);
                out.println(JSON.writeValueAsString(
                        req.has("patterns") ? handlePatterns(patterns, req.get("patterns")) : handle(kb, req)));
            } catch (Exception e) {
                ObjectNode err = JSON.createObjectNode();
                err.put("error", e.getClass().getSimpleName() + ": " + e.getMessage());
                out.println(JSON.writeValueAsString(err));
            }
        }
    }

    static ObjectNode handle(KieBase kb, JsonNode req) {
        JsonNode p = req.get("params");
        JsonNode cases = req.get("cases");
        KieSession s = kb.newKieSession();
        try {
            s.insert(new Params(p.get("stale_factor").asDouble(), p.get("battery_low").asDouble()));
            for (int i = 0; i < cases.size(); i++) {
                JsonNode c = cases.get(i);
                s.insert(new Case(i, num(c, "silent_s"), c.get("period_s").asDouble(), num(c, "idle_s"),
                        num(c, "battery"), c.get("away").asBoolean()));
                for (JsonNode lv : c.get("levels")) {
                    s.insert(new Level(i, lv.get("minutes").asDouble(), lv.get("severity").asText()));
                }
            }
            s.fireAllRules();
            Decision[] got = new Decision[cases.size()];
            for (Object o : s.getObjects(o -> o instanceof Decision)) {
                Decision d = (Decision) o;
                if (got[d.getCaseId()] != null) {
                    throw new IllegalStateException("세대 " + d.getCaseId() + "에 결정이 둘 — 규칙 순서 오류");
                }
                got[d.getCaseId()] = d;
            }
            ObjectNode res = JSON.createObjectNode();
            ArrayNode arr = res.putArray("decisions");
            for (Decision d : got) {
                ObjectNode o = arr.addObject();
                o.put("code", d.getCode());
                if (d.getMinutes() == null) o.putNull("minutes"); else o.put("minutes", d.getMinutes());
            }
            return res;
        } finally {
            s.dispose();
        }
    }

    /** 시간 패턴 — 가상 시계를 '지금'에 맞추고 이벤트를 시간 순으로 넣은 뒤 지금(tick)을 넣고 판정한다. */
    static ObjectNode handlePatterns(KieBase kb, JsonNode req) {
        KieSessionConfiguration conf = KieServices.Factory.get().newKieSessionConfiguration();
        conf.setOption(ClockTypeOption.PSEUDO);
        KieSession s = kb.newKieSession(conf, null);
        try {
            long now = req.get("now").asLong();
            SessionPseudoClock clock = s.getSessionClock();
            clock.advanceTime(now - clock.getCurrentTime(), TimeUnit.MILLISECONDS);
            for (JsonNode h : req.get("homes")) {
                Double hot = num(h, "hot_c");
                Double wander = num(h, "wander_count");
                s.insert(new Home(h.get("id").asText(), hot, lng(h, "morning_from"), lng(h, "morning_by"),
                        lng(h, "night_from"), lng(h, "night_to"), wander == null ? null : wander.intValue()));
            }
            java.util.List<JsonNode> evs = new java.util.ArrayList<>();
            req.get("events").forEach(evs::add);
            evs.sort(java.util.Comparator.comparingLong(e -> e.get("ts").asLong()));
            for (JsonNode e : evs) {
                if (e.get("ts").asLong() > now) continue;        // 미래 기록은 시계를 거꾸로 돌린다 — 버린다
                s.insert(new Ev(text(e, "home"), e.get("type").asText(), e.get("ts").asLong(), num(e, "value"), text(e, "ref")));
            }
            s.insert(new Ev(null, "tick", now, null, null));
            s.fireAllRules();
            ObjectNode res = JSON.createObjectNode();
            ArrayNode arr = res.putArray("findings");
            for (Object o : s.getObjects(o -> o instanceof Finding)) {
                Finding f = (Finding) o;
                ObjectNode n = arr.addObject();
                n.put("home", f.getHome());
                n.put("code", f.getCode());
                if (f.getSince() == null) n.putNull("since"); else n.put("since", f.getSince());
                if (f.getRef() == null) n.putNull("ref"); else n.put("ref", f.getRef());
            }
            return res;
        } finally {
            s.dispose();
        }
    }

    private static Long lng(JsonNode c, String key) {
        JsonNode v = c.get(key);
        return v == null || v.isNull() ? null : v.asLong();
    }

    private static String text(JsonNode c, String key) {
        JsonNode v = c.get(key);
        return v == null || v.isNull() ? null : v.asText();
    }

    private static Double num(JsonNode c, String key) {
        JsonNode v = c.get(key);
        return v == null || v.isNull() ? null : v.asDouble();
    }
}
