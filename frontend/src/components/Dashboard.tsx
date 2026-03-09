"use client";

import React from "react";
import { ChartConfig } from "@/lib/api";
import ChartRenderer from "./ChartRenderer";
import { LayoutDashboard } from "lucide-react";

interface DashboardProps {
  charts: ChartConfig[];
  summary?: string;
}

export default function Dashboard({ charts, summary }: DashboardProps) {
  if (!charts.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-8">
        <div className="w-20 h-20 rounded-2xl bg-slate-800 flex items-center justify-center mb-4">
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
      {/* Summary Banner */}
      {summary && (
        <div className="mb-6 bg-brand-600/10 border border-brand-500/20 rounded-xl px-5 py-4 animate-fade-in">
          <p className="text-sm text-brand-200">{summary}</p>
        </div>
      )}

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
