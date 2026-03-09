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
