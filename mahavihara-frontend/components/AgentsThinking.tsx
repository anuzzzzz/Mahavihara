// components/AgentThinking.tsx
"use client";

import React, { useState, useEffect } from "react";
import { Terminal } from "lucide-react";

interface AgentThinkingProps {
  isVisible: boolean;
  phase: string;
  rootCause?: string;
}

const getThinkingSteps = (phase: string, rootCause?: string) => {
  if (phase === "diagnostic") {
    return [
      "Processing answer...",
      "Updating mastery scores...",
      "Preparing next question...",
    ];
  } else if (phase === "analyzing" || rootCause) {
    return [
      "Analyzing diagnostic results...",
      "Scanning knowledge graph...",
      "Tracing dependency chain...",
      `Root cause identified: ${rootCause || "Unknown"}`,
      "Generating teaching strategy...",
    ];
  } else if (phase === "teaching") {
    return [
      "Processing response...",
      "Applying Socratic method...",
      "Generating guiding question...",
    ];
  } else if (phase === "verifying") {
    return [
      "Evaluating answer...",
      "Updating mastery level...",
      "Checking completion criteria...",
    ];
  }
  return ["Processing..."];
};

export default function AgentThinking({ isVisible, phase, rootCause }: AgentThinkingProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [displayedText, setDisplayedText] = useState("");
  const steps = getThinkingSteps(phase, rootCause);

  useEffect(() => {
    if (!isVisible) {
      setCurrentStep(0);
      setDisplayedText("");
      return;
    }

    // Type out current step
    const step = steps[currentStep];
    let charIndex = 0;
    
    const typeInterval = setInterval(() => {
      if (charIndex <= step.length) {
        setDisplayedText(step.slice(0, charIndex));
        charIndex++;
      } else {
        clearInterval(typeInterval);
        
        // Move to next step after delay
        setTimeout(() => {
          if (currentStep < steps.length - 1) {
            setCurrentStep(prev => prev + 1);
          }
        }, 400);
      }
    }, 30);

    return () => clearInterval(typeInterval);
  }, [isVisible, currentStep, steps]);

  if (!isVisible) return null;

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 mb-3 font-mono text-xs">
      <div className="flex items-center gap-2 text-zinc-500 mb-2">
        <Terminal className="w-3 h-3" />
        <span>AGENT REASONING</span>
      </div>
      <div className="space-y-1">
        {steps.slice(0, currentStep).map((step, i) => (
          <div key={i} className="text-green-500/70">
            ✓ {step}
          </div>
        ))}
        {currentStep < steps.length && (
          <div className="text-cyan-400">
            → {displayedText}<span className="animate-pulse">▊</span>
          </div>
        )}
      </div>
    </div>
  );
}