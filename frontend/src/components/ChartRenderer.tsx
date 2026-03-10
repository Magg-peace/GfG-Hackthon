"use client";

import React, { useState } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ChartConfig } from "@/lib/api";
import {
  TrendingUp,
  Code,
  ChevronDown,
  AlertCircle,
  Table,
  ArrowUpDown,
} from "lucide-react";

const COLORS = [
  "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#f97316", "#14b8a6", "#a855f7",
  "#6366f1", "#84cc16",
];

function formatNumber(val: unknown): string {
  if (val === null || val === undefined) return "—";
  const n = typeof val === "string" ? parseFloat(val) : (val as number);
  if (isNaN(n)) return String(val);
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + "K";
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toFixed(2);
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 shadow-xl">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-sm font-medium" style={{ color: entry.color }}>
          {entry.name}: {formatNumber(entry.value)}
        </p>
      ))}
    </div>
  );
}

interface SortConfig {
  key: string;
  direction: "asc" | "desc";
}

function DataTable({ data }: { data: Record<string, unknown>[] }) {
  const [sortConfig, setSortConfig] = useState<SortConfig | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const pageSize = 10;

  if (!data.length) return <p className="text-slate-500 text-sm">No data</p>;

  const columns = Object.keys(data[0]);

  const sortedData = React.useMemo(() => {
    if (!sortConfig) return data;
    return [...data].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      if (aVal === bVal) return 0;
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      const aNum = Number(aVal);
      const bNum = Number(bVal);
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortConfig.direction === "asc" ? aNum - bNum : bNum - aNum;
      }
      const cmp = String(aVal).localeCompare(String(bVal));
      return sortConfig.direction === "asc" ? cmp : -cmp;
    });
  }, [data, sortConfig]);

  const paginated = sortedData.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize
  );
  const totalPages = Math.ceil(sortedData.length / pageSize);

  const handleSort = (key: string) => {
    setSortConfig((prev) =>
      prev?.key === key
        ? { key, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" }
    );
    setCurrentPage(0);
  };

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className="text-left px-3 py-2 text-slate-400 font-medium cursor-pointer hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1">
                    {col}
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.map((row, i) => (
              <tr
                key={i}
                className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors"
              >
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2 text-slate-300">
                    {formatNumber(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
          <span>
            Page {currentPage + 1} of {totalPages} ({sortedData.length} rows)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
              disabled={currentPage === 0}
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              onClick={() =>
                setCurrentPage((p) => Math.min(totalPages - 1, p + 1))
              }
              disabled={currentPage >= totalPages - 1}
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ chart }: { chart: ChartConfig }) {
  const value =
    chart.data?.[0]?.[chart.value_column || "metric_value"] ?? "—";
  return (
    <div className="flex flex-col items-center justify-center py-6">
      <p className="text-sm text-slate-400 mb-2">{chart.label || chart.title}</p>
      <p className="text-4xl font-bold text-white">
        {chart.prefix || ""}
        {formatNumber(value)}
        {chart.suffix || ""}
      </p>
      {chart.insight && (
        <p className="text-sm text-slate-400 mt-3 flex items-center gap-1">
          <TrendingUp className="w-3.5 h-3.5 text-green-400" />
          {chart.insight}
        </p>
      )}
    </div>
  );
}

export default function ChartRenderer({ chart }: { chart: ChartConfig }) {
  const [showSql, setShowSql] = useState(false);

  if (chart.error) {
    return (
      <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 animate-slide-up">
        <h3 className="text-lg font-semibold text-white mb-2">{chart.title}</h3>
        <div className="flex items-center gap-2 text-red-400 bg-red-900/20 rounded-lg px-4 py-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium">Chart Error</p>
            <p className="text-xs text-red-300 mt-0.5">{chart.error}</p>
          </div>
        </div>
        {chart.sql_executed && (
          <details className="mt-3">
            <summary className="text-xs text-slate-500 cursor-pointer">
              View SQL
            </summary>
            <pre className="mt-1 text-xs bg-slate-900 rounded-lg p-3 overflow-x-auto text-slate-400">
              {chart.sql_executed}
            </pre>
          </details>
        )}
      </div>
    );
  }

  if (!chart.data?.length && chart.chart_type !== "metric") {
    return (
      <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 animate-slide-up">
        <h3 className="text-lg font-semibold text-white mb-2">{chart.title}</h3>
        <p className="text-sm text-slate-500">No data returned for this query.</p>
      </div>
    );
  }

  const xKey = chart.x_axis || (chart.data?.[0] ? Object.keys(chart.data[0])[0] : "x");
  const yKeys = chart.y_axis || (chart.data?.[0] ? Object.keys(chart.data[0]).filter((k) => k !== xKey) : ["y"]);

  const renderChart = () => {
    switch (chart.chart_type) {
      case "metric":
        return <MetricCard chart={chart} />;

      case "table":
        return <DataTable data={chart.data} />;

      case "pie":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={chart.data}
                dataKey={yKeys[0]}
                nameKey={xKey}
                cx="50%"
                cy="50%"
                outerRadius={110}
                innerRadius={50}
                paddingAngle={2}
                label={({ name, percent }: { name: string; percent: number }) =>
                  `${name}: ${(percent * 100).toFixed(0)}%`
                }
                labelLine={{ stroke: "#475569" }}
              >
                {chart.data.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }}
              />
            </PieChart>
          </ResponsiveContainer>
        );

      case "line":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chart.data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey={xKey}
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                label={
                  chart.x_label
                    ? { value: chart.x_label, position: "insideBottom", offset: -5, fill: "#64748b" }
                    : undefined
                }
              />
              <YAxis
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                tickFormatter={(v) => formatNumber(v)}
                label={
                  chart.y_label
                    ? { value: chart.y_label, angle: -90, position: "insideLeft", fill: "#64748b" }
                    : undefined
                }
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              {yKeys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 6, stroke: "#fff", strokeWidth: 2 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      case "area":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chart.data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey={xKey} tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} tickFormatter={(v) => formatNumber(v)} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              {yKeys.map((key, i) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLORS[i % COLORS.length]}
                  fill={COLORS[i % COLORS.length]}
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );

      case "scatter":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey={xKey}
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                name={chart.x_label || xKey}
                type="number"
              />
              <YAxis
                dataKey={yKeys[0]}
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                name={chart.y_label || yKeys[0]}
              />
              <Tooltip content={<CustomTooltip />} />
              <Scatter data={chart.data} fill={COLORS[0]} />
            </ScatterChart>
          </ResponsiveContainer>
        );

      case "bar":
      default:
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chart.data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey={xKey}
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                label={
                  chart.x_label
                    ? { value: chart.x_label, position: "insideBottom", offset: -5, fill: "#64748b" }
                    : undefined
                }
              />
              <YAxis
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                tickFormatter={(v) => formatNumber(v)}
                label={
                  chart.y_label
                    ? { value: chart.y_label, angle: -90, position: "insideLeft", fill: "#64748b" }
                    : undefined
                }
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              {yKeys.map((key, i) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={COLORS[i % COLORS.length]}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={60}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );
    }
  };

  return (
    <div className="glass-card-hover p-6 animate-slide-up transition-all duration-200">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white">{chart.title}</h3>
          {chart.insight && (
            <p className="text-sm text-slate-400 mt-1 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
              {chart.insight}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {chart.row_count !== undefined && (
            <span className="text-xs text-slate-500 bg-slate-900/80 px-2 py-1 rounded-md">
              <Table className="w-3 h-3 inline mr-1" />
              {chart.row_count} rows
            </span>
          )}
          <button
            onClick={() => setShowSql(!showSql)}
            className="text-xs text-slate-500 hover:text-slate-300 bg-slate-900/80 px-2 py-1 rounded-md transition-colors"
          >
            <Code className="w-3 h-3 inline mr-1" />
            SQL
            <ChevronDown
              className={`w-3 h-3 inline ml-0.5 transition-transform ${
                showSql ? "rotate-180" : ""
              }`}
            />
          </button>
        </div>
      </div>

      {/* SQL Expandable */}
      {showSql && chart.sql_executed && (
        <pre className="mb-4 text-xs bg-slate-950 rounded-lg p-3 overflow-x-auto text-emerald-400 border border-slate-700 font-mono">
          {chart.sql_executed}
        </pre>
      )}

      {/* Chart */}
      {renderChart()}
    </div>
  );
}
