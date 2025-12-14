"""
FastAPI Backend for Mahavihara - AI Tutoring Platform

"ChatGPT writes explanations. Mahavihara prescribes the perfect YouTube timestamp."

Endpoints:
    POST /start-session     - Start new tutoring session
    POST /chat              - Send message, get agent response
    POST /diagnose          - Diagnose learning gaps from quiz results
    GET  /prescription/{id} - Get learning prescription for concept
    POST /verify            - Verify mastery after studying
    GET  /graph-state/{id}  - Get current graph visualization
    GET  /session/{id}      - Get full session state
    GET  /resources/{id}    - Get learning resources for concept
    DELETE /session/{id}    - Delete session
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge_graph import KnowledgeGraph
from core.student_model import StudentModel
from core.adaptive_tester import AdaptiveTester
from core.misconception_detector import MisconceptionDetector, WrongAnswerAnalysis
from core.prescription_engine import PrescriptionEngine
from teaching.socratic_tutor import SocraticTutor, TutorContext
from teaching.resource_curator import ResourceCurator
from redis_store import RedisStore

# ==================== Initialize ====================

app = FastAPI(
    title="Mahavihara API",
    description="Adaptive AI Tutor for Linear Algebra - Prescription-based Learning",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize shared components
kg = KnowledgeGraph()
store = RedisStore()
misconception_detector = MisconceptionDetector()
resource_curator = ResourceCurator()
tutor = SocraticTutor()

# Session-specific components (created per session)
session_models: Dict[str, StudentModel] = {}
session_testers: Dict[str, AdaptiveTester] = {}


def get_or_create_model(session_id: str) -> StudentModel:
    """Get or create student model for session."""
    if session_id not in session_models:
        session_models[session_id] = StudentModel()
    return session_models[session_id]


def get_or_create_tester(session_id: str) -> AdaptiveTester:
    """Get or create adaptive tester for session."""
    if session_id not in session_testers:
        model = get_or_create_model(session_id)
        session_testers[session_id] = AdaptiveTester(kg, model)
    return session_testers[session_id]


# ==================== Request/Response Models ====================

class StartSessionRequest(BaseModel):
    session_id: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    messages: list
    phase: str
    mastery: dict
    root_cause: Optional[str] = None
    current_concept: Optional[str] = None


class DiagnoseRequest(BaseModel):
    session_id: str
    concept_id: str
    quiz_results: List[dict]  # [{question_id, user_answer, correct_answer, is_correct}]


class DiagnoseResponse(BaseModel):
    concept_id: str
    misconceptions: List[dict]
    root_cause: Optional[dict]
    severity: int
    needs_prescription: bool


class PrescriptionResponse(BaseModel):
    concept_id: str
    concept_name: str
    severity: int
    root_cause: Optional[dict]
    misconceptions: List[dict]
    phases: List[dict]
    total_estimated_minutes: int
    verification: dict
    formatted: str  # Markdown for display


class VerifyRequest(BaseModel):
    session_id: str
    concept_id: str
    quiz_results: List[dict]


class VerifyResponse(BaseModel):
    passed: bool
    score: str
    misconception_fixed: bool
    next_action: str
    new_mastery: float


class GraphNode(BaseModel):
    id: str
    label: str
    color: str
    status: str


class GraphStateResponse(BaseModel):
    nodes: list
    edges: list


# ==================== Helper Functions ====================

def mastery_to_status(score: float) -> str:
    """Convert mastery score to status string."""
    if score >= 0.6:
        return "mastered"
    elif score < 0.4:
        return "failed"
    return "neutral"


def get_concept_order() -> List[str]:
    """Get concepts in learning order."""
    return ["vectors", "matrix_ops", "determinants", "inverse_matrix", "eigenvalues"]


# ==================== Core Endpoints ====================

@app.get("/")
def root():
    """Health check."""
    return {
        "status": "ok",
        "message": "Mahavihara API is running",
        "version": "2.0.0",
        "tagline": "ChatGPT writes explanations. Mahavihara prescribes the perfect YouTube timestamp."
    }


@app.post("/start-session")
def start_session(request: StartSessionRequest):
    """Start a new tutoring session."""
    session_id = request.session_id or str(uuid.uuid4())[:8]

    # Clean up old session
    store.delete_session(session_id)
    if session_id in session_models:
        del session_models[session_id]
    if session_id in session_testers:
        del session_testers[session_id]

    # Initialize session
    store.get_or_create_session(session_id)
    model = get_or_create_model(session_id)

    # Get first concept
    concepts = get_concept_order()
    first_concept = concepts[0]
    concept_data = kg.get_concept(first_concept)

    # Generate welcome message
    welcome = f"""**Welcome to Mahavihara!**

