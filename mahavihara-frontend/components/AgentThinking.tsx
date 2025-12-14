// components/AgentThinking.tsx
"use client";

import React from "react";

interface AgentThinkingProps {
  isVisible: boolean;
  phase: string;
  rootCause?: string;
}

export default function AgentThinking({ isVisible, phase, rootCause }: AgentThinkingProps) {
  if (!isVisible) return null;

  const getThinkingMessage = () => {
    switch (phase) {
      case "diagnostic":
        return "Analyzing your knowledge gaps...";
      case "teaching":
        return "Preparing personalized explanation...";
      case "verifying":
        return "Evaluating your understanding...";
      case "complete":
        return "Finalizing assessment...";
      default:
        return "Thinking...";
    }
  };

  return (
    <div className="mx-4 mb-3 p-3 rounded-lg bg-zinc-800/50 border border-cyan-500/20">
      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          <span className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
          <span className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse delay-150" />
          <span className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse delay-300" />
        </div>
        <span className="text-xs font-mono text-cyan-400">{getThinkingMessage()}</span>
      </div>
      {rootCause && (
        <div className="mt-2 text-[10px] text-zinc-500 font-mono">
          Focus: <span className="text-red-400">{rootCause}</span>
        </div>
      )}
    </div>
  );
}
