"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Sparkles,
  User,
  Bot,
  Loader2,
  AlertCircle,
  ChevronDown,
} from "lucide-react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  thinking?: string;
  assumptions?: string[];
  isError?: boolean;
}

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  suggestions: string[];
}

export default function ChatInterface({
  messages,
  onSendMessage,
  isLoading,
  suggestions,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSendMessage(trimmed);
    setInput("");
    setShowSuggestions(false);
    if (inputRef.current) inputRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  };

  const handleSuggestionClick = (suggestion: string) => {
    onSendMessage(suggestion);
    setShowSuggestions(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-5">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in px-3">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#A5B4FC]/20 to-[#93C5FD]/15 flex items-center justify-center mb-4 shadow-md border border-[#C7D2FE]/30">
              <Sparkles className="w-7 h-7 text-[#6366F1]" />
            </div>
            <h2 className="text-base font-semibold text-[#1F2937] mb-1.5 tracking-tight">
              Ask anything about your data
            </h2>
            <p className="text-[#9CA3AF] text-xs max-w-[260px] mb-6 leading-relaxed">
              Type a question in plain English and I&apos;ll generate interactive
              charts and insights.
            </p>

            {showSuggestions && suggestions.length > 0 && (
              <div className="w-full space-y-2">
                <p className="section-label text-center mb-2.5">
                  Try asking
                </p>
                {suggestions.slice(0, 4).map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleSuggestionClick(s)}
                    className="w-full text-left px-3.5 py-3 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] hover:border-[#C7D2FE] hover:bg-[#EEF2FF]/50 transition-all duration-300 text-xs text-[#6B7280] hover:text-[#1F2937] group shadow-sm"
                  >
                    <Sparkles className="w-3 h-3 inline mr-2 text-[#C7D2FE] group-hover:text-[#818CF8] transition-colors" />
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2.5 animate-fade-in ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {msg.role === "assistant" && (
              <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-[#A5B4FC]/25 to-[#818CF8]/15 flex items-center justify-center mt-0.5 border border-[#C7D2FE]/30">
                <Bot className="w-3.5 h-3.5 text-[#6366F1]" />
              </div>
            )}
            <div
              className={`max-w-[82%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-gradient-to-br from-[#A5B4FC] to-[#818CF8] text-white shadow-md shadow-[#A5B4FC]/20"
                  : msg.isError
                  ? "bg-[#FEF2F2] border border-[#FECACA] text-[#991B1B]"
                  : "bg-white border border-[#E5E7EB] text-[#374151] shadow-md shadow-black/[0.03]"
              }`}
            >
              {msg.isError && (
                <div className="flex items-center gap-2 mb-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-[#EF4444]" />
                  <span className="text-[10px] font-semibold text-[#EF4444] uppercase tracking-wide">Error</span>
                </div>
              )}
              <div className="chat-message text-[13px] whitespace-pre-wrap leading-relaxed">
                {msg.content}
              </div>
              {msg.thinking && (
                <details className="mt-2.5">
                  <summary className="text-[11px] text-[#9CA3AF] cursor-pointer hover:text-[#6B7280] transition-colors">
                    <ChevronDown className="w-3 h-3 inline mr-1" />
                    Reasoning
                  </summary>
                  <p className="text-[11px] text-[#9CA3AF] mt-1.5 pl-2.5 border-l-2 border-[#E5E7EB] leading-relaxed">
                    {msg.thinking}
                  </p>
                </details>
              )}
              {msg.assumptions && msg.assumptions.length > 0 && (
                <div className="mt-2 text-[11px] text-[#D97706]">
                  <span className="font-medium">Assumptions: </span>
                  {msg.assumptions.join("; ")}
                </div>
              )}
              <div className={`text-[9px] mt-1.5 ${msg.role === 'user' ? 'text-white/50' : 'text-[#9CA3AF]'}`}>
                {msg.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
            {msg.role === "user" && (
              <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-[#F1F5F9] border border-[#E5E7EB] flex items-center justify-center mt-0.5">
                <User className="w-3.5 h-3.5 text-[#6B7280]" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-2.5 animate-fade-in">
            <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-[#A5B4FC]/25 to-[#818CF8]/15 flex items-center justify-center border border-[#C7D2FE]/30">
              <Bot className="w-3.5 h-3.5 text-[#6366F1]" />
            </div>
            <div className="bg-white border border-[#E5E7EB] rounded-2xl px-4 py-3.5 shadow-md shadow-black/[0.03]">
              <div className="flex items-center gap-2.5">
                <div className="flex gap-1">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
                <span className="text-[12px] text-[#9CA3AF]">
                  VizPulse is analyzing your data...
                </span>
              </div>
              <div className="mt-3 space-y-2">
                <div className="skeleton h-2 w-48" />
                <div className="skeleton h-2 w-36" />
                <div className="skeleton h-2 w-24" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion pills (shown after messages exist) */}
      {messages.length > 0 && showSuggestions && suggestions.length > 0 && (
        <div className="px-4 py-2 flex gap-2 overflow-x-auto border-t border-[#E5E7EB]">
          {suggestions.slice(0, 3).map((s, i) => (
            <button
              key={i}
              onClick={() => handleSuggestionClick(s)}
              disabled={isLoading}
              className="flex-shrink-0 text-[11px] px-3 py-1.5 rounded-full bg-[#F8FAFC] border border-[#E5E7EB] text-[#9CA3AF] hover:text-[#1F2937] hover:border-[#C7D2FE] hover:bg-[#EEF2FF]/50 transition-all duration-300 disabled:opacity-40"
            >
              {s.length > 50 ? s.slice(0, 50) + "..." : s}
            </button>
          ))}
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-[#E5E7EB] px-3.5 py-3.5 bg-white">
        <div className="flex items-end gap-2.5 bg-[#F8FAFC] border border-[#E5E7EB] rounded-xl px-3.5 py-2.5 focus-within:border-[#A5B4FC] focus-within:shadow-[0_0_0_3px_rgba(165,180,252,0.15)] transition-all duration-300">
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your data..."
            rows={1}
            className="flex-1 bg-transparent text-[#1F2937] placeholder-[#D1D5DB] text-[13px] resize-none outline-none max-h-[100px] leading-relaxed"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-[#A5B4FC] to-[#818CF8] hover:from-[#818CF8] hover:to-[#6366F1] disabled:from-[#E5E7EB] disabled:to-[#E5E7EB] disabled:cursor-not-allowed flex items-center justify-center transition-all duration-300 hover:shadow-md hover:shadow-[#A5B4FC]/25 hover:-translate-y-0.5 disabled:hover:translate-y-0"
          >
            <Send className="w-3.5 h-3.5 text-white" />
          </button>
        </div>
        <p className="text-[9px] text-[#D1D5DB] mt-2 text-center tracking-wide">
          Powered by Google Gemini · Real-time chart generation
        </p>
      </div>
    </div>
  );
}