I'll guide you through Linear Algebra, building from foundations to advanced topics.

**Your learning path:**
Vectors -> Matrix Operations -> Determinants -> Inverse Matrix -> Eigenvalues

Let's start with **{concept_data.get('name', first_concept)}**!

---

"""

    lesson = concept_data.get("lesson", "")
    lesson_with_prompt = lesson + "\n\n---\n*Ask me anything about this, or say \"quiz me\" when ready to test yourself!*"

    messages = [
        {"role": "assistant", "content": welcome},
        {"role": "assistant", "content": lesson_with_prompt}
    ]

    # Set initial state
    store.set_phase(session_id, "qa")
    store.set_current_concept_index(session_id, 0)

    return {
        "session_id": session_id,
        "messages": messages,
        "phase": "qa",
        "mastery": {c: 0.5 for c in concepts},
        "current_concept": first_concept
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Process a chat message."""
    session = store.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_id = request.session_id
    user_message = request.message
    phase = store.get_phase(session_id)
    concept_index = store.get_current_concept_index(session_id)

    concepts = get_concept_order()
    current_concept = concepts[concept_index] if concept_index < len(concepts) else concepts[-1]
    concept_data = kg.get_concept(current_concept)

    model = get_or_create_model(session_id)
    tester = get_or_create_tester(session_id)

    response_messages = []
    user_msg_lower = user_message.lower().strip()

    # ==================== Q&A PHASE ====================
    if phase == "qa":
        quiz_triggers = ["quiz me", "test me", "ready", "practice", "quiz"]
        wants_quiz = any(t in user_msg_lower for t in quiz_triggers)

        if wants_quiz:
            # Start quiz
            questions = tester.generate_quiz(current_concept, num_questions=3, strategy="progressive")

            if not questions:
                response_messages.append({
                    "role": "assistant",
                    "content": "You've answered all available questions! Say 'continue' to move on."
                })
                store.mark_concept_completed(session_id, current_concept)
            else:
                store.set_quiz_questions(session_id, questions)
                store.set_quiz_current_index(session_id, 0)
                store.set_quiz_answers(session_id, [])

                q = questions[0]
                difficulty_name = ["Easy", "Medium", "Hard"][q.get("difficulty", 2) - 1]

                options_text = "\n".join([
                    f"  {chr(65+i)}. {opt}"
                    for i, opt in enumerate(q["options"])
                ])

                response_messages.append({
                    "role": "assistant",
                    "content": f"""**Quiz: {concept_data.get('name', current_concept)}** (Need 2/3 to pass)

*Question 1/3 ({difficulty_name})*

{q['text']}

{options_text}"""
                })

            store.set_phase(session_id, "quiz")
            phase = "quiz"
        else:
            # Continue Q&A with Socratic tutor
            mastery_data = model._get_or_create_mastery(current_concept)
            context = TutorContext(
                concept_id=current_concept,
                concept_name=concept_data.get("name", current_concept),
                lesson=concept_data.get("lesson", ""),
                misconceptions=[m.description for m in misconception_detector.get_concept_misconceptions(current_concept)],
                mastery=mastery_data.mastery,
                streak=mastery_data.streak,
                teaching_turns=store.get_teaching_turns(session_id)
            )

            response = tutor.respond(user_message, context)
            response_messages.append({"role": "assistant", "content": response})
            store.increment_teaching_turns(session_id)

    # ==================== QUIZ PHASE ====================
    elif phase == "quiz":
        questions = store.get_quiz_questions(session_id)
        current_idx = store.get_quiz_current_index(session_id)

        if current_idx < len(questions):
            question = questions[current_idx]

            # Parse answer
            answer = user_message.strip().upper()
            answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            answer_idx = -1
            for key in answer_map:
                if key in answer:
                    answer_idx = answer_map[key]
                    break

            is_correct = (answer_idx == question["correct"])
            correct_option = chr(65 + question["correct"])

            # Record response
            result = tester.record_response(question, current_concept, is_correct)

            # Save quiz answer
            quiz_answers = store.get_quiz_answers(session_id)
            quiz_answers.append({
                "question_id": question["id"],
                "is_correct": is_correct,
                "user_answer": chr(65 + answer_idx) if answer_idx >= 0 else answer,
                "correct_answer": correct_option
            })
            store.set_quiz_answers(session_id, quiz_answers)

            # Feedback
            if is_correct:
                response_messages.append({"role": "assistant", "content": "Correct!"})
            else:
                explanation = question.get("explanation", question.get("hint", ""))
                response_messages.append({
                    "role": "assistant",
                    "content": f"The answer was **{correct_option}**.\n\n{explanation}"
                })

            # Next question or evaluate
            store.set_quiz_current_index(session_id, current_idx + 1)

            if current_idx + 1 < len(questions):
                next_q = questions[current_idx + 1]
                difficulty_name = ["Easy", "Medium", "Hard"][next_q.get("difficulty", 2) - 1]
                correct_so_far = sum(1 for a in quiz_answers if a["is_correct"])

                options_text = "\n".join([
                    f"  {chr(65+i)}. {opt}"
                    for i, opt in enumerate(next_q["options"])
                ])

                response_messages.append({
                    "role": "assistant",
                    "content": f"""*Question {current_idx + 2}/3 ({difficulty_name})* - {correct_so_far}/{current_idx + 1} correct so far

{next_q['text']}

{options_text}"""
                })
            else:
                # Quiz complete - evaluate
                correct_count = sum(1 for a in quiz_answers if a["is_correct"])

                if correct_count >= 2:
                    store.mark_concept_completed(session_id, current_concept)
                    store.set_can_advance(session_id, True)

                    if concept_index + 1 < len(concepts):
                        next_concept_name = kg.get_concept(concepts[concept_index + 1]).get("name", "")
                        response_messages.append({
                            "role": "assistant",
                            "content": f"""**Passed!** You got {correct_count}/3 correct.

**{concept_data.get('name')} Complete!**

**Next:** {next_concept_name}

Say **'continue'** to proceed, or ask questions to review."""
                        })
                    else:
                        response_messages.append({
                            "role": "assistant",
                            "content": f"""**Congratulations!** You got {correct_count}/3 and completed all concepts!

You've mastered Linear Algebra fundamentals!"""
                        })
                        phase = "complete"
                else:
                    # Failed - generate prescription
                    store.set_can_advance(session_id, False)

                    # Analyze wrong answers
                    wrong_analyses = []
                    for qa in quiz_answers:
                        if not qa["is_correct"]:
                            analysis = misconception_detector.analyze_wrong_answer(
                                question_id=qa["question_id"],
                                concept_id=current_concept,
                                user_answer=qa["user_answer"],
                                correct_answer=qa["correct_answer"]
                            )
                            wrong_analyses.append(analysis)

                    # Generate prescription
                    engine = PrescriptionEngine(kg, model, misconception_detector)
                    prescription = engine.generate_prescription(
                        concept_id=current_concept,
                        wrong_answers=wrong_analyses,
                        session_id=session_id
                    )

                    # Format for display
                    prescription_text = engine.format_prescription_for_display(prescription)

                    response_messages.append({
                        "role": "assistant",
                        "content": f"""You got {correct_count}/3 correct. Need 2/3 to advance.

{prescription_text}

After studying, say **'quiz me'** to try again!"""
                    })

                store.set_phase(session_id, "evaluate")
                phase = "evaluate"

    # ==================== EVALUATE PHASE ====================
    elif phase == "evaluate":
        continue_triggers = ["continue", "next", "move on", "proceed"]
        retry_triggers = ["retry", "try again", "quiz me", "practice"]

        can_advance = store.get_can_advance(session_id)

        if can_advance and any(t in user_msg_lower for t in continue_triggers):
            new_index = concept_index + 1
            if new_index < len(concepts):
                store.set_current_concept_index(session_id, new_index)
                new_concept = concepts[new_index]
                new_concept_data = kg.get_concept(new_concept)

                tutor.reset_conversation()

                lesson = new_concept_data.get("lesson", "")
                lesson_with_prompt = lesson + "\n\n---\n*Ask me anything, or say \"quiz me\" when ready!*"

                response_messages.append({
                    "role": "assistant",
                    "content": f"""**Concept {new_index + 1}/5: {new_concept_data.get('name')}**

---

{lesson_with_prompt}"""
                })

                store.set_phase(session_id, "qa")
                store.reset_teaching_turns(session_id)
                phase = "qa"
                current_concept = new_concept
            else:
                response_messages.append({
                    "role": "assistant",
                    "content": "You've completed all concepts! Amazing work!"
                })
                phase = "complete"

        elif any(t in user_msg_lower for t in retry_triggers):
            store.set_phase(session_id, "qa")
            phase = "qa"

            # Restart quiz
            tester.reset()
            questions = tester.generate_quiz(current_concept, num_questions=3)

            if questions:
                store.set_quiz_questions(session_id, questions)
                store.set_quiz_current_index(session_id, 0)
                store.set_quiz_answers(session_id, [])

                q = questions[0]
                options_text = "\n".join([f"  {chr(65+i)}. {opt}" for i, opt in enumerate(q["options"])])

                response_messages.append({
                    "role": "assistant",
                    "content": f"""**Quiz: {concept_data.get('name')}** (Need 2/3 to pass)

*Question 1/3*

{q['text']}

{options_text}"""
                })
                store.set_phase(session_id, "quiz")
                phase = "quiz"
        else:
            # Treat as Q&A
            store.set_phase(session_id, "qa")
            phase = "qa"

            mastery_data = model._get_or_create_mastery(current_concept)
            context = TutorContext(
                concept_id=current_concept,
                concept_name=concept_data.get("name", current_concept),
                lesson=concept_data.get("lesson", ""),
                misconceptions=[],
                mastery=mastery_data.mastery,
                streak=mastery_data.streak,
                teaching_turns=0
            )

            response = tutor.respond(user_message, context)
            response_messages.append({"role": "assistant", "content": response})

    # ==================== COMPLETE PHASE ====================
    elif phase == "complete":
        response_messages.append({
            "role": "assistant",
            "content": "You've completed the course! Feel free to ask questions for review."
        })

    # Build mastery dict from model
    mastery = {c: model.get_mastery(c) for c in concepts}

    return ChatResponse(
        messages=response_messages,
        phase=phase,
        mastery=mastery,
        current_concept=current_concept
    )


