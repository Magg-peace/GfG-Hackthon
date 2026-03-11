"use client";

import React, { useState } from "react";
import { ChartConfig, exportDashboard } from "@/lib/api";
import ChartRenderer from "./ChartRenderer";
import { LayoutDashboard, Download, FileText, Sheet, Loader2, Sparkles, ArrowDownToLine } from "lucide-react";

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
        <div className="w-20 h-20 rounded-2xl bg-[#0e1225] border border-[#1c2340] flex items-center justify-center mb-5 animate-float">
          <LayoutDashboard className="w-9 h-9 text-[#2a3355]" />
        </div>
        <h2 className="text-lg font-semibold text-[#8b95b0] mb-2">
          Your dashboard will appear here
        </h2>
        <p className="text-sm text-[#5a6380] max-w-sm leading-relaxed">
          Ask a question in the chat panel to generate interactive charts and
          visualizations from your data.
        </p>
        <div className="mt-6 flex items-center gap-2 text-[10px] text-[#5a6380] bg-[#0e1225] px-3 py-1.5 rounded-lg border border-[#1c2340]">
          <Sparkles className="w-3 h-3 text-[#4f8fff]/40" />
          Powered by AI-driven analytics
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto px-6 py-6 space-y-6">
      {/* 1. AI Insight — Top priority in visual hierarchy */}
      {summary && (
        <div className="insight-card px-5 py-4 animate-fade-in">
          <div className="flex items-start gap-3.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#4f8fff]/15 to-[#8b5cf6]/10 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
              <Sparkles className="w-4 h-4 text-[#4f8fff]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="section-label text-[#4f8fff]/70 mb-1.5">AI Insight</p>
              <p className="text-[13px] text-[#c4ccdf] leading-relaxed">{summary}</p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Chart Visualizations — Primary content */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <p className="section-label">Visualizations</p>
          <span className="text-[10px] text-[#5a6380] bg-[#0e1225] px-2 py-0.5 rounded-md border border-[#1c2340]">
            {charts.length} chart{charts.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
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

      {/* 3. Export Options — Bottom action bar */}
      <div className="flex items-center justify-between pt-2 border-t border-[#1c2340]/40 animate-fade-in">
        <p className="section-label">Export Report</p>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport("pdf")}
            disabled={!!exporting}
            className="group flex items-center gap-2 px-4 py-2 bg-[#0e1225] hover:bg-[#151b30] text-[#e87171] border border-[#e87171]/15 hover:border-[#e87171]/30 rounded-xl text-xs font-medium transition-all duration-300 hover:shadow-lg hover:shadow-[#e87171]/5 hover:-translate-y-0.5 disabled:opacity-40 disabled:hover:translate-y-0"
            title="Export as PDF"
          >
            {exporting === "pdf" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <FileText className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
            )}
            Export PDF
          </button>
          <button
            onClick={() => handleExport("excel")}
            disabled={!!exporting}
            className="group flex items-center gap-2 px-4 py-2 bg-[#0e1225] hover:bg-[#151b30] text-[#34d399] border border-[#34d399]/15 hover:border-[#34d399]/30 rounded-xl text-xs font-medium transition-all duration-300 hover:shadow-lg hover:shadow-[#34d399]/5 hover:-translate-y-0.5 disabled:opacity-40 disabled:hover:translate-y-0"
            title="Export as Excel"
          >
            {exporting === "excel" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ArrowDownToLine className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
            )}
            Export Excel
          </button>
        </div>
      </div>
    </div>
  );
}

