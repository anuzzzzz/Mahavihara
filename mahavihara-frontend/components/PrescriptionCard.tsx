// components/PrescriptionCard.tsx
// The "Doctor's Prescription" UI - This is the demo centerpiece

"use client";

import React, { useState } from "react";
import {
  Play,
  BookOpen,
  Beaker,
  PenTool,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  AlertTriangle,
  Brain,
  Clock,
  Target,
  Sparkles
} from "lucide-react";

interface PrescriptionPhase {
  phase: number;
  action: string;
  title: string;
  url: string | null;
  source: string;
  duration: string;
  instruction?: string;
  icon: string;
}

interface PrescriptionResource {
  type: string;
  title: string;
  url: string;
  source: string;
  why: string;
  timestamp?: string;
}

interface Diagnosis {
  failed_concept: string;
  root_cause: string;
  misconception: string | null;
  explanation: string | null;
  confidence: number;
}

interface PrescriptionData {
  diagnosis: Diagnosis;
  phases: PrescriptionPhase[];
  resources: PrescriptionResource[];
  verification: {
    question_ids: string[];
    success_criteria: string;
  };
  estimated_time: string;
}

interface PrescriptionCardProps {
  prescription: PrescriptionData;
  onStartPhase: (phase: number) => void;
  onComplete: () => void;
  currentPhase: number;
  completedPhases: number[];
}

// Icon mapping
const getPhaseIcon = (icon: string) => {
  const iconMap: Record<string, React.ReactNode> = {
    "🎬": <Play className="w-5 h-5" />,
    "📖": <BookOpen className="w-5 h-5" />,
    "🔬": <Beaker className="w-5 h-5" />,
    "✏️": <PenTool className="w-5 h-5" />,
    "✅": <CheckCircle2 className="w-5 h-5" />,
    "🤖": <Brain className="w-5 h-5" />,
  };
  return iconMap[icon] || <ChevronRight className="w-5 h-5" />;
};

// Source badge colors
const getSourceColor = (source: string): string => {
  const colors: Record<string, string> = {
    "3blue1brown": "bg-blue-500/20 text-blue-400 border-blue-500/30",
    "khan_academy": "bg-green-500/20 text-green-400 border-green-500/30",
    "setosa": "bg-purple-500/20 text-purple-400 border-purple-500/30",
    "desmos": "bg-orange-500/20 text-orange-400 border-orange-500/30",
    "mahavihara": "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
    "youtube": "bg-red-500/20 text-red-400 border-red-500/30",
  };
  return colors[source.toLowerCase()] || "bg-zinc-500/20 text-zinc-400 border-zinc-500/30";
};

