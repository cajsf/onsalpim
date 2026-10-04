export type Severity = keyof typeof import('./format').SEV;

export type CareHome = {
  home: string;
  severity: Severity;
  reason?: string;
  welfare_check?: boolean;
  life_known?: boolean;
  last_contact_at?: string;
  last_activity_at?: string;
  judged_at?: string;
  silent_s?: number;
  idle_s?: number;
  idle_min?: number | null;
  idle_levels?: { minutes: number; severity: Severity }[];
  away?: { until: string; reason: string };
  battery?: number | null;
  applied?: { source?: string; common?: number; rule_id?: number; minutes?: number };
};

export type CareResponse = {
  updated: string | null;
  homes: CareHome[];
  stale: boolean;
  message?: string;
};

export type EngineStatus = {
  running: boolean;
  last_run: string | null;
  message: string;
  platform_error?: string | null;
};

export type AlertRecord = {
  id: string;
  home: string;
  ts: string;
  from: Severity | null;
  to: Severity;
  reason: string;
  welfare?: boolean;
  state: string | null;
  log: { at: string; status: string; by: string; memo?: string }[];
  first_response_s?: number | null;
};

export type ActionStatus = 'ack' | 'progress' | 'done' | 'late' | 'edit';

export type RuleRecord = {
  id: number;
  sentence: string;
  status?: string;
  enabled?: boolean;
  rule?: Record<string, unknown>;
  questions?: string[];
  conflicts?: {
    id: number;
    summary?: string;
    homes: string[];
    covers_all?: boolean;
  }[];
};

export type AbsenceRecord = {
  id: number;
  home: string;
  start: string;
  end: string;
  reason: string;
  ended_at?: string | null;
  ended_by?: string | null;
};

export type PreviewResult = {
  ok: boolean;
  supported?: boolean;
  reason?: string;
  errors?: string[];
  days?: number;
  total?: number;
  baseline_total?: number;
  delta_total?: number;
  sparse_data?: boolean;
  homes?: { home: string; alerts: number; baseline: number }[];
};

export type MonthlyReportRow = {
  home: string;
  kind: string;
  start: string;
  end?: string | null;
  duration_s: number;
  draft: string;
  cut?: boolean;
  notes: { at: string; status: string; memo: string }[];
};

export type DeviceTree = {
  path: string;
  meta?: { kind?: string; type?: string; desc?: string };
  labels?: string[];
};
