package onsalpim.rules;

/** 판정 상수 — 정본은 파이썬(care_monitor.STALE_FACTOR, BATTERY_LOW)이고 요청마다 같이 온다. */
public class Params {
    private final double staleFactor;
    private final double batteryLow;

    public Params(double staleFactor, double batteryLow) {
        this.staleFactor = staleFactor;
        this.batteryLow = batteryLow;
    }

    public double getStaleFactor() { return staleFactor; }
    public double getBatteryLow() { return batteryLow; }
}
