// components/ChatInterface.tsx
// Uses explicit state flags from backend (quizPassed, canAdvance) instead of guessing

"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, RotateCcw, BookOpen, HelpCircle, Play, ArrowRight, RefreshCw } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface QuickAction {
  label: string;
  message: string;
  icon: React.ReactNode;
  variant: "primary" | "secondary" | "success";
}

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  onReset: () => void;
  isLoading: boolean;
  phase: string;
  mastery: Record<string, number>;
  // NEW: Explicit state from backend
  quizPassed: boolean | null;
  canAdvance: boolean;
  nextConcept: string | null;
}

export default function ChatInterface({
  messages,
  onSendMessage,
  onReset,
  isLoading,
  phase,
  mastery,
  quizPassed,
  canAdvance,
  nextConcept,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput("");
    }
  };

  const handleQuickAction = (message: string) => {
    if (!isLoading) {
      onSendMessage(message);
    }
  };

  // Get quick actions based on EXPLICIT state from backend
  const getQuickActions = (): QuickAction[] => {
    // During active quiz - no buttons
    if (phase === "quiz") {
      return [];
    }

    // Course complete
    if (phase === "complete") {
      return [
        {
          label: "Start Over",
          message: "restart",
          icon: <RotateCcw className="w-3 h-3" />,
          variant: "secondary",
        },
      ];
    }

    // EVALUATE phase - use backend state!
    if (phase === "evaluate") {
      // User PASSED and can advance
      if (quizPassed === true && canAdvance) {
        return [
          {
            label: nextConcept ? `Continue to ${nextConcept}` : "Continue",
            message: "continue",
            icon: <ArrowRight className="w-3 h-3" />,
            variant: "success",
          },
          {
            label: "Review What I Missed",
            message: "explain what I missed",
            icon: <HelpCircle className="w-3 h-3" />,
            variant: "secondary",
          },
          {
            label: "Resources",
            message: "show me resources",
            icon: <BookOpen className="w-3 h-3" />,
            variant: "secondary",
          },
        ];
      }
      
      // User FAILED
      if (quizPassed === false) {
        return [
          {
            label: "Try Again",
            message: "quiz me",
            icon: <RefreshCw className="w-3 h-3" />,
            variant: "primary",
          },
          {
            label: "Explain My Mistakes",
            message: "explain what I got wrong",
            icon: <HelpCircle className="w-3 h-3" />,
            variant: "secondary",
          },
          {
            label: "Resources",
            message: "show me resources",
            icon: <BookOpen className="w-3 h-3" />,
            variant: "secondary",
          },
        ];
      }
      
      // Fallback for evaluate phase (should rarely happen)
      return [
        {
          label: "Continue",
          message: "continue",
          icon: <ArrowRight className="w-3 h-3" />,
          variant: "success",
        },
        {
          label: "Quiz Me",
          message: "quiz me",
          icon: <Play className="w-3 h-3" />,
          variant: "primary",
        },
      ];
    }

    // Q&A or Lesson phase
    if (phase === "qa" || phase === "lesson") {
      return [
        {
          label: "Quiz Me",
          message: "quiz me",
          icon: <Play className="w-3 h-3" />,
          variant: "primary",
        },
        {
          label: "Resources",
          message: "show me resources",
          icon: <BookOpen className="w-3 h-3" />,
          variant: "secondary",
        },
        {
          label: "Explain More",
          message: "explain this better",
          icon: <HelpCircle className="w-3 h-3" />,
          variant: "secondary",
        },
      ];
    }

    // Default
    return [
      {
        label: "Quiz Me",
        message: "quiz me",
        icon: <Play className="w-3 h-3" />,
        variant: "primary",
      },
    ];
  };

  const quickActions = getQuickActions();

  // Calculate overall mastery
  const masteryValues = Object.values(mastery);
  const overallMastery = masteryValues.length > 0
    ? Math.round((masteryValues.reduce((a, b) => a + b, 0) / masteryValues.length) * 100)
    : 50;

  const getButtonStyle = (variant: "primary" | "secondary" | "success") => {
    switch (variant) {
      case "primary":
        return "bg-cyan-500/20 text-cyan-400 border-cyan-500/50 hover:bg-cyan-500/30 hover:border-cyan-400";
      case "success":
        return "bg-green-500/20 text-green-400 border-green-500/50 hover:bg-green-500/30 hover:border-green-400";
      case "secondary":
      default:
        return "bg-zinc-800/50 text-zinc-300 border-zinc-700 hover:bg-zinc-700/50 hover:border-zinc-600";
    }
  };

  return (
    <div className="h-full flex flex-col rounded-xl border border-cyan-500/30 bg-zinc-900/50 overflow-hidden shadow-[0_0_30px_rgba(0,255,255,0.1)]">
      {/* Header */}
      <div className="p-3 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/80">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold font-mono text-cyan-400 drop-shadow-[0_0_10px_rgba(0,255,255,0.5)]">
            MAHAVIHARA
          </h1>
          <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 font-mono uppercase">
            {phase}
          </span>
          {quizPassed === true && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-green-500/20 text-green-400 border border-green-500/30">
              ✓ Passed
            </span>
          )}
          {quizPassed === false && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">
              ✗ Try Again
            </span>
          )}
        </div>
        <button
          onClick={onReset}
          className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
          title="Reset session"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Mastery Bar */}
      <div className="px-3 py-2 border-b border-zinc-800/50 bg-zinc-900/30">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
            Overall Mastery
          </span>
          <span className={`text-xs font-mono ${overallMastery >= 60 ? 'text-green-400' : 'text-amber-400'}`}>
            {overallMastery}%
          </span>
        </div>
        <div className="flex gap-1">
          {Object.entries(mastery).map(([concept, score]) => (
            <div
              key={concept}
              className="flex-1 h-1.5 rounded-full overflow-hidden bg-zinc-800"
              title={`${concept}: ${Math.round(score * 100)}%`}
            >
              <div
                className={`h-full transition-all duration-500 ${
                  score >= 0.6
                    ? "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]"
                    : score < 0.4
                    ? "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]"
                    : "bg-amber-500"
                }`}
                style={{ width: `${score * 100}%` }}
              />
            </div>
          ))}
        </div>
        <div className="flex justify-between mt-1">
          {Object.keys(mastery).map((concept) => (
            <span key={concept} className="text-[8px] text-zinc-600 font-mono uppercase">
              {concept.slice(0, 3)}
            </span>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                message.role === "user"
                  ? "bg-cyan-500/20 text-cyan-100 border border-cyan-500/30"
                  : "bg-zinc-800/50 text-zinc-200 border border-zinc-700/50"
              }`}
            >
              <div className="prose prose-invert prose-sm max-w-none
                  prose-p:my-1 prose-p:leading-relaxed
                  prose-ul:my-1 prose-li:my-0.5
                  prose-strong:text-cyan-400 prose-strong:font-semibold
                  prose-code:text-amber-400 prose-code:bg-zinc-800 prose-code:px-1 prose-code:rounded
                  prose-a:text-cyan-400 prose-a:no-underline hover:prose-a:underline">
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg px-3 py-2">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Action Buttons */}
      {quickActions.length > 0 && !isLoading && (
        <div className="px-3 py-2 border-t border-zinc-800/50 bg-zinc-900/30">
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action, index) => (
              <button
                key={index}
                onClick={() => handleQuickAction(action.message)}
                disabled={isLoading}
                className={`
                  flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
                  border transition-all duration-200
                  disabled:opacity-50 disabled:cursor-not-allowed
                  ${getButtonStyle(action.variant)}
                `}
              >
                {action.icon}
                {action.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-zinc-800 bg-zinc-900/80">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              phase === "quiz" 
                ? "Enter your answer (A, B, C, or D)..." 
                : "Ask a question or explain your thinking..."
            }
            disabled={isLoading}
            className="flex-1 bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2 text-sm
              text-zinc-100 placeholder:text-zinc-500
              focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-2 rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30
              hover:bg-cyan-500/30 hover:border-cyan-400
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}