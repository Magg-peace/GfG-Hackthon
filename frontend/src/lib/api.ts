const API_BASE = "/api";

export interface ChartConfig {
  title: string;
  chart_type: "bar" | "line" | "pie" | "area" | "scatter" | "table" | "metric";
  sql: string;
  sql_executed?: string;
  data: Record<string, unknown>[];
  x_axis?: string;
  y_axis?: string[];
  x_label?: string;
  y_label?: string;
  color_by?: string | null;
  highlight?: string | null;
  insight?: string;
  row_count?: number;
  error?: string;
  // metric-specific
  value_column?: string;
  label?: string;
  prefix?: string;
  suffix?: string;
}

export interface DashboardResponse {
  success: boolean;
  session_id: string;
  summary: string;
  thinking?: string;
  assumptions?: string[];
  charts: ChartConfig[];
  error?: string;
}

export interface UploadResponse {
  success: boolean;
  session_id: string;
  filename: string;
  table_name: string;
  columns: string[];
  row_count: number;
  schema: string;
}

export interface SuggestionsResponse {
  suggestions: string[];
}

export async function queryDashboard(
  query: string,
  sessionId?: string | null
): Promise<DashboardResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API request failed");
  }
  return res.json();
}

export async function followUpQuery(
  query: string,
  sessionId: string,
  previousQuery: string,
  previousSql: string
): Promise<DashboardResponse> {
  const res = await fetch(`${API_BASE}/followup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      previous_query: previousQuery,
      previous_sql: previousSql,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API request failed");
  }
  return res.json();
}

export async function uploadCsv(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function getSuggestions(
  sessionId?: string | null
): Promise<SuggestionsResponse> {
  const url = sessionId
    ? `${API_BASE}/suggestions?session_id=${sessionId}`
    : `${API_BASE}/suggestions`;
  const res = await fetch(url);
  if (!res.ok) return { suggestions: [] };
  return res.json();
}

// ── ML Model APIs ──────────────────────────────────

export interface PredictionResult {
  success: boolean;
  predicted_settlement_ratio: number;
  predicted_percentage: number;
  risk_level: string;
  insurer: string;
  year: number;
  risk_classification: {
    risk_tier: string;
    confidence: Record<string, number>;
    insurer: string;
    year: number;
  };
}

export interface AnomalyResult {
  insurer: string;
  year: string;
  settlement_ratio: number;
  anomaly_score: number;
  total_claims: number;
  reason: string;
}

export interface MLOverviewItem {
  insurer: string;
  year: string;
  actual_ratio: number;
  predicted_ratio: number;
  residual: number;
  total_claims: number;
  total_amount: number;
}

export async function mlPredict(data: {
  insurer: string;
  year: number;
  total_claims_no: number;
  total_claims_amt: number;
  claims_repudiated_no: number;
  claims_rejected_no: number;
  claims_pending_start_no: number;
  claims_pending_end_no: number;
  claims_intimated_no: number;
  claims_unclaimed_no: number;
  claims_paid_amt: number;
}): Promise<PredictionResult> {
  const res = await fetch(`${API_BASE}/ml/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Prediction failed");
  }
  return res.json();
}

export async function mlAnomalies(): Promise<{ success: boolean; anomalies: AnomalyResult[] }> {
  const res = await fetch(`${API_BASE}/ml/anomalies`);
  if (!res.ok) throw new Error("Failed to fetch anomalies");
  return res.json();
}

export async function mlInsurers(): Promise<{ success: boolean; insurers: string[] }> {
  const res = await fetch(`${API_BASE}/ml/insurers`);
  if (!res.ok) throw new Error("Failed to fetch insurers");
  return res.json();
}

export async function mlOverview(): Promise<{ success: boolean; predictions: MLOverviewItem[] }> {
  const res = await fetch(`${API_BASE}/ml/overview`);
  if (!res.ok) throw new Error("Failed to fetch overview");
  return res.json();
}
