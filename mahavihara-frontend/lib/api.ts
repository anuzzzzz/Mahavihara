// lib/api.ts
// Updated with new response fields for proper button logic

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

export interface PrescriptionPhase {
  phase: number;
  action: string;
  title: string;
  url: string | null;
  source: string;
  duration: string;
  instruction?: string;
  icon: string;
}

export interface PrescriptionResource {
  type: string;
  title: string;
  url: string;
  source: string;
  why: string;
  timestamp?: string;
}

export interface Diagnosis {
  title?: string;
  failed_concept: string;
  root_cause: string;
  misconception: string | null;
  explanation: string | null;
  confidence: number;
}

export interface PrescriptionData {
  diagnosis: Diagnosis;
  prescription: {
    title: string;
    phases: PrescriptionPhase[];
    total_time: string;
  };
  resources: {
    title: string;
    items: PrescriptionResource[];
  };
  verification: {
    title: string;
    criteria: string;
    question_ids: string[];
    success_criteria: string;
  };
  formatted?: string;
}

export interface SessionResponse {
  session_id: string;
  messages: Message[];
  phase: string;
  mastery: Record<string, number>;
  current_concept?: string;
  quiz_passed?: boolean | null;
  can_advance?: boolean;
}

// NEW: Enhanced chat response with explicit state flags
export interface ChatResponse {
  messages: Message[];
  phase: string;
  mastery: Record<string, number>;
  current_concept?: string;
  // NEW: Explicit state flags
  quiz_passed: boolean | null;  // true = passed, false = failed, null = not in evaluate
  can_advance: boolean;         // true = user can click Continue
  next_concept: string | null;  // name of next concept
  // Prescription
  show_prescription_card: boolean;
  prescription: PrescriptionData | null;
}

export interface GraphStateResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface VerifyRequest {
  session_id: string;
  concept_id: string;
  quiz_results: Array<{
    question_id: string;
    user_answer: string;
    correct_answer: string;
    is_correct: boolean;
  }>;
}

export interface VerifyResponse {
  passed: boolean;
  score: string;
  misconception_fixed: boolean;
  next_action: string;
  new_mastery: number;
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

export async function getPrescription(
  sessionId: string,
  conceptId: string
): Promise<PrescriptionData> {
  const res = await fetch(`${API_URL}/prescription/${sessionId}/${conceptId}`);
  if (!res.ok) throw new Error("Failed to get prescription");
  return res.json();
}

export async function verifyMastery(request: VerifyRequest): Promise<VerifyResponse> {
  const res = await fetch(`${API_URL}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error("Failed to verify mastery");
  return res.json();
}

export async function getResources(conceptId: string, limit: number = 5) {
  const res = await fetch(`${API_URL}/resources/${conceptId}?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to get resources");
  return res.json();
}