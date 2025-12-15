// lib/api.ts
// Updated to handle new response format with inline prescription and gap analysis

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

// ==================== Gap Analysis Types ====================

export interface Misconception {
  id: string;
  name: string;
  description: string;
  severity: string;
  explanation?: string;
  remediation_focus?: string;
}

export interface WrongAnswer {
  question_id: string;
  user_answer: string;
  correct_answer: string;
  misconception?: Misconception;
}

export interface GapAnalysis {
  total_questions: number;
  correct_count: number;
  wrong_answers: WrongAnswer[];
  primary_weakness?: string;
  misconceptions: Misconception[];
  most_critical?: {
    name: string;
    description: string;
    explanation: string;
    remediation: string;
  };
}

// ==================== Prescription Types ====================

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
  duration?: string;
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

// ==================== Session Response Types ====================

export interface SessionResponse {
  session_id: string;
  messages: Message[];
  phase: string;
  mastery: Record<string, number>;
  current_concept?: string;
}

// NEW: Enhanced chat response with inline prescription
export interface ChatResponse {
  messages: Message[];
  phase: string;
  mastery: Record<string, number>;
  current_concept?: string;
  root_cause?: string;
  // NEW FIELDS - prescription data inline!
  gap_analysis?: GapAnalysis | null;
  prescription?: PrescriptionData | null;
  resources?: PrescriptionResource[] | null;
  show_prescription_card: boolean;
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

export interface ResourcesResponse {
  concept_id: string;
  resources: PrescriptionResource[];
  formatted: string;
  tavily_enabled: boolean;
}

// ==================== API Functions ====================

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

export async function getResources(conceptId: string, limit: number = 5): Promise<ResourcesResponse> {
  const res = await fetch(`${API_URL}/resources/${conceptId}?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to get resources");
  return res.json();
}

// Health check - also shows if Tavily is enabled
export async function checkHealth(): Promise<{
  status: string;
  version: string;
  features: {
    misconception_detection: boolean;
    prescription_engine: boolean;
    tavily_search: boolean;
    socratic_tutor: boolean;
  };
}> {
  const res = await fetch(`${API_URL}/`);
  if (!res.ok) throw new Error("API not available");
  return res.json();
}