# ==================== Diagnosis & Prescription Endpoints ====================

@app.post("/diagnose", response_model=DiagnoseResponse)
def diagnose_learning_gaps(request: DiagnoseRequest):
    """
    Diagnose learning gaps from quiz results.

    Analyzes wrong answers to identify misconceptions and root causes.
    """
    model = get_or_create_model(request.session_id)

    # Analyze each wrong answer
    wrong_analyses = []
    for result in request.quiz_results:
        if not result.get("is_correct", True):
            analysis = misconception_detector.analyze_wrong_answer(
                question_id=result["question_id"],
                concept_id=request.concept_id,
                user_answer=result["user_answer"],
                correct_answer=result["correct_answer"]
            )
            wrong_analyses.append(analysis)

    # Extract misconceptions
    misconceptions = []
    for analysis in wrong_analyses:
        if analysis.misconception:
            misconceptions.append({
                "id": analysis.misconception.id,
                "description": analysis.misconception.description,
                "remediation": analysis.misconception.remediation,
                "confidence": analysis.confidence
            })

    # Check for root cause in prerequisites
    root_cause = None
    prerequisites = kg.get_prerequisites(request.concept_id)
    mastery_scores = model.get_all_mastery()

    weak_prereqs = [p for p in prerequisites if mastery_scores.get(p, 0.5) < 0.5]
    if weak_prereqs:
        weakest = min(weak_prereqs, key=lambda p: mastery_scores.get(p, 0.5))
        concept = kg.get_concept(weakest)
        root_cause = {
            "concept_id": weakest,
            "concept_name": concept.get("name", weakest) if concept else weakest,
            "mastery": mastery_scores.get(weakest, 0.5)
        }

    # Calculate severity
    severity = 1
    if root_cause:
        severity = 3
    elif len(misconceptions) >= 2:
        severity = 2

    return DiagnoseResponse(
        concept_id=request.concept_id,
        misconceptions=misconceptions,
        root_cause=root_cause,
        severity=severity,
        needs_prescription=len(misconceptions) > 0 or root_cause is not None
    )


