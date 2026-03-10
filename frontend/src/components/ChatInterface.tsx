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
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-brand-600/20 flex items-center justify-center mb-4">
              <Sparkles className="w-8 h-8 text-brand-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              Ask anything about your data
            </h2>
            <p className="text-slate-400 text-sm max-w-md mb-6">
              Type a question in plain English and I&apos;ll generate interactive
              charts and insights for you.
            </p>

            {showSuggestions && suggestions.length > 0 && (
              <div className="w-full max-w-lg space-y-2">
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">
                  Try asking
                </p>
                {suggestions.slice(0, 4).map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleSuggestionClick(s)}
                    className="w-full text-left px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-700/50 hover:border-brand-500/50 hover:bg-slate-800 transition-all text-sm text-slate-300 hover:text-white"
                  >
                    <Sparkles className="w-3.5 h-3.5 inline mr-2 text-brand-400" />
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
            className={`flex gap-3 animate-fade-in ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {msg.role === "assistant" && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center mt-0.5">
                <Bot className="w-4 h-4 text-blue-400" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-md ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : msg.isError
                  ? "bg-red-900/30 border border-red-700/50 text-red-200"
                  : "bg-slate-800 border border-slate-700 text-slate-200"
              }`}
            >
              {msg.isError && (
                <div className="flex items-center gap-2 mb-1">
                  <AlertCircle className="w-4 h-4 text-red-400" />
                  <span className="text-xs font-medium text-red-400">Error</span>
                </div>
              )}
              <div className="chat-message text-sm whitespace-pre-wrap">
                {msg.content}
              </div>
              {msg.thinking && (
                <details className="mt-2">
                  <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400">
                    <ChevronDown className="w-3 h-3 inline mr-1" />
                    Reasoning
                  </summary>
                  <p className="text-xs text-slate-500 mt-1 pl-2 border-l-2 border-slate-700">
                    {msg.thinking}
                  </p>
                </details>
              )}
              {msg.assumptions && msg.assumptions.length > 0 && (
                <div className="mt-2 text-xs text-amber-400/80">
                  <span className="font-medium">Assumptions: </span>
                  {msg.assumptions.join("; ")}
                </div>
              )}
              <div className="text-[10px] text-slate-500 mt-1">
                {msg.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
            {msg.role === "user" && (
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center mt-0.5">
                <User className="w-4 h-4 text-slate-300" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 animate-fade-in">
            <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-brand-600/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-brand-400" />
            </div>
            <div className="bg-slate-800 rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                <span className="text-sm text-slate-400">
                  Analyzing your data and generating charts...
                </span>
              </div>
              <div className="mt-3 space-y-2">
                <div className="skeleton h-3 w-48" />
                <div className="skeleton h-3 w-36" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion pills (shown after messages exist) */}
      {messages.length > 0 && showSuggestions && suggestions.length > 0 && (
        <div className="px-4 py-2 flex gap-2 overflow-x-auto">
          {suggestions.slice(0, 3).map((s, i) => (
            <button
              key={i}
              onClick={() => handleSuggestionClick(s)}
              disabled={isLoading}
              className="flex-shrink-0 text-xs px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-400 hover:text-white hover:border-brand-500/50 transition-all disabled:opacity-50"
            >
              {s.length > 50 ? s.slice(0, 50) + "..." : s}
            </button>
          ))}
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-slate-800 px-4 py-3 bg-slate-950">
        <div className="flex items-end gap-2 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 focus-within:border-blue-500 focus-within:shadow-inner transition-all">
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your data..."
            rows={1}
            className="flex-1 bg-transparent text-white placeholder-slate-500 text-sm resize-none outline-none max-h-[120px]"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="flex-shrink-0 w-8 h-8 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed flex items-center justify-center transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/20"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
        <p className="text-[10px] text-slate-600 mt-1.5 text-center">
          Powered by Google Gemini • Charts generated from your data in real-time
        </p>
      </div>
    </div>
  );
}
