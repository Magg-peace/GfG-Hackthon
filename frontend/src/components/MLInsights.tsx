"use client";

import React, { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  Cell,
} from "recharts";
import {
  Brain,
  AlertTriangle,
  TrendingUp,
  Shield,
  Loader2,
  ChevronDown,
  ChevronUp,
  Target,
} from "lucide-react";
import {
  mlPredict,
  mlAnomalies,
  mlInsurers,
  mlOverview,
  PredictionResult,
  AnomalyResult,
  MLOverviewItem,
} from "@/lib/api";

const RISK_COLORS: Record<string, string> = {
  "Low Risk": "#22c55e",
  "Medium Risk": "#f59e0b",
  "High Risk": "#ef4444",
};

function formatPct(val: number): string {
  return (val * 100).toFixed(1) + "%";
}

// ── Prediction Form ──────────────────────
function PredictionPanel() {
  const [insurers, setInsurers] = useState<string[]>([]);
  const [selectedInsurer, setSelectedInsurer] = useState("");
  const [year, setYear] = useState(2024);
  const [totalClaims, setTotalClaims] = useState(1000);
  const [totalAmt, setTotalAmt] = useState(500);
  const [repudiated, setRepudiated] = useState(20);
  const [rejected, setRejected] = useState(5);
  const [pendingStart, setPendingStart] = useState(10);
  const [pendingEnd, setPendingEnd] = useState(15);
  const [paidAmt, setPaidAmt] = useState(450);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);

  useEffect(() => {
    mlInsurers()
      .then((res) => {
        setInsurers(res.insurers);
        if (res.insurers.length > 0) setSelectedInsurer(res.insurers[0]);
      })
      .catch(() => {});
  }, []);

  const handlePredict = async () => {
    setLoading(true);
    try {
      const res = await mlPredict({
        insurer: selectedInsurer,
        year,
        total_claims_no: totalClaims,
        total_claims_amt: totalAmt,
        claims_repudiated_no: repudiated,
        claims_rejected_no: rejected,
        claims_pending_start_no: pendingStart,
        claims_pending_end_no: pendingEnd,
        claims_intimated_no: totalClaims,
        claims_unclaimed_no: 0,
        claims_paid_amt: paidAmt,
      });
      setResult(res);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="text-xs text-slate-400 mb-1 block">Insurer</label>
          <select
            value={selectedInsurer}
            onChange={(e) => setSelectedInsurer(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          >
            {insurers.map((ins) => (
              <option key={ins} value={ins}>
                {ins}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Year</label>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Total Claims</label>
          <input
            type="number"
            value={totalClaims}
            onChange={(e) => setTotalClaims(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Claims Amount (Cr)</label>
          <input
            type="number"
            value={totalAmt}
            onChange={(e) => setTotalAmt(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Paid Amount (Cr)</label>
          <input
            type="number"
            value={paidAmt}
            onChange={(e) => setPaidAmt(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Repudiated</label>
          <input
            type="number"
            value={repudiated}
            onChange={(e) => setRepudiated(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Rejected</label>
          <input
            type="number"
            value={rejected}
            onChange={(e) => setRejected(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Pending (Start)</label>
          <input
            type="number"
            value={pendingStart}
            onChange={(e) => setPendingStart(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="text-xs text-slate-400 mb-1 block">Pending (End)</label>
          <input
            type="number"
            value={pendingEnd}
            onChange={(e) => setPendingEnd(+e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
          />
        </div>
      </div>

      <button
        onClick={handlePredict}
        disabled={loading || !selectedInsurer}
        className="w-full py-2.5 bg-brand-600 hover:bg-brand-500 disabled:bg-slate-700 rounded-xl text-sm font-medium text-white transition-colors flex items-center justify-center gap-2"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Brain className="w-4 h-4" />
        )}
        Predict Settlement Ratio
      </button>

      {result && (
        <div className="animate-fade-in space-y-3">
          {/* Big Metric */}
          <div
            className="rounded-xl p-4 text-center border"
            style={{
              borderColor: RISK_COLORS[result.risk_level] + "40",
              backgroundColor: RISK_COLORS[result.risk_level] + "10",
            }}
          >
            <p className="text-xs text-slate-400 mb-1">
              Predicted Settlement Ratio
            </p>
            <p
              className="text-3xl font-bold"
              style={{ color: RISK_COLORS[result.risk_level] }}
            >
              {result.predicted_percentage}%
            </p>
            <span
              className="inline-block mt-2 text-xs font-medium px-3 py-1 rounded-full"
              style={{
                color: RISK_COLORS[result.risk_level],
                backgroundColor: RISK_COLORS[result.risk_level] + "20",
              }}
            >
              {result.risk_level}
            </span>
          </div>

          {/* Risk Tier Confidence */}
          <div className="bg-slate-800/60 rounded-xl p-4">
            <p className="text-xs text-slate-400 mb-3">
              Risk Classification Confidence
            </p>
            {Object.entries(result.risk_classification.confidence).map(
              ([tier, pct]) => (
                <div key={tier} className="flex items-center gap-2 mb-2">
                  <span className="text-xs text-slate-400 w-24">{tier}</span>
                  <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: RISK_COLORS[tier] || "#3b82f6",
                      }}
                    />
                  </div>
                  <span className="text-xs text-slate-300 w-12 text-right">
                    {pct}%
                  </span>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Anomaly Panel ──────────────────────
function AnomalyPanel() {
  const [anomalies, setAnomalies] = useState<AnomalyResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mlAnomalies()
      .then((res) => setAnomalies(res.anomalies))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500 mb-3">
        {anomalies.length} anomalous patterns detected by Isolation Forest
      </p>
      {anomalies.map((a, i) => (
        <div
          key={i}
          className="bg-slate-800/60 border border-amber-700/30 rounded-lg px-3 py-2.5"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-sm font-medium text-white">
                {a.insurer}
              </span>
              <span className="text-xs text-slate-500">{a.year}</span>
            </div>
            <span className="text-xs font-mono text-amber-300">
              {formatPct(a.settlement_ratio)}
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1 pl-5">{a.reason}</p>
        </div>
      ))}
    </div>
  );
}

// ── Overview Chart ──────────────────────
function OverviewPanel() {
  const [data, setData] = useState<MLOverviewItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mlOverview()
      .then((res) => setData(res.predictions))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />
      </div>
    );
  }

  // Aggregate latest year data for chart
  const latestYear = data.reduce((max, d) => {
    const yr = d.year?.toString() || "";
    return yr > max ? yr : max;
  }, "");

  const latestData = data
    .filter((d) => d.year?.toString() === latestYear)
    .sort((a, b) => b.actual_ratio - a.actual_ratio)
    .slice(0, 15);

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        Top 15 insurers by settlement ratio ({latestYear})
      </p>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={latestData}
          margin={{ top: 5, right: 10, left: 10, bottom: 60 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="insurer"
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            angle={-45}
            textAnchor="end"
            interval={0}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            domain={[0.8, 1]}
            tickFormatter={(v: number) => formatPct(v)}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as MLOverviewItem;
              return (
                <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 shadow-xl text-xs">
                  <p className="font-medium text-white">{d.insurer}</p>
                  <p className="text-green-400">
                    Actual: {formatPct(d.actual_ratio)}
                  </p>
                  <p className="text-brand-400">
                    Predicted: {formatPct(d.predicted_ratio)}
                  </p>
                  <p className="text-slate-400">
                    Claims: {d.total_claims.toLocaleString()}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="actual_ratio" name="Actual" radius={[3, 3, 0, 0]} maxBarSize={30}>
            {latestData.map((d, i) => (
              <Cell
                key={i}
                fill={
                  d.actual_ratio >= 0.95
                    ? "#22c55e"
                    : d.actual_ratio >= 0.85
                    ? "#f59e0b"
                    : "#ef4444"
                }
              />
            ))}
          </Bar>
          <Bar
            dataKey="predicted_ratio"
            name="Predicted"
            fill="#3b82f680"
            radius={[3, 3, 0, 0]}
            maxBarSize={30}
          />
        </BarChart>
      </ResponsiveContainer>

      {/* Scatter: Actual vs Predicted */}
      <p className="text-xs text-slate-500 mt-4">
        Model Accuracy: Actual vs Predicted (all years)
      </p>
      <ResponsiveContainer width="100%" height={250}>
        <ScatterChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="actual_ratio"
            name="Actual"
            type="number"
            domain={[0.6, 1]}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v: number) => formatPct(v)}
          />
          <YAxis
            dataKey="predicted_ratio"
            name="Predicted"
            type="number"
            domain={[0.6, 1]}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v: number) => formatPct(v)}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as MLOverviewItem;
              return (
                <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 shadow-xl text-xs">
                  <p className="font-medium text-white">{d.insurer} ({d.year})</p>
                  <p className="text-green-400">Actual: {formatPct(d.actual_ratio)}</p>
                  <p className="text-brand-400">Predicted: {formatPct(d.predicted_ratio)}</p>
                </div>
              );
            }}
          />
          <Scatter data={data} fill="#3b82f6">
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={
                  Math.abs(d.residual) < 0.02
                    ? "#22c55e"
                    : Math.abs(d.residual) < 0.05
                    ? "#f59e0b"
                    : "#ef4444"
                }
                opacity={0.7}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Main Exported Component ──────────────
export default function MLInsights() {
  const [activeTab, setActiveTab] = useState<"predict" | "anomalies" | "overview">("overview");
  const [collapsed, setCollapsed] = useState(false);

  const tabs = [
    { id: "overview" as const, label: "Overview", icon: TrendingUp },
    { id: "predict" as const, label: "Predict", icon: Target },
    { id: "anomalies" as const, label: "Anomalies", icon: AlertTriangle },
  ];

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-600/20 flex items-center justify-center">
            <Brain className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-white">ML Insights</h3>
            <p className="text-[10px] text-slate-500">
              Insurance Claims Prediction & Anomaly Detection
            </p>
          </div>
        </div>
        {collapsed ? (
          <ChevronDown className="w-4 h-4 text-slate-500" />
        ) : (
          <ChevronUp className="w-4 h-4 text-slate-500" />
        )}
      </button>

      {!collapsed && (
        <div className="px-5 pb-5 animate-fade-in">
          {/* Tabs */}
          <div className="flex gap-1 mb-4 bg-slate-800 rounded-lg p-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-slate-700 text-white"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                <tab.icon className="w-3 h-3" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content */}
          {activeTab === "overview" && <OverviewPanel />}
          {activeTab === "predict" && <PredictionPanel />}
          {activeTab === "anomalies" && <AnomalyPanel />}
        </div>
      )}
    </div>
  );
}
