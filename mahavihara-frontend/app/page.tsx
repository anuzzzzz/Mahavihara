// app/page.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import ChatInterface from "@/components/ChatInterface";
import Sidebar from "@/components/Sidebar";
import {
  startSession,
  sendMessage,
  getGraphState,
  deleteSession,
  Message,
  GraphNode,
  GraphEdge,
} from "@/lib/api";

const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center bg-zinc-900">
      <p className="text-zinc-500 font-mono">Loading graph...</p>
    </div>
  ),
});

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [phase, setPhase] = useState<string>("diagnostic");
  const [mastery, setMastery] = useState<Record<string, number>>({});
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [rootCause, setRootCause] = useState<string | undefined>();

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

  const handleSendMessage = async (message: string) => {
    if (!sessionId) return;

    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsLoading(true);

    try {
      const response = await sendMessage(sessionId, message);

      setMessages((prev) => [...prev, ...response.messages]);
      setPhase(response.phase);
      setMastery(response.mastery);
      if (response.root_cause) {
        setRootCause(response.root_cause);
      }

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

  const handleReset = async () => {
    // Delete old session from Redis first
    if (sessionId) {
      await deleteSession(sessionId);
    }

    // Clear local state
    setSessionId(null);
    setMessages([]);
    setPhase("diagnostic");
    setMastery({});
    setGraphNodes([]);
    setGraphEdges([]);
    setRootCause(undefined);

    // Start fresh
    initSession();
  };

  return (
    <main className="h-screen w-screen bg-[#0A0A0A] text-white flex overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Chat Panel (35%) */}
      <div className="w-[35%] h-full p-4">
        <ChatInterface
          messages={messages}
          onSendMessage={handleSendMessage}
          onReset={handleReset}
          isLoading={isLoading}
          phase={phase}
          mastery={mastery}
          rootCause={rootCause}
        />
      </div>

      {/* Knowledge Graph Panel (remaining) */}
      <div className="flex-1 h-full p-4">
        <div className="h-full rounded-xl border border-cyan-500/30 overflow-hidden bg-zinc-900/30 shadow-[0_0_30px_rgba(0,255,255,0.1)]">
          <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
            <h2 className="text-sm font-mono text-cyan-400 drop-shadow-[0_0_10px_rgba(0,255,255,0.5)]">
              KNOWLEDGE GRAPH
            </h2>
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
          <div className="h-[calc(100%-48px)]">
            <KnowledgeGraph nodes={graphNodes} edges={graphEdges} />
          </div>
        </div>
      </div>
    </main>
  );
}