"""
FastAPI Backend for Mahavihara

Endpoints:
    POST /start-session     - Start new tutoring session
    POST /chat              - Send message, get agent response
    GET  /graph-state/{id}  - Get current graph visualization
    GET  /session/{id}      - Get full session state
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

from agent import TutorAgent
from redis_store import RedisStore
from knowledge_graph import KnowledgeGraph

# ==================== Initialize ====================

app = FastAPI(
    title="Mahavihara API",
    description="Agentic AI Tutor for Linear Algebra",
    version="1.0.0"
)

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
agent = TutorAgent()
store = RedisStore()
kg = KnowledgeGraph()

# ==================== Request/Response Models ====================

class StartSessionRequest(BaseModel):
    session_id: Optional[str] = None  # Auto-generate if not provided

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    messages: list
    phase: str
    mastery: dict
    root_cause: Optional[str] = None

class GraphNode(BaseModel):
    id: str
    label: str
    color: str
    status: str  # "mastered", "failed", "neutral"

class GraphEdge(BaseModel):
    source: str
    target: str

class GraphStateResponse(BaseModel):
    nodes: list
    edges: list

# ==================== Helper Functions ====================

def mastery_to_status(score: float) -> str:
    """Convert mastery score to status string for frontend."""
    if score >= 0.6:
        return "mastered"
    elif score < 0.4:
        return "failed"
    return "neutral"

# ==================== Endpoints ====================

@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Mahavihara API is running"}


@app.post("/start-session")
def start_session(request: StartSessionRequest):
    """
    Start a new tutoring session.
    
    Returns the first diagnostic question.
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())[:8]
    
    # Delete any existing session data (fresh start)
    store.delete_session(session_id)
    
    # Start the session
    result = agent.start_session(session_id)
    
    return {
        "session_id": session_id,
        "messages": result["messages"],
        "phase": result["phase"],
        "mastery": result["mastery"]
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Process a chat message and return agent response.
    
    Handles all phases: diagnostic answers, teaching dialogue, verification.
    """
    session = store.get_session(request.session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Start a new session first.")
    
    # Process the message through the agent
    result = agent.process_message(request.session_id, request.message)
    
    return ChatResponse(
        messages=result["messages"],
        phase=result["phase"],
        mastery=result["mastery"],
        root_cause=result.get("root_cause")
    )


@app.get("/graph-state/{session_id}", response_model=GraphStateResponse)
def get_graph_state(session_id: str):
    """
    Get the current knowledge graph visualization state.
    
    Returns nodes with colors based on mastery scores.
    Frontend polls this endpoint to update the graph in real-time.
    """
    session = store.get_session(session_id)
    
    if not session:
        # Return default state for new sessions
        mastery = {c: 0.5 for c in store.CONCEPTS}
    else:
        mastery = session["mastery"]
    
    # Get visualization data from knowledge graph
    viz = kg.get_graph_visualization(mastery)
    
    # Add status field for frontend animations
    nodes = []
    for node in viz["nodes"]:
        score = mastery.get(node["id"], 0.5)
        nodes.append({
            "id": node["id"],
            "label": node["label"],
            "color": node["color"],
            "status": mastery_to_status(score)
        })
    
    return GraphStateResponse(
        nodes=nodes,
        edges=viz["edges"]
    )


@app.get("/session/{session_id}")
def get_session(session_id: str):
    """
    Get full session state (for debugging/admin).
    """
    session = store.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "state": session["state"],
        "mastery": session["mastery"],
        "answers": store.get_answers(session_id)
    }


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    """
    Delete a session (reset).
    """
    store.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)