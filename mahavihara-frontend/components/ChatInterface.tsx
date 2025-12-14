// components/ChatInterface.tsx
"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, RotateCcw } from "lucide-react";
import { Message } from "@/lib/api";
import AgentThinking from "./AgentThinking";

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  onReset: () => void;
  isLoading: boolean;
  phase: string;
  mastery: Record<string, number>;
  rootCause?: string;
}

export default function ChatInterface({
  messages,
  onSendMessage,
  onReset,
  isLoading,
  phase,
  mastery,
  rootCause,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput("");
    }
  };

  // Quick answer buttons for MCQ
  const QuickAnswers = () => (
    <div className="flex gap-2 mb-4">
      {["A", "B", "C", "D"].map((opt) => (
        <button
          key={opt}
          onClick={() => onSendMessage(opt)}
          disabled={isLoading}
          className="w-12 h-12 rounded-lg bg-zinc-800 border border-zinc-700 
                     hover:border-cyan-400 hover:text-cyan-400 
                     transition-all font-mono font-bold
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {opt}
        </button>
      ))}
    </div>
  );

  // Mastery bar component
  const MasteryBar = () => (
    <div className="flex gap-2 text-xs font-mono mb-4 flex-wrap">
      {Object.entries(mastery).map(([concept, score]) => {
        const percent = Math.round(score * 100);
        const color = score >= 0.6 ? "text-green-400" : score < 0.4 ? "text-red-400" : "text-yellow-400";
        return (
          <span key={concept} className={`${color}`}>
            {concept.slice(0, 3).toUpperCase()}:{percent}%
          </span>
        );
      })}
    </div>
  );

  return (
    <div className="flex flex-col h-full bg-zinc-900 rounded-lg border border-zinc-800">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div>
          <h2 className="text-lg font-bold text-cyan-400 font-mono">MAHAVIHARA</h2>
          <p className="text-xs text-zinc-500">
            Phase: <span className="text-cyan-400">{phase.toUpperCase()}</span>
          </p>
        </div>
        <button
          onClick={onReset}
          className="p-2 rounded-lg hover:bg-zinc-800 transition-colors"
          title="Reset Session"
        >
          <RotateCcw className="w-5 h-5 text-zinc-400" />
        </button>
      </div>

      {/* Mastery Display */}
      <div className="px-4 pt-4">
        <MasteryBar />
      </div>

      {/* Agent Thinking */}
      <AgentThinking isVisible={isLoading} phase={phase} rootCause={rootCause} />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-4 py-3 ${
                msg.role === "user"
                  ? "bg-cyan-600 text-white"
                  : "bg-zinc-800 text-zinc-100"
              }`}
            >
              <pre className="whitespace-pre-wrap text-sm font-mono font-normal break-words">
                {msg.content}
              </pre>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800 rounded-lg px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce delay-100" />
                <span className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce delay-200" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Answers (for MCQ phases) */}
      {(phase === "diagnostic" || phase === "verifying") && (
        <div className="px-4">
          <QuickAnswers />
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-zinc-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              phase === "diagnostic" || phase === "verifying"
                ? "Type A, B, C, or D..."
                : "Type your response..."
            }
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3
                       text-white placeholder-zinc-500 font-mono text-sm
                       focus:outline-none focus:border-cyan-400 transition-colors"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-3 bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-700
                       rounded-lg transition-colors disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  );
}