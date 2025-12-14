
"use client";

import React from "react";
import { BookOpen, Lock, Sparkles } from "lucide-react";

const subjects = [
  { name: "Linear Algebra", status: "active", icon: Sparkles },
  { name: "Calculus", status: "locked", icon: Lock },
  { name: "Probability", status: "locked", icon: Lock },
  { name: "Quantum Physics", status: "locked", icon: Lock },
  { name: "Organic Chemistry", status: "locked", icon: Lock },
];

export default function Sidebar() {
  return (
    <div className="w-56 h-full bg-zinc-900/50 border-r border-zinc-800 flex flex-col">
      {/* Logo */}
      <div className="p-4 border-b border-zinc-800">
        <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent">
          MAHAVIHARA
        </h1>
        <p className="text-[10px] text-zinc-500 mt-1">AI-POWERED LEARNING</p>
      </div>

      {/* Subjects */}
      <div className="flex-1 p-3">
        <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-3 px-2">
          Subjects
        </p>
        <div className="space-y-1">
          {subjects.map((subject) => (
            <div
              key={subject.name}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all cursor-pointer ${
                subject.status === "active"
                  ? "bg-cyan-500/10 border border-cyan-500/30 text-cyan-400"
                  : "text-zinc-500 hover:bg-zinc-800/50"
              }`}
            >
              <subject.icon className="w-4 h-4" />
              <span className="text-sm">{subject.name}</span>
              {subject.status === "locked" && (
                <span className="text-[9px] ml-auto bg-zinc-800 px-1.5 py-0.5 rounded">
                  SOON
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-800">
        <div className="text-[10px] text-zinc-600 text-center">
          Built for AI Agents Hackathon
        </div>
      </div>
    </div>
  );
}