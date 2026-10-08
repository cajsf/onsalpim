package onsalpim.rules;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.kie.api.KieBase;
import org.kie.api.io.ResourceType;
import org.kie.api.runtime.KieSession;
import org.kie.internal.utils.KieHelper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;

/**
 * 표준 입출력으로 판정 요청을 받는다. 한 줄 = 한 요청(JSON), 한 줄 = 한 응답(JSON).
 *
 *   요청 {"params": {"stale_factor", "battery_low"},
 *        "cases": [{"silent_s", "period_s", "idle_s", "levels": [{"minutes", "severity"}], "battery", "away"}]}
 *   응답 {"decisions": [{"code", "minutes"}]}   (cases 와 같은 순서)   또는 {"error": "..."}
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
        out.println("READY");
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = in.readLine()) != null) {
            if (line.isBlank()) continue;
            try {
                out.println(JSON.writeValueAsString(handle(kb, JSON.readTree(line))));
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

    private static Double num(JsonNode c, String key) {
        JsonNode v = c.get(key);
        return v == null || v.isNull() ? null : v.asDouble();
    }
}
