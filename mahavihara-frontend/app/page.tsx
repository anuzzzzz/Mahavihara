// app/page.tsx
// Updated to pass quiz state flags to ChatInterface
"use client";

import React, { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import Confetti from "react-confetti";
import ChatInterface from "@/components/ChatInterface";
import Sidebar from "@/components/Sidebar";
import PrescriptionCard from "@/components/PrescriptionCard";
import {
  startSession,
  sendMessage,
  getGraphState,
  deleteSession,
  Message,
  GraphNode,
  GraphEdge,
  PrescriptionData,
} from "@/lib/api";

const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center bg-zinc-900">
      <p className="text-zinc-500 font-mono">Loading graph...</p>
    </div>
  ),
});

const CONCEPT_ORDER = ["vectors", "matrix_ops", "determinants", "inverse_matrix", "eigenvalues"];

export default function Home() {
  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [phase, setPhase] = useState<string>("lesson");
  const [mastery, setMastery] = useState<Record<string, number>>({});
  const [currentConceptIndex, setCurrentConceptIndex] = useState(0);
  
  // NEW: Quiz state flags from backend
  const [quizPassed, setQuizPassed] = useState<boolean | null>(null);
  const [canAdvance, setCanAdvance] = useState<boolean>(false);
  const [nextConcept, setNextConcept] = useState<string | null>(null);
  
  // Graph state
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  
  // Prescription state
  const [prescription, setPrescription] = useState<PrescriptionData | null>(null);
  const [showPrescription, setShowPrescription] = useState(false);
  const [currentPrescriptionPhase, setCurrentPrescriptionPhase] = useState(1);
  const [completedPrescriptionPhases, setCompletedPrescriptionPhases] = useState<number[]>([]);

  const currentConcept = CONCEPT_ORDER[currentConceptIndex] || "vectors";

  // Initialize session
  const initSession = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await startSession();
      setSessionId(response.session_id);
      setMessages(response.messages);
      setPhase(response.phase);
      setMastery(response.mastery);
      setQuizPassed(response.quiz_passed ?? null);
      setCanAdvance(response.can_advance ?? false);

      const graphState = await getGraphState(response.session_id);
      setGraphNodes(graphState.nodes);
      setGraphEdges(graphState.edges);
    } catch (error) {
      console.error("Failed to start session:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    initSession();
  }, [initSession]);

  // Poll graph state
  useEffect(() => {
    if (!sessionId) return;

    const interval = setInterval(async () => {
      try {
        const graphState = await getGraphState(sessionId);
        setGraphNodes(graphState.nodes);
        setGraphEdges(graphState.edges);
      } catch (error) {
        console.error("Failed to get graph state:", error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [sessionId]);

  // Handle sending messages
  const handleSendMessage = async (message: string) => {
    if (!sessionId) return;

    // Hide prescription when user starts new quiz
    if (showPrescription && message.toLowerCase().includes("quiz")) {
      setShowPrescription(false);
    }

    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);

    try {
      const response = await sendMessage(sessionId, message);

      setMessages((prev) => [...prev, ...response.messages]);
      setPhase(response.phase);

      // Update quiz state flags from backend
      setQuizPassed(response.quiz_passed);
      setCanAdvance(response.can_advance);
      setNextConcept(response.next_concept);

      // Check for mastery celebration
      const prevMastery = mastery;
      const newMastery = response.mastery;
      Object.keys(newMastery).forEach((concept) => {
        if ((prevMastery[concept] || 0) < 0.6 && newMastery[concept] >= 0.6) {
          setShowConfetti(true);
          setShowPrescription(false);
          setPrescription(null);
          setTimeout(() => setShowConfetti(false), 5000);
        }
      });

      setMastery(response.mastery);

      // Update current concept
      if (response.current_concept) {
        const newIndex = CONCEPT_ORDER.indexOf(response.current_concept);
        if (newIndex !== -1) {
          setCurrentConceptIndex(newIndex);
        }
      }

      // Show prescription card if backend says so
      if (response.show_prescription_card && response.prescription) {
        setPrescription(response.prescription);
        setShowPrescription(true);
        setCurrentPrescriptionPhase(1);
        setCompletedPrescriptionPhases([]);
      }

      // Update graph
      const graphState = await getGraphState(sessionId);
      setGraphNodes(graphState.nodes);
      setGraphEdges(graphState.edges);
    } catch (error) {
      console.error("Failed to send message:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: Failed to get response." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Prescription handlers
  const handleStartPrescriptionPhase = (phase: number) => {
    setCurrentPrescriptionPhase(phase);
    const newCompleted = Array.from({ length: phase - 1 }, (_, i) => i + 1)
      .filter(p => !completedPrescriptionPhases.includes(p));
    setCompletedPrescriptionPhases([...completedPrescriptionPhases, ...newCompleted]);
  };

  const handlePrescriptionComplete = () => {
    if (prescription) {
      const allPhases = prescription.prescription.phases.map((_, i) => i + 1);
      setCompletedPrescriptionPhases(allPhases);
    }
    handleSendMessage("quiz me");
    setShowPrescription(false);
  };

  const handleClosePrescription = () => {
    setShowPrescription(false);
  };

  // Reset session
  const handleReset = async () => {
    if (sessionId) {
      await deleteSession(sessionId);
    }

    setSessionId(null);
    setMessages([]);
    setPhase("lesson");
    setMastery({});
    setGraphNodes([]);
    setGraphEdges([]);
    setPrescription(null);
    setShowPrescription(false);
    setCurrentConceptIndex(0);
    setCompletedPrescriptionPhases([]);
    setQuizPassed(null);
    setCanAdvance(false);
    setNextConcept(null);

    initSession();
  };

  // Calculate overall mastery
  const overallMastery = Object.values(mastery).length > 0
    ? Math.round((Object.values(mastery).reduce((a, b) => a + b, 0) / Object.values(mastery).length) * 100)
    : 50;

  return (
    <main className="h-screen w-screen bg-[#0A0A0A] text-white flex overflow-hidden">
      {showConfetti && <Confetti numberOfPieces={200} recycle={false} />}

      <Sidebar />

      {/* Chat Panel */}
      <div className="w-[35%] h-full p-4 relative">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          onReset={handleReset}
          isLoading={isLoading}
          phase={phase}
          mastery={mastery}
          quizPassed={quizPassed}
          canAdvance={canAdvance}
          nextConcept={nextConcept}
        />
        
        {/* Prescription Card Overlay */}
        {showPrescription && prescription && (
          <div className="absolute inset-0 z-50 p-4 bg-black/80 backdrop-blur-sm overflow-auto">
            <div className="relative">
              <button
                onClick={handleClosePrescription}
                className="absolute -top-2 -right-2 z-10 w-8 h-8 bg-zinc-800 hover:bg-zinc-700 
                           rounded-full flex items-center justify-center text-zinc-400 hover:text-white
                           transition-colors border border-zinc-700"
              >
                ✕
              </button>
              
              <PrescriptionCard
                prescription={{
                  diagnosis: prescription.diagnosis,
                  phases: prescription.prescription?.phases || [],
                  resources: prescription.resources?.items || [],
                  verification: {
                    question_ids: prescription.verification?.question_ids || [],
                    success_criteria: prescription.verification?.success_criteria || "Pass 2/3 questions",
                  },
                  estimated_time: prescription.prescription?.total_time || "10 minutes",
                }}
                onStartPhase={handleStartPrescriptionPhase}
                onComplete={handlePrescriptionComplete}
                currentPhase={currentPrescriptionPhase}
                completedPhases={completedPrescriptionPhases}
              />
            </div>
          </div>
        )}
      </div>

      {/* Knowledge Graph Panel */}
      <div className="flex-1 h-full p-4">
        <div className="h-full rounded-xl border border-cyan-500/30 overflow-hidden bg-zinc-900/30 shadow-[0_0_30px_rgba(0,255,255,0.1)]">
          <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
            <h2 className="text-sm font-mono text-cyan-400 drop-shadow-[0_0_10px_rgba(0,255,255,0.5)]">
              KNOWLEDGE GRAPH
            </h2>
            <div className="flex items-center gap-4">
              {prescription && !showPrescription && (
                <button
                  onClick={() => setShowPrescription(true)}
                  className="text-xs bg-amber-500/20 text-amber-400 px-3 py-1 rounded-full
                             border border-amber-500/30 hover:bg-amber-500/30 transition-colors
                             animate-pulse"
                >
                  📋 View Prescription
                </button>
              )}
              
              <div className="text-xs font-mono text-zinc-500">
                Mastery: <span className={overallMastery >= 60 ? "text-green-400" : "text-amber-400"}>
                  {overallMastery}%
                </span>
              </div>
              
              <div className="flex items-center gap-2 text-[10px]">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.8)]"></span>
                  Mastered
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.8)]"></span>
                  Weak
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-zinc-500"></span>
                  Neutral
                </span>
              </div>
            </div>
          </div>
          
          <div className="h-[calc(100%-48px)]">
            <KnowledgeGraph nodes={graphNodes} edges={graphEdges} />
          </div>
        </div>
      </div>
    </main>
  );
}