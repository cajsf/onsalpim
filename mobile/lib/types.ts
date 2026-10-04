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
  applied?: { source?: string; common?: number };
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
