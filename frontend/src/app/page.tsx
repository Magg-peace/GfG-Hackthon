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
  explainData,
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
        } else if (result.success) {
          // Explain-type response or query returned no chart data
          addMessage("assistant", result.summary || result.error || "The query returned no results. Try asking a different question.");
          // Update suggestions if the backend returned them (e.g. from explain)
          const resp = result as unknown as Record<string, unknown>;
          if (Array.isArray(resp.suggested_questions) && (resp.suggested_questions as string[]).length > 0) {
            setSuggestions(resp.suggested_questions as string[]);
          }
        } else {
          const errorMsg =
            result.error ||
            result.summary ||
            "Something went wrong processing your query. Please try again.";
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
    async (result: UploadResponse) => {
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

      // Confirm upload
      addMessage(
        "assistant",
        `Got it! **${result.filename}** loaded — ${result.row_count.toLocaleString()} rows across ${result.columns.length} columns. Let me analyse what this data is about…`
      );

      setIsLoading(true);
      try {
        const explanation = await explainData(result.session_id);

        const suggestionsBlock =
          explanation.suggested_questions?.length
            ? `\n\nHere are some things you can ask me:\n${explanation.suggested_questions
                .map((q) => `• ${q}`)
                .join("\n")}`
            : "";

        addMessage(
          "assistant",
          `**${explanation.title}**\n\n${explanation.description}${suggestionsBlock}\n\nWhat would you like to visualise?`
        );

        // Replace generic suggestions with data-specific ones
        if (explanation.suggested_questions?.length) {
          setSuggestions(explanation.suggested_questions);
        }
      } catch {
        addMessage(
          "assistant",
          "Data loaded! What would you like to visualise? You can ask me anything — trends, comparisons, top performers, or a summary overview."
        );
      } finally {
        setIsLoading(false);
      }
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
    <div className="h-screen flex flex-col bg-[#06080f]">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-[#1c2340] bg-[#06080f]/85 backdrop-blur-2xl px-5 py-3 flex items-center justify-between z-20">
        <div className="flex items-center gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#4f8fff] via-[#7dd3fc] to-[#34d399] flex items-center justify-center shadow-lg shadow-[#4f8fff]/25">
            <Sparkles className="w-[18px] h-[18px] text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight leading-none">
              <span className="bg-gradient-to-r from-[#4f8fff] via-[#7dd3fc] to-[#34d399] bg-clip-text text-transparent">VizPulse</span>
            </h1>
            <p className="text-[10px] text-[#5a6380] mt-0.5 tracking-widest uppercase font-medium">
              Conversational Business Intelligence
            </p>  
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          {/* System status badges */}
          {health && (
            <div className="hidden sm:flex items-center gap-1.5">
              <span
                className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-lg font-medium ${
                  health.postgres
                    ? "bg-[#34d399]/10 text-[#34d399] border border-[#34d399]/20"
                    : "bg-[#151b30] text-[#5a6380] border border-[#1c2340]"
                }`}
                title={health.postgres ? "PostgreSQL connected" : "Using SQLite"}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${health.postgres ? 'bg-[#34d399]' : 'bg-[#5a6380]'}`} />
                <Database className="w-3 h-3" />
                {health.postgres ? "PostgreSQL" : "SQLite"}
              </span>
              <span
                className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-lg font-medium ${
                  health.ollama
                    ? "bg-[#4f8fff]/10 text-[#4f8fff] border border-[#4f8fff]/20"
                    : "bg-[#151b30] text-[#5a6380] border border-[#1c2340]"
                }`}
                title={health.ollama ? "Ollama (local LLM) running" : "Using Gemini API"}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${health.ollama ? 'bg-[#4f8fff]' : 'bg-[#5a6380]'}`} />
                <Cpu className="w-3 h-3" />
                {health.ollama ? "Ollama" : "Gemini"}
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 text-[11px] text-[#8b95b0] bg-[#080c18] px-3 py-1.5 rounded-lg border border-[#1c2340] font-medium">
            <Database className="w-3.5 h-3.5 text-[#4f8fff]" />
            <span className="max-w-[140px] truncate">
              {uploadedFile ? uploadedFile : "Sample Business Data"}
            </span>
          </div>
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 text-[#5a6380] hover:text-white rounded-lg hover:bg-[#151b30] transition-all duration-200 lg:hidden"
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
          className={`flex-shrink-0 border-r border-[#1c2340] bg-[#080c18] flex flex-col transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
            sidebarCollapsed
              ? "w-0 overflow-hidden"
              : "w-full lg:w-[360px]"
          }`}
        >
          {/* File Upload Area */}
          <div className="flex-shrink-0 p-3.5 border-b border-[#1c2340]">
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
        <div className="flex-1 overflow-y-auto bg-dashboard-gradient">
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
