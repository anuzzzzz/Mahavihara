// app/page.tsx
// Updated to use inline prescription from chat response
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
  GapAnalysis,
  PrescriptionResource,
} from "@/lib/api";

const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center bg-zinc-900">
      <p className="text-zinc-500 font-mono">Loading graph...</p>
    </div>
  ),
});

// Concept order for tracking
const CONCEPT_ORDER = ["vectors", "matrix_ops", "determinants", "inverse_matrix", "eigenvalues"];

export default function Home() {
  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [phase, setPhase] = useState<string>("lesson");
  const [mastery, setMastery] = useState<Record<string, number>>({});
  const [currentConceptIndex, setCurrentConceptIndex] = useState(0);
  
  // Graph state
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [rootCause, setRootCause] = useState<string | undefined>();
  const [showConfetti, setShowConfetti] = useState(false);
  
  // Prescription state - NOW COMES FROM CHAT RESPONSE!
  const [prescription, setPrescription] = useState<PrescriptionData | null>(null);
  const [showPrescription, setShowPrescription] = useState(false);
  const [currentPrescriptionPhase, setCurrentPrescriptionPhase] = useState(1);
  const [completedPrescriptionPhases, setCompletedPrescriptionPhases] = useState<number[]>([]);
  
  // Gap analysis state - NEW!
  const [gapAnalysis, setGapAnalysis] = useState<GapAnalysis | null>(null);
  const [resources, setResources] = useState<PrescriptionResource[] | null>(null);

  // Get current concept ID
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

      // Check if any concept just crossed 0.6 threshold (mastered!)
      const prevMastery = mastery;
      const newMastery = response.mastery;
      Object.keys(newMastery).forEach((concept) => {
        if ((prevMastery[concept] || 0) < 0.6 && newMastery[concept] >= 0.6) {
          setShowConfetti(true);
          setShowPrescription(false); // Hide prescription on success
          setPrescription(null);
          setGapAnalysis(null);
          setTimeout(() => setShowConfetti(false), 5000);
        }
      });

      setMastery(response.mastery);
      
      if (response.root_cause) {
        setRootCause(response.root_cause);
      }

      // Update current concept if provided
      if (response.current_concept) {
        const newIndex = CONCEPT_ORDER.indexOf(response.current_concept);
        if (newIndex !== -1) {
          setCurrentConceptIndex(newIndex);
        }
      }

      // ==================== NEW: Handle inline prescription data ====================
      
      // Update gap analysis if provided
      if (response.gap_analysis) {
        setGapAnalysis(response.gap_analysis);
      }
      
      // Update resources if provided
      if (response.resources) {
        setResources(response.resources);
      }
      
      // Show prescription card if backend says so!
      if (response.show_prescription_card && response.prescription) {
        console.log("📋 Showing prescription card:", response.prescription);
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

  // Handle prescription phase progression
  const handleStartPrescriptionPhase = (phase: number) => {
    setCurrentPrescriptionPhase(phase);
    
    // Mark previous phases as completed
    const newCompleted = Array.from(
      { length: phase - 1 }, 
      (_, i) => i + 1
    ).filter(p => !completedPrescriptionPhases.includes(p));
    
    setCompletedPrescriptionPhases([...completedPrescriptionPhases, ...newCompleted]);
  };

  // Handle prescription completion (verification)
  const handlePrescriptionComplete = () => {
    // Mark all phases as completed
    if (prescription) {
      const allPhases = prescription.prescription.phases.map((_, i) => i + 1);
      setCompletedPrescriptionPhases(allPhases);
    }
    
    // Send "quiz me" to trigger verification quiz
    handleSendMessage("quiz me");
    setShowPrescription(false);
  };

  // Close prescription card
  const handleClosePrescription = () => {
    setShowPrescription(false);
  };

  // Reset session
  const handleReset = async () => {
    if (sessionId) {
      await deleteSession(sessionId);
    }

    // Clear all state
    setSessionId(null);
    setMessages([]);
    setPhase("lesson");
    setMastery({});
    setGraphNodes([]);
    setGraphEdges([]);
    setRootCause(undefined);
    setPrescription(null);
    setShowPrescription(false);
    setCurrentConceptIndex(0);
    setCompletedPrescriptionPhases([]);
    setGapAnalysis(null);
    setResources(null);

    // Start fresh
    initSession();
  };

  // Calculate overall mastery
  const overallMastery = Object.values(mastery).length > 0
    ? Math.round((Object.values(mastery).reduce((a, b) => a + b, 0) / Object.values(mastery).length) * 100)
    : 50;

  return (
    <main className="h-screen w-screen bg-[#0A0A0A] text-white flex overflow-hidden">
      {showConfetti && <Confetti numberOfPieces={200} recycle={false} />}

      {/* Sidebar */}
      <Sidebar />

      {/* Chat Panel (35%) */}
      <div className="w-[35%] h-full p-4 relative">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          onReset={handleReset}
          isLoading={isLoading}
          phase={phase}
          mastery={mastery}
          rootCause={rootCause}
        />
        
        {/* Prescription Card Overlay - Shows on quiz failure */}
        {showPrescription && prescription && (
          <div className="absolute inset-0 z-50 p-4 bg-black/80 backdrop-blur-sm overflow-auto">
            <div className="relative">
              {/* Close button */}
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

      {/* Knowledge Graph Panel (remaining) */}
      <div className="flex-1 h-full p-4">
        <div className="h-full rounded-xl border border-cyan-500/30 overflow-hidden bg-zinc-900/30 shadow-[0_0_30px_rgba(0,255,255,0.1)]">
          <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
            <h2 className="text-sm font-mono text-cyan-400 drop-shadow-[0_0_10px_rgba(0,255,255,0.5)]">
              KNOWLEDGE GRAPH
            </h2>
            <div className="flex items-center gap-4">
              {/* Prescription indicator */}
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
              
              {/* Gap Analysis indicator */}
              {gapAnalysis && gapAnalysis.wrong_answers.length > 0 && !showPrescription && (
                <button
                  onClick={() => prescription && setShowPrescription(true)}
                  className="text-xs bg-red-500/20 text-red-400 px-3 py-1 rounded-full
                             border border-red-500/30 hover:bg-red-500/30 transition-colors"
                >
                  ⚠️ {gapAnalysis.wrong_answers.length} gaps found
                </button>
              )}
              
              {/* Overall mastery */}
              <div className="text-xs font-mono text-zinc-500">
                Mastery: <span className={overallMastery >= 60 ? "text-green-400" : "text-amber-400"}>
                  {overallMastery}%
                </span>
              </div>
              
              {/* Legend */}
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