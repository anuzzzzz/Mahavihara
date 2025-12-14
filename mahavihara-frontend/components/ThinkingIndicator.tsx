"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

const steps = [
  "Analyzing response...",
  "Tracing knowledge graph...",
  "Identifying root cause...",
  "Applying Socratic method...",
  "Generating response..."
];

export function ThinkingIndicator() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => (s < steps.length - 1 ? s + 1 : s));
    }, 400);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-3 p-3 mb-3 text-xs text-emerald-400 bg-emerald-950/20 border border-emerald-900/50 rounded-lg">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span className="font-mono tracking-wide">{steps[step]}</span>
    </div>
  );
}