@app.get("/prescription/{session_id}/{concept_id}", response_model=PrescriptionResponse)
def get_prescription(session_id: str, concept_id: str):
    """
    Get a learning prescription for a concept.

    Returns personalized resources and study plan.
    """
    model = get_or_create_model(session_id)

    # Get recent quiz answers for this concept (if available)
    quiz_answers = store.get_quiz_answers(session_id)
    wrong_analyses = []

    for qa in quiz_answers:
        if not qa.get("is_correct", True):
            analysis = misconception_detector.analyze_wrong_answer(
                question_id=qa.get("question_id", "unknown"),
                concept_id=concept_id,
                user_answer=qa.get("user_answer", ""),
                correct_answer=qa.get("correct_answer", "")
            )
            wrong_analyses.append(analysis)

    # Generate prescription
    engine = PrescriptionEngine(kg, model, misconception_detector)
    prescription = engine.generate_prescription(
        concept_id=concept_id,
        wrong_answers=wrong_analyses,
        session_id=session_id
    )

    # Convert to response format
    return PrescriptionResponse(
        concept_id=prescription.diagnosed_concept,
        concept_name=prescription.diagnosed_concept_name,
        severity=prescription.severity,
        root_cause={
            "concept_id": prescription.root_cause_concept,
            "concept_name": prescription.root_cause_name
        } if prescription.root_cause_concept else None,
        misconceptions=[
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "severity": m.severity,
                "remediation_concept": m.remediation_concept,
                "remediation_focus": m.remediation_focus
            }
            for m in prescription.misconceptions
        ],
        phases=engine.to_frontend_format(prescription)["phases"],
        total_estimated_minutes=prescription.total_estimated_minutes,
        verification={
            "questions_to_pass": prescription.questions_to_pass,
            "questions_total": prescription.questions_total,
            "must_show_work": prescription.must_show_work
        },
        formatted=engine.format_prescription_for_display(prescription)
    )


