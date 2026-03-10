"use client";

import React, { useState } from "react";
import { ChartConfig, exportDashboard } from "@/lib/api";
import ChartRenderer from "./ChartRenderer";
import { LayoutDashboard, Download, FileText, Sheet, Loader2 } from "lucide-react";

interface DashboardProps {
  charts: ChartConfig[];
  summary?: string;
  sessionId?: string | null;
  lastQuery?: string;
}

export default function Dashboard({ charts, summary, sessionId, lastQuery }: DashboardProps) {
  const [exporting, setExporting] = useState<"pdf" | "excel" | null>(null);

  const handleExport = async (format: "pdf" | "excel") => {
    setExporting(format);
    try {
      const blob = await exportDashboard({
        session_id: sessionId,
        query: lastQuery || "",
        summary: summary || "",
        charts,
        format,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = format === "pdf" ? "bi_report.pdf" : "bi_report.xlsx";
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert(`Export failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setExporting(null);
    }
  };

  if (!charts.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-8">
        <div className="w-20 h-20 rounded-2xl bg-slate-900/60 border border-slate-700 flex items-center justify-center mb-4">
          <LayoutDashboard className="w-10 h-10 text-slate-600" />
        </div>
        <h2 className="text-xl font-semibold text-slate-400 mb-2">
          Your dashboard will appear here
        </h2>
        <p className="text-sm text-slate-600 max-w-md">
          Ask a question in the chat panel to generate interactive charts and
          visualizations from your data.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      {/* Summary Banner + Export buttons */}
      <div className="mb-6 flex items-start gap-4">
        {summary && (
          <div className="flex-1 bg-blue-900/30 border border-blue-700 rounded-xl px-5 py-4 animate-fade-in">
            <p className="text-sm text-blue-300 font-medium">{summary}</p>
          </div>
        )}
        {/* Export controls */}
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={() => handleExport("pdf")}
            disabled={!!exporting}
            className="flex items-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-xl text-xs font-medium shadow-lg transition-all duration-200 hover:scale-[1.02] disabled:opacity-50"
            title="Export as PDF"
          >
            {exporting === "pdf" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <FileText className="w-3.5 h-3.5" />
            )}
            PDF
          </button>
          <button
            onClick={() => handleExport("excel")}
            disabled={!!exporting}
            className="flex items-center gap-1.5 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-xl text-xs font-medium shadow-lg transition-all duration-200 hover:scale-[1.02] disabled:opacity-50"
            title="Export as Excel"
          >
            {exporting === "excel" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5" />
            )}
            Excel
          </button>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {charts.map((chart, i) => (
          <div
            key={i}
            className={
              chart.chart_type === "table" || charts.length === 1
                ? "xl:col-span-2"
                : ""
            }
          >
            <ChartRenderer chart={chart} />
          </div>
        ))}
      </div>
    </div>
  );
}