export default function PrescriptionCard({
  prescription,
  onStartPhase,
  onComplete,
  currentPhase,
  completedPhases
}: PrescriptionCardProps) {
  const [expandedSection, setExpandedSection] = useState<"diagnosis" | "treatment" | "resources" | null>("diagnosis");

  const { diagnosis, phases, resources, verification, estimated_time } = prescription;

  return (
    <div className="bg-gradient-to-br from-zinc-900 to-zinc-950 rounded-2xl border border-cyan-500/30 overflow-hidden shadow-[0_0_40px_rgba(0,255,255,0.1)]">

      {/* Header */}
      <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Sparkles className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Your Learning Prescription</h2>
              <p className="text-xs text-zinc-400">Personalized path to mastery</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Clock className="w-4 h-4 text-zinc-400" />
            <span className="text-zinc-300">{estimated_time}</span>
          </div>
        </div>
      </div>

      {/* Diagnosis Section */}
      <div className="border-b border-zinc-800">
        <button
          onClick={() => setExpandedSection(expandedSection === "diagnosis" ? null : "diagnosis")}
          className="w-full p-4 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <span className="font-semibold text-white">Diagnosis</span>
          </div>
          <ChevronRight className={`w-5 h-5 text-zinc-400 transition-transform ${expandedSection === "diagnosis" ? "rotate-90" : ""}`} />
        </button>

        {expandedSection === "diagnosis" && (
          <div className="px-4 pb-4 space-y-3">
            {/* Root Cause */}
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 text-xs text-zinc-500 uppercase tracking-wider mb-1">
                <Target className="w-3 h-3" />
                Root Cause
              </div>
              <p className="text-zinc-200">
                Your struggle with <span className="text-red-400 font-semibold">{diagnosis.failed_concept}</span> traces back to gaps in <span className="text-amber-400 font-semibold">{diagnosis.root_cause}</span>
              </p>
            </div>

            {/* Misconception */}
            {diagnosis.misconception && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                <div className="flex items-center gap-2 text-xs text-red-400 uppercase tracking-wider mb-1">
                  <Brain className="w-3 h-3" />
                  Detected Misconception
                </div>
                <p className="text-zinc-200 font-medium">{diagnosis.misconception}</p>
                {diagnosis.explanation && (
                  <p className="text-zinc-400 text-sm mt-1">{diagnosis.explanation}</p>
                )}
              </div>
            )}

            {/* Confidence */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-500">Diagnosis Confidence:</span>
              <div className="flex-1 h-2 bg-zinc-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-purple-500 transition-all duration-1000"
                  style={{ width: `${diagnosis.confidence * 100}%` }}
                />
              </div>
              <span className="text-sm text-zinc-300">{Math.round(diagnosis.confidence * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Treatment Plan */}
      <div className="border-b border-zinc-800">
        <button
          onClick={() => setExpandedSection(expandedSection === "treatment" ? null : "treatment")}
          className="w-full p-4 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <Play className="w-5 h-5 text-green-400" />
            <span className="font-semibold text-white">Treatment Plan</span>
            <span className="text-xs text-zinc-500">({phases.length} phases)</span>
          </div>
          <ChevronRight className={`w-5 h-5 text-zinc-400 transition-transform ${expandedSection === "treatment" ? "rotate-90" : ""}`} />
        </button>

        {expandedSection === "treatment" && (
          <div className="px-4 pb-4 space-y-2">
            {phases.map((phase, index) => {
              const isCompleted = completedPhases.includes(phase.phase);
              const isCurrent = currentPhase === phase.phase;
              const isLocked = phase.phase > currentPhase && !isCompleted;

              return (
                <div
                  key={phase.phase}
                  className={`
                    relative rounded-xl border transition-all duration-300
                    ${isCurrent ? "bg-cyan-500/10 border-cyan-500/50 shadow-[0_0_20px_rgba(0,255,255,0.2)]" : ""}
                    ${isCompleted ? "bg-green-500/10 border-green-500/30" : ""}
                    ${isLocked ? "bg-zinc-800/30 border-zinc-700 opacity-60" : ""}
                    ${!isCurrent && !isCompleted && !isLocked ? "bg-zinc-800/50 border-zinc-700 hover:border-zinc-600" : ""}
                  `}
                >
                  <button
                    onClick={() => !isLocked && onStartPhase(phase.phase)}
                    disabled={isLocked}
                    className="w-full p-4 text-left"
                  >
                    <div className="flex items-start gap-4">
                      {/* Phase Number/Status */}
                      <div className={`
                        w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0
                        ${isCompleted ? "bg-green-500/20 text-green-400" : ""}
                        ${isCurrent ? "bg-cyan-500/20 text-cyan-400" : ""}
                        ${isLocked ? "bg-zinc-700 text-zinc-500" : ""}
                        ${!isCurrent && !isCompleted && !isLocked ? "bg-zinc-700 text-zinc-400" : ""}
                      `}>
                        {isCompleted ? (
                          <CheckCircle2 className="w-5 h-5" />
                        ) : (
                          getPhaseIcon(phase.icon)
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`font-semibold ${isCurrent ? "text-cyan-400" : isCompleted ? "text-green-400" : "text-zinc-200"}`}>
                            {phase.action}
                          </span>
                          <span className="text-xs text-zinc-500">{phase.duration}</span>
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${getSourceColor(phase.source)}`}>
                            {phase.source}
                          </span>
                        </div>

                        <p className="text-sm text-zinc-400 truncate">{phase.title}</p>

                        {phase.instruction && isCurrent && (
                          <p className="text-xs text-cyan-400/80 mt-2 flex items-center gap-1">
                            <Sparkles className="w-3 h-3" />
                            {phase.instruction}
                          </p>
                        )}

                        {phase.url && isCurrent && (
                          <a
                            href={phase.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 mt-2"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="w-3 h-3" />
                            Open Resource
                          </a>
                        )}
                      </div>

                      {/* Arrow */}
                      {!isLocked && !isCompleted && (
                        <ChevronRight className={`w-5 h-5 ${isCurrent ? "text-cyan-400" : "text-zinc-500"}`} />
                      )}
                    </div>
                  </button>

                  {/* Connector Line */}
                  {index < phases.length - 1 && (
                    <div className="absolute left-[2.25rem] top-full w-0.5 h-2 bg-zinc-700" />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Resources Section */}
      <div className="border-b border-zinc-800">
        <button
          onClick={() => setExpandedSection(expandedSection === "resources" ? null : "resources")}
          className="w-full p-4 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <BookOpen className="w-5 h-5 text-purple-400" />
            <span className="font-semibold text-white">Curated Resources</span>
            <span className="text-xs text-zinc-500">({resources.length})</span>
          </div>
          <ChevronRight className={`w-5 h-5 text-zinc-400 transition-transform ${expandedSection === "resources" ? "rotate-90" : ""}`} />
        </button>

        {expandedSection === "resources" && (
          <div className="px-4 pb-4 space-y-2">
            {resources.map((resource, index) => (
              <a
                key={index}
                href={resource.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-zinc-800/50 hover:bg-zinc-800 rounded-lg p-3 transition-colors group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${getSourceColor(resource.source)}`}>
                        {resource.type}
                      </span>
                      <span className="text-xs text-zinc-500">{resource.source}</span>
                      {resource.timestamp && (
                        <span className="text-xs text-amber-400">@{resource.timestamp}</span>
                      )}
                    </div>
                    <p className="text-sm text-zinc-200 group-hover:text-cyan-400 transition-colors truncate">
                      {resource.title}
                    </p>
                    <p className="text-xs text-zinc-500 mt-1">{resource.why}</p>
                  </div>
                  <ExternalLink className="w-4 h-4 text-zinc-500 group-hover:text-cyan-400 transition-colors flex-shrink-0" />
                </div>
              </a>
            ))}
          </div>
        )}
      </div>

      {/* Verification Footer */}
      <div className="p-4 bg-gradient-to-r from-green-500/10 to-cyan-500/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            <div>
              <p className="text-sm font-medium text-zinc-200">Verification</p>
              <p className="text-xs text-zinc-400">{verification.success_criteria}</p>
            </div>
          </div>
          <button
            onClick={onComplete}
            disabled={completedPhases.length < phases.length - 1}
            className={`
              px-4 py-2 rounded-lg font-medium text-sm transition-all
              ${completedPhases.length >= phases.length - 1
                ? "bg-green-500 hover:bg-green-600 text-white shadow-[0_0_20px_rgba(34,197,94,0.3)]"
                : "bg-zinc-700 text-zinc-400 cursor-not-allowed"
              }
            `}
          >
            Take Verification Quiz
          </button>
        </div>
      </div>
    </div>
  );
}


// ==================== EXAMPLE USAGE ====================

export function PrescriptionCardDemo() {
  const [currentPhase, setCurrentPhase] = useState(1);
  const [completedPhases, setCompletedPhases] = useState<number[]>([]);

  const samplePrescription: PrescriptionData = {
    diagnosis: {
      failed_concept: "Eigenvalues",
      root_cause: "Determinants",
      misconception: "Eigenvector-Eigenvalue Swap",
      explanation: "You chose 'Eigenvector' when asked about λ. Remember: λ is the eigenVALUE (a number), v is the eigenVECTOR (a direction).",
      confidence: 0.85
    },
    phases: [
      {
        phase: 1,
        action: "Watch",
        title: "3Blue1Brown - Eigenvectors and Eigenvalues",
        url: "https://youtube.com/watch?v=PFDu9oVAE-g",
        source: "3blue1brown",
        duration: "5 min",
        instruction: "Focus on why eigenvectors 'stay on their span'",
        icon: "🎬"
      },
      {
        phase: 2,
        action: "Experiment",
        title: "Eigenvector Visualization Tool",
        url: "https://setosa.io/ev/eigenvectors-and-eigenvalues/",
        source: "setosa",
        duration: "3 min",
        instruction: "Drag vectors and watch which ones stay on their line",
        icon: "🔬"
      },
      {
        phase: 3,
        action: "Practice",
        title: "Targeted Eigenvalue Problems",
        url: null,
        source: "mahavihara",
        duration: "5 min",
        instruction: "3 problems testing eigenvalue vs eigenvector distinction",
        icon: "✏️"
      },
      {
        phase: 4,
        action: "Prove It",
        title: "Verification Quiz",
        url: null,
        source: "mahavihara",
        duration: "2 min",
        instruction: "2/3 correct to pass",
        icon: "✅"
      }
    ],
    resources: [
      {
        type: "video",
        title: "Eigenvectors and eigenvalues | Essence of linear algebra",
        url: "https://youtube.com/watch?v=PFDu9oVAE-g",
        source: "3blue1brown",
        why: "Best visual intuition - eigenvectors as directions that stay on their span",
        timestamp: "0:00"
      },
      {
        type: "interactive",
        title: "Eigenvectors and Eigenvalues Explained Visually",
        url: "https://setosa.io/ev/eigenvectors-and-eigenvalues/",
        source: "setosa",
        why: "Drag vectors to see eigenvalue scaling in real-time"
      }
    ],
    verification: {
      question_ids: ["eig_1", "eig_2", "eig_3"],
      success_criteria: "Answer 2/3 eigenvalue questions correctly"
    },
    estimated_time: "15 minutes"
  };

  const handleStartPhase = (phase: number) => {
    setCurrentPhase(phase);
    // Simulate completing a phase after clicking
    if (!completedPhases.includes(phase)) {
      setTimeout(() => {
        setCompletedPhases([...completedPhases, phase]);
        if (phase < samplePrescription.phases.length) {
          setCurrentPhase(phase + 1);
        }
      }, 1000);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 p-8">
      <div className="max-w-xl mx-auto">
        <PrescriptionCard
          prescription={samplePrescription}
          currentPhase={currentPhase}
          completedPhases={completedPhases}
          onStartPhase={handleStartPhase}
          onComplete={() => alert("Starting verification quiz!")}
        />
      </div>
    </div>
  );
}
