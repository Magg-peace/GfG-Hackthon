"use client";

import React, { useState, useEffect, useCallback } from "react";
import ChatInterface, { ChatMessage } from "@/components/ChatInterface";
import Dashboard from "@/components/Dashboard";
import FileUpload from "@/components/FileUpload";
import MLInsights from "@/components/MLInsights";
import {
  queryDashboard,
  followUpQuery,
  getSuggestions,
  getHealth,
  ChartConfig,
  UploadResponse,
} from "@/lib/api";
import {
  Database,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
  ServerCrash,
  CheckCircle2,
  Cpu,
} from "lucide-react";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [charts, setCharts] = useState<ChartConfig[]>([]);
  const [summary, setSummary] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState("");
  const [lastSql, setLastSql] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [health, setHealth] = useState<{ postgres: boolean; ollama: boolean } | null>(null);

  useEffect(() => {
    getSuggestions().then((res) => setSuggestions(res.suggestions));
    getHealth().then((h) => setHealth(h)).catch(() => {});
  }, []);

  const addMessage = useCallback(
    (role: "user" | "assistant", content: string, extras?: Partial<ChatMessage>) => {
      const msg: ChatMessage = {
        id: Date.now().toString() + Math.random().toString(36).slice(2),
        role,
        content,
        timestamp: new Date(),
        ...extras,
      };
      setMessages((prev) => [...prev, msg]);
      return msg;
    },
    []
  );

  const handleSendMessage = useCallback(
    async (message: string) => {
      addMessage("user", message);
      setIsLoading(true);

      try {
        let result;

        // Use follow-up if we have prior context
        const isFollowUp =
          lastQuery &&
          lastSql &&
          sessionId &&
          messages.length > 0;

        if (isFollowUp) {
          result = await followUpQuery(message, sessionId!, lastQuery, lastSql);
        } else {
          result = await queryDashboard(message, sessionId);
        }

        if (result.session_id) {
          setSessionId(result.session_id);
        }

        if (result.success && result.charts?.length > 0) {
          setCharts(result.charts);
          setSummary(result.summary || "");
          setLastQuery(message);
          setLastSql(
            result.charts.map((c) => c.sql_executed || c.sql).join(";\n")
          );

          addMessage("assistant", result.summary || "Dashboard updated with your results.", {
            thinking: result.thinking,
            assumptions: result.assumptions,
          });
        } else {
          const errorMsg =
            result.error ||
            "I couldn't generate charts for that query. Please try rephrasing your question.";
          addMessage("assistant", errorMsg, { isError: true });
        }
      } catch (err) {
        const errorText =
          err instanceof Error ? err.message : "An unexpected error occurred.";
        addMessage("assistant", `Sorry, something went wrong: ${errorText}`, {
          isError: true,
        });
      } finally {
        setIsLoading(false);
      }
    },
    [addMessage, lastQuery, lastSql, sessionId, messages.length]
  );

  const handleUploadComplete = useCallback(
    (result: UploadResponse) => {
      setSessionId(result.session_id);
      setUploadedFile(result.filename);
      setCharts([]);
      setSummary("");
      setMessages([]);
      setLastQuery("");
      setLastSql("");

      getSuggestions(result.session_id).then((res) =>
        setSuggestions(res.suggestions)
      );

      addMessage(
        "assistant",
        `Successfully loaded **${result.filename}** (${result.row_count.toLocaleString()} rows, ` +
        `${result.columns.length} columns). The data has been stored in ${
          (result as unknown as { postgres?: boolean }).postgres ? "PostgreSQL" : "SQLite"
        }. Ask me anything about it!`
      );
    },
    [addMessage]
  );

  const handleClearSession = useCallback(() => {
    setSessionId(null);
    setUploadedFile(null);
    setCharts([]);
    setSummary("");
    setMessages([]);
    setLastQuery("");
    setLastSql("");
    getSuggestions().then((res) => setSuggestions(res.suggestions));
  }, []);

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-6 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">
              InsightAI
            </h1>
            <p className="text-[10px] text-slate-500 -mt-0.5">
              Conversational Business Intelligence
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* System status badges */}
          {health && (
            <div className="hidden sm:flex items-center gap-2">
              <span
                className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded-full ${
                  health.postgres
                    ? "bg-emerald-900/30 text-emerald-400 border border-emerald-700/30"
                    : "bg-slate-800 text-slate-500"
                }`}
                title={health.postgres ? "PostgreSQL connected" : "Using SQLite"}
              >
                <Database className="w-3 h-3" />
                {health.postgres ? "PostgreSQL" : "SQLite"}
              </span>
              <span
                className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded-full ${
                  health.ollama
                    ? "bg-blue-900/30 text-blue-400 border border-blue-700/30"
                    : "bg-slate-800 text-slate-500"
                }`}
                title={health.ollama ? "Ollama (local LLM) running" : "Using Gemini API"}
              >
                <Cpu className="w-3 h-3" />
                {health.ollama ? "Ollama" : "Gemini"}
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Database className="w-3.5 h-3.5" />
            <span>
              {uploadedFile ? uploadedFile : "Sample Business Data"}
            </span>
          </div>
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 text-slate-500 hover:text-white rounded-lg hover:bg-slate-800 transition-colors lg:hidden"
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen className="w-4 h-4" />
            ) : (
              <PanelLeftClose className="w-4 h-4" />
            )}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Sidebar */}
        <div
          className={`flex-shrink-0 border-r border-slate-800 bg-slate-900/50 flex flex-col transition-all duration-300 ${
            sidebarCollapsed
              ? "w-0 overflow-hidden"
              : "w-full lg:w-[420px]"
          }`}
        >
          {/* File Upload Area */}
          <div className="flex-shrink-0 p-4 border-b border-slate-800">
            <FileUpload
              onUploadComplete={handleUploadComplete}
              currentFile={uploadedFile}
              onClearSession={handleClearSession}
            />
          </div>

          {/* Chat */}
          <div className="flex-1 overflow-hidden">
            <ChatInterface
              messages={messages}
              onSendMessage={handleSendMessage}
              isLoading={isLoading}
              suggestions={suggestions}
            />
          </div>
        </div>

        {/* Dashboard Area */}
        <div className="flex-1 overflow-y-auto bg-slate-950/50">
          {/* ML Insights Panel */}
          <div className="px-6 pt-6">
            <MLInsights />
          </div>

          {/* Charts Dashboard with export */}
          <Dashboard
            charts={charts}
            summary={summary}
            sessionId={sessionId}
            lastQuery={lastQuery}
          />
        </div>
      </div>
    </div>
  );
}