@app.post("/verify", response_model=VerifyResponse)
def verify_mastery(request: VerifyRequest):
    """
    Verify mastery after studying prescription.

    Checks if misconceptions have been fixed.
    """
    model = get_or_create_model(request.session_id)

    # Count correct answers
    correct_count = sum(1 for r in request.quiz_results if r.get("is_correct", False))
    total = len(request.quiz_results)

    passed = correct_count >= 2  # Need 2/3 to pass

    # Check if previous misconceptions are fixed
    misconception_fixed = True
    for result in request.quiz_results:
        if not result.get("is_correct", True):
            analysis = misconception_detector.analyze_wrong_answer(
                question_id=result["question_id"],
                concept_id=request.concept_id,
                user_answer=result["user_answer"],
                correct_answer=result["correct_answer"]
            )
            if analysis.misconception:
                misconception_fixed = False
                break

    # Update mastery
    new_mastery = model.get_mastery(request.concept_id)
    if passed:
        new_mastery = min(1.0, new_mastery + 0.2)
    else:
        new_mastery = max(0.0, new_mastery - 0.1)

    # Determine next action
    if passed:
        next_action = "continue"
    elif misconception_fixed:
        next_action = "practice_more"
    else:
        next_action = "review_prescription"

    return VerifyResponse(
        passed=passed,
        score=f"{correct_count}/{total}",
        misconception_fixed=misconception_fixed,
        next_action=next_action,
        new_mastery=new_mastery
    )


# ==================== Graph & Resource Endpoints ====================

@app.get("/graph-state/{session_id}", response_model=GraphStateResponse)
def get_graph_state(session_id: str):
    """Get knowledge graph visualization state."""
    session = store.get_session(session_id)

    if not session:
        mastery = {c: 0.5 for c in get_concept_order()}
    else:
        model = get_or_create_model(session_id)
        mastery = {c: model.get_mastery(c) for c in get_concept_order()}

    viz = kg.get_graph_visualization(mastery)

    nodes = []
    for node in viz["nodes"]:
        score = mastery.get(node["id"], 0.5)
        nodes.append({
            "id": node["id"],
            "label": node["label"],
            "color": node["color"],
            "status": mastery_to_status(score)
        })

    return GraphStateResponse(nodes=nodes, edges=viz["edges"])


@app.get("/resources/{concept_id}")
def get_resources(concept_id: str, difficulty: Optional[int] = None, limit: int = 5):
    """Get curated learning resources for a concept."""
    resources = resource_curator.get_resources(
        concept_id,
        difficulty=difficulty,
        limit=limit
    )

    return {
        "concept_id": concept_id,
        "resources": resource_curator.to_frontend_format(resources),
        "formatted": resource_curator.format_resources_for_display(resources),
        "stats": {
            "total_available": len(resource_curator.concept_resources.get(concept_id, [])),
            "returned": len(resources)
        }
    }


@app.get("/session/{session_id}")
def get_session_state(session_id: str):
    """Get full session state."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    model = get_or_create_model(session_id)

    return {
        "session_id": session_id,
        "state": session["state"],
        "mastery": {c: model.get_mastery(c) for c in get_concept_order()},
        "completed_concepts": store.get_completed_concepts(session_id),
        "current_phase": store.get_phase(session_id),
        "current_concept_index": store.get_current_concept_index(session_id)
    }


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    """Delete a session."""
    store.delete_session(session_id)

    if session_id in session_models:
        del session_models[session_id]
    if session_id in session_testers:
        del session_testers[session_id]

    return {"status": "deleted", "session_id": session_id}


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
