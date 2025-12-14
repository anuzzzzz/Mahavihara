// lib/api.ts
const API_URL = "http://localhost:8000";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface GraphNode {
  id: string;
  label: string;
  color: string;
  status: "mastered" | "failed" | "neutral";
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface SessionResponse {
  session_id: string;
  messages: Message[];
  phase: string;
  mastery: Record<string, number>;
}

export interface ChatResponse {
  messages: Message[];
  phase: string;
  mastery: Record<string, number>;
  root_cause?: string;
}

export interface GraphStateResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export async function startSession(sessionId?: string): Promise<SessionResponse> {
  const res = await fetch(`${API_URL}/start-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error("Failed to start session");
  return res.json();
}

export async function sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) throw new Error("Failed to send message");
  return res.json();
}

export async function getGraphState(sessionId: string): Promise<GraphStateResponse> {
  const res = await fetch(`${API_URL}/graph-state/${sessionId}`);
  if (!res.ok) throw new Error("Failed to get graph state");
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${API_URL}/session/${sessionId}`, {
    method: "DELETE",
  });
}