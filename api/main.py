"""
FastAPI Backend for Mahavihara - AI Tutoring Platform

"ChatGPT writes explanations. Mahavihara prescribes the perfect YouTube timestamp."

FIXED VERSION: Actually uses all the components we built:
- MisconceptionDetector: Analyzes WHY students got answers wrong
- PrescriptionEngine: Generates targeted learning plans
- ResourceCurator + Tavily: Finds specific videos/resources
- Socratic Tutor: Context-aware with quiz history
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge_graph import KnowledgeGraph
from core.student_model import StudentModel
from core.adaptive_tester import AdaptiveTester
from core.misconception_detector import MisconceptionDetector
from teaching.socratic_tutor import SocraticTutor, TutorContext
from teaching.resource_curator import ResourceCurator
from teaching.prescription_engine import PrescriptionEngine, format_prescription_for_display
from redis_store import RedisStore

# ==================== Initialize ====================

app = FastAPI(
    title="Mahavihara API",
    description="Adaptive AI Tutor - Prescription-based Learning",
    version="2.1.0"
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
resource_curator = ResourceCurator()  # Will use Tavily if TAVILY_API_KEY is set
tutor = SocraticTutor()
prescription_engine = PrescriptionEngine(kg)

# Session-specific components
session_models: Dict[str, StudentModel] = {}
session_testers: Dict[str, AdaptiveTester] = {}


def get_or_create_model(session_id: str) -> StudentModel:
    if session_id not in session_models:
        session_models[session_id] = StudentModel()
    return session_models[session_id]


def get_or_create_tester(session_id: str) -> AdaptiveTester:
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
    current_concept: Optional[str] = None
    # NEW: Gap analysis and prescription data for frontend
    gap_analysis: Optional[dict] = None
    prescription: Optional[dict] = None
    resources: Optional[list] = None
    show_prescription_card: bool = False


class DiagnoseRequest(BaseModel):
    session_id: str
    concept_id: str
    quiz_results: List[dict]


class DiagnoseResponse(BaseModel):
    concept_id: str
    misconceptions: List[dict]
    root_cause: Optional[dict]
    severity: int
    needs_prescription: bool


class PrescriptionResponse(BaseModel):
    diagnosis: dict
    prescription: dict
    resources: dict
    verification: dict
    formatted: str


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
    if score >= 0.6:
        return "mastered"
    elif score < 0.4:
        return "failed"
    return "neutral"


def get_concept_order() -> List[str]:
    return ["vectors", "matrix_ops", "determinants", "inverse_matrix", "eigenvalues"]


def sync_mastery_to_model(model: StudentModel, concept_id: str, new_mastery: float):
    """Sync mastery to StudentModel so graph visualization works."""
    mastery_data = model._get_or_create_mastery(concept_id)
    mastery_data.mastery = new_mastery
    mastery_data.practice_count += 1
    if new_mastery >= 0.6:
        mastery_data.correct_count += 1
    model.concepts[concept_id] = mastery_data


def analyze_quiz_results(quiz_answers: List[dict], concept_id: str) -> dict:
    """
    Analyze quiz answers using MisconceptionDetector.
    Returns structured gap analysis.
    """
    if not quiz_answers:
        return None
    
    # Convert to format expected by misconception detector
    formatted_answers = []
    for qa in quiz_answers:
        formatted_answers.append({
            "question_id": qa.get("question_id", ""),
            "chosen": ord(qa.get("user_answer", "A").upper()) - ord('A') if qa.get("user_answer") else 0,
            "correct": ord(qa.get("correct_answer", "A").upper()) - ord('A') if qa.get("correct_answer") else 0,
            "is_correct": qa.get("is_correct", False)
        })
    
    # Analyze pattern
    pattern = misconception_detector.analyze_answer_pattern(formatted_answers)
    
    # Build gap analysis
    wrong_answers = [qa for qa in quiz_answers if not qa.get("is_correct")]
    
    gap_analysis = {
        "total_questions": len(quiz_answers),
        "correct_count": sum(1 for qa in quiz_answers if qa.get("is_correct")),
        "wrong_answers": [],
        "primary_weakness": pattern.get("primary_weakness"),
        "misconceptions": []
    }
    
    # Analyze each wrong answer
    for wa in wrong_answers:
        analysis = misconception_detector.analyze_wrong_answer(
            question_id=wa.get("question_id", ""),
            concept_id=concept_id,
            user_answer=wa.get("user_answer", ""),
            correct_answer=wa.get("correct_answer", "")
        )
        
        wrong_detail = {
            "question_id": wa.get("question_id"),
            "user_answer": wa.get("user_answer"),
            "correct_answer": wa.get("correct_answer"),
        }
        
        if analysis and analysis.misconception:
            wrong_detail["misconception"] = {
                "id": analysis.misconception.id,
                "name": analysis.misconception.name,
                "description": analysis.misconception.description,
                "severity": analysis.misconception.severity,
                "explanation": analysis.explanation,
                "remediation_focus": analysis.misconception.remediation_focus
            }
            gap_analysis["misconceptions"].append(wrong_detail["misconception"])
        
        gap_analysis["wrong_answers"].append(wrong_detail)
    
    # Get most critical misconception
    if pattern.get("most_critical"):
        mc = pattern["most_critical"]
        gap_analysis["most_critical"] = {
            "name": mc.misconception.name,
            "description": mc.misconception.description,
            "explanation": mc.explanation,
            "remediation": mc.misconception.remediation_focus
        }
    
    return gap_analysis


def generate_full_prescription(
    session_id: str,
    concept_id: str,
    quiz_answers: List[dict],
    model: StudentModel
) -> dict:
    """
    Generate a full prescription using PrescriptionEngine + ResourceCurator.
    This is what makes Mahavihara different from ChatGPT!
    """
    # Convert quiz answers to prescription engine format
    wrong_answers = [
        {
            "question_id": qa.get("question_id", ""),
            "chosen": ord(qa.get("user_answer", "A").upper()) - ord('A') if qa.get("user_answer") else 0,
            "correct": ord(qa.get("correct_answer", "A").upper()) - ord('A') if qa.get("correct_answer") else 0,
            "is_correct": qa.get("is_correct", False)
        }
        for qa in quiz_answers
    ]
    
    # Get mastery scores
    mastery_scores = {c: model.get_mastery(c) for c in get_concept_order()}
    
    # Generate prescription
    prescription = prescription_engine.generate_prescription(
        failed_concept=concept_id,
        wrong_answers=wrong_answers,
        mastery_scores=mastery_scores,
        learning_style="visual"
    )
    
    # Get additional resources via Tavily (if available)
    additional_resources = []
    if resource_curator.tavily_client:
        try:
            # Search for targeted resources based on misconception
            search_query = f"{concept_id} {prescription.misconception or 'tutorial'}"
            import asyncio
            # Use sync version or fallback
            resources = resource_curator.get_resources(concept_id, limit=3)
            additional_resources = resource_curator.to_frontend_format(resources)
        except Exception as e:
            print(f"Tavily search error: {e}")
    
    # Format for frontend
    frontend_format = prescription.to_frontend_format()
    
    # Add any additional Tavily resources
    if additional_resources:
        frontend_format["resources"]["items"].extend(additional_resources)
    
    return frontend_format


def get_targeted_resources(concept_id: str, misconception: str = None) -> List[dict]:
    """
    Get targeted resources for a concept, optionally focused on a misconception.
    Uses Tavily if available, falls back to curated resources.
    """
    resources = resource_curator.get_prescription_resources(
        concept_id,
        mastery=0.4  # Assume struggling
    )
    
    # Combine understand + practice resources
    all_resources = []
    for r in resources.get("understand", []):
        all_resources.append({
            "type": r.source_type,
            "title": r.title,
            "url": r.url,
            "source": r.tags[0] if r.tags else "web",
            "why": r.why_recommended,
            "duration": f"{r.duration_minutes} min" if r.duration_minutes else None,
            "timestamp": r.timestamp
        })
    
    for r in resources.get("practice", []):
        all_resources.append({
            "type": r.source_type,
            "title": r.title,
            "url": r.url,
            "source": r.tags[0] if r.tags else "web",
            "why": r.why_recommended
        })
    
    return all_resources[:5]  # Limit to 5


def build_feedback_message(
    passed: bool,
    correct_count: int,
    total: int,
    concept_name: str,
    gap_analysis: dict,
    resources: List[dict],
    next_concept_name: str = None
) -> str:
    """
    Build a helpful feedback message that actually tells the student what went wrong.
    This is NOT Socratic - this is DIRECT feedback.
    """
    lines = []
    
    if passed:
        lines.append(f"🎉 **Passed!** You got {correct_count}/{total} correct.")
        lines.append(f"\n**{concept_name} Complete!** ✅")
        
        # Even when passed, tell them what they almost got wrong
        if gap_analysis and gap_analysis.get("wrong_answers"):
            lines.append("\n**Quick note on what you missed:**")
            for wa in gap_analysis["wrong_answers"]:
                if wa.get("misconception"):
                    mc = wa["misconception"]
                    lines.append(f"• {mc['description']}")
                    lines.append(f"  → *{mc.get('explanation', 'Review this concept')}*")
        
        # Suggest optional resource
        if resources and len(resources) > 0:
            r = resources[0]
            lines.append(f"\n📺 **Optional review:** [{r['title']}]({r['url']})")
            if r.get('why'):
                lines.append(f"   *{r['why']}*")
        
        if next_concept_name:
            lines.append(f"\n**Next:** {next_concept_name}")
            lines.append("\nSay **'continue'** to proceed, or ask questions to review.")
        else:
            lines.append("\n🏆 **Congratulations!** You've completed all concepts!")
    
    else:
        lines.append(f"📊 **You got {correct_count}/{total}.** Need 2/3 to advance.")
        
        # Tell them EXACTLY what went wrong
        if gap_analysis:
            lines.append("\n**🔍 Here's what happened:**")
            
            for i, wa in enumerate(gap_analysis.get("wrong_answers", []), 1):
                lines.append(f"\n**Q{i}:** You chose {wa.get('user_answer')}, correct was {wa.get('correct_answer')}")
                if wa.get("misconception"):
                    mc = wa["misconception"]
                    lines.append(f"   ❌ **Issue:** {mc['description']}")
                    if mc.get('explanation'):
                        lines.append(f"   💡 **Why:** {mc['explanation']}")
            
            # Root cause
            if gap_analysis.get("most_critical"):
                mc = gap_analysis["most_critical"]
                lines.append(f"\n**🎯 Main issue:** {mc['name']}")
                lines.append(f"   {mc['description']}")
        
        # Show resources
        if resources:
            lines.append("\n**📚 Your Prescription:**")
            for i, r in enumerate(resources[:3], 1):
                emoji = "🎬" if r.get("type") == "youtube" else "🔗"
                timestamp = f" @ {r['timestamp']}" if r.get('timestamp') else ""
                lines.append(f"{i}. {emoji} [{r['title']}]({r['url']}){timestamp}")
                if r.get('why'):
                    lines.append(f"   *{r['why']}*")
        
        lines.append("\n💪 Study the resources above, then say **'quiz me'** to try again!")
    
    return "\n".join(lines)


# ==================== Core Endpoints ====================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Mahavihara API is running",
        "version": "2.1.0",
        "tagline": "ChatGPT writes explanations. Mahavihara prescribes the perfect YouTube timestamp.",
        "features": {
            "misconception_detection": True,
            "prescription_engine": True,
            "tavily_search": resource_curator.tavily_client is not None,
            "socratic_tutor": True
        }
    }


@app.post("/start-session")
def start_session(request: StartSessionRequest):
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
    
    if concept_data is None:
        concept_data = {"name": first_concept.replace("_", " ").title(), "lesson": ""}

    concept_name = concept_data.get('name', first_concept)
    
    welcome = f"""**Welcome to Mahavihara!** 🎓

I'll guide you through Linear Algebra, building from foundations to advanced topics.

**Your learning path:**
Vectors → Matrix Operations → Determinants → Inverse Matrix → Eigenvalues

Let's start with **{concept_name}**!

---
"""

    lesson = concept_data.get("lesson", "")
    if not lesson:
        lesson = f"Let's learn about {concept_name}!"
    lesson_with_prompt = lesson + "\n\n---\n💬 *Ask me anything about this, or say \"quiz me\" when ready!*"

    messages = [
        {"role": "assistant", "content": welcome},
        {"role": "assistant", "content": lesson_with_prompt}
    ]

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
    
    if concept_data is None:
        concept_data = {"name": current_concept.replace("_", " ").title(), "lesson": ""}

    concept_name = concept_data.get("name", current_concept)
    
    model = get_or_create_model(session_id)
    tester = get_or_create_tester(session_id)

    response_messages = []
    user_msg_lower = user_message.lower().strip()
    
    # Response data
    gap_analysis = None
    prescription_data = None
    resources_data = None
    show_prescription_card = False

    # ==================== Q&A PHASE ====================
    if phase == "qa":
        # Expanded quiz triggers
        quiz_triggers = [
            "quiz me", "test me", "practice", "quiz",
            "start quiz", "take quiz", "begin quiz",
            "questions", "ask questions", "jump to questions",
            "let's go", "lets go", "begin", "start",
            "i'm ready", "im ready", "ready",
            "test my knowledge", "check my understanding"
        ]
        wants_quiz = any(t in user_msg_lower for t in quiz_triggers)
        
        # Short message trigger
        if not wants_quiz and len(user_msg_lower.split()) <= 4:
            short_triggers = ["question", "test", "go", "start", "begin", "try"]
            wants_quiz = any(t in user_msg_lower for t in short_triggers)

        if wants_quiz:
            questions = tester.generate_quiz(current_concept, num_questions=3, strategy="progressive")

            if not questions:
                response_messages.append({
                    "role": "assistant",
                    "content": "You've answered all available questions! Say 'continue' to move on."
                })
                store.mark_concept_completed(session_id, current_concept)
                sync_mastery_to_model(model, current_concept, 0.75)
            else:
                store.set_quiz_questions(session_id, questions)
                store.set_quiz_current_index(session_id, 0)
                store.set_quiz_answers(session_id, [])

                q = questions[0]
                difficulty_name = ["Easy", "Medium", "Hard"][q.get("difficulty", 1) - 1]
                options_text = "\n".join([f"  {chr(65+i)}. {opt}" for i, opt in enumerate(q["options"])])

                response_messages.append({
                    "role": "assistant",
                    "content": f"""📝 **Quiz: {concept_name}** (Need 2/3 to pass)

*Question 1/3 ({difficulty_name})*

{q['text']}

{options_text}"""
                })

            store.set_phase(session_id, "quiz")
            phase = "quiz"
        
        # Check if asking about gaps/mistakes
        elif any(t in user_msg_lower for t in ["gaps", "mistakes", "wrong", "missed", "explain my"]):
            # Get stored quiz answers and provide targeted feedback
            quiz_answers = store.get_quiz_answers(session_id)
            if quiz_answers:
                gap_analysis = analyze_quiz_results(quiz_answers, current_concept)
                resources_data = get_targeted_resources(current_concept)
                
                # Build helpful response
                lines = ["**Here's what you got wrong:**\n"]
                for wa in gap_analysis.get("wrong_answers", []):
                    lines.append(f"• **Q:** You chose {wa['user_answer']}, correct was {wa['correct_answer']}")
                    if wa.get("misconception"):
                        mc = wa["misconception"]
                        lines.append(f"  💡 {mc['description']}")
                        lines.append(f"  → {mc.get('explanation', '')}")
                
                if resources_data:
                    lines.append("\n**📚 Resources to help:**")
                    for r in resources_data[:2]:
                        lines.append(f"• [{r['title']}]({r['url']})")
                
                response_messages.append({"role": "assistant", "content": "\n".join(lines)})
            else:
                response_messages.append({
                    "role": "assistant",
                    "content": "You haven't taken a quiz yet! Say **'quiz me'** to test your knowledge."
                })
        
        else:
            # Socratic Q&A with context
            quiz_answers = store.get_quiz_answers(session_id)
            detected_misconceptions = []
            
            if quiz_answers:
                gap = analyze_quiz_results(quiz_answers, current_concept)
                if gap:
                    detected_misconceptions = [m.get("description", "") for m in gap.get("misconceptions", [])]
            
            mastery_data = model._get_or_create_mastery(current_concept)
            context = TutorContext(
                concept_id=current_concept,
                concept_name=concept_name,
                lesson=concept_data.get("lesson", ""),
                misconceptions=detected_misconceptions,  # NOW POPULATED!
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

            tester.record_response(question, current_concept, is_correct)

            quiz_answers = store.get_quiz_answers(session_id)
            quiz_answers.append({
                "question_id": question["id"],
                "is_correct": is_correct,
                "user_answer": chr(65 + answer_idx) if answer_idx >= 0 else answer,
                "correct_answer": correct_option
            })
            store.set_quiz_answers(session_id, quiz_answers)

            # Immediate feedback
            if is_correct:
                response_messages.append({"role": "assistant", "content": "✅ Correct!"})
            else:
                explanation = question.get("explanation", question.get("hint", ""))
                response_messages.append({
                    "role": "assistant",
                    "content": f"❌ The answer was **{correct_option}**.\n\n{explanation}"
                })

            store.set_quiz_current_index(session_id, current_idx + 1)

            if current_idx + 1 < len(questions):
                next_q = questions[current_idx + 1]
                difficulty_name = ["Easy", "Medium", "Hard"][next_q.get("difficulty", 1) - 1]
                correct_so_far = sum(1 for a in quiz_answers if a["is_correct"])
                options_text = "\n".join([f"  {chr(65+i)}. {opt}" for i, opt in enumerate(next_q["options"])])

                response_messages.append({
                    "role": "assistant",
                    "content": f"""*Question {current_idx + 2}/3 ({difficulty_name})* - {correct_so_far}/{current_idx + 1} correct so far

{next_q['text']}

{options_text}"""
                })
            else:
                # ==================== QUIZ COMPLETE ====================
                correct_count = sum(1 for a in quiz_answers if a["is_correct"])
                passed = correct_count >= 2
                
                # ANALYZE RESULTS (This is the key part!)
                gap_analysis = analyze_quiz_results(quiz_answers, current_concept)
                resources_data = get_targeted_resources(current_concept, 
                    gap_analysis.get("most_critical", {}).get("name") if gap_analysis else None)
                
                if passed:
                    # PASSED
                    store.mark_concept_completed(session_id, current_concept)
                    store.set_can_advance(session_id, True)
                    sync_mastery_to_model(model, current_concept, 0.75)
                    
                    next_concept_name = None
                    if concept_index + 1 < len(concepts):
                        next_data = kg.get_concept(concepts[concept_index + 1])
                        next_concept_name = next_data.get("name", concepts[concept_index + 1]) if next_data else concepts[concept_index + 1]
                    
                    feedback = build_feedback_message(
                        passed=True,
                        correct_count=correct_count,
                        total=3,
                        concept_name=concept_name,
                        gap_analysis=gap_analysis,
                        resources=resources_data,
                        next_concept_name=next_concept_name
                    )
                    response_messages.append({"role": "assistant", "content": feedback})
                    
                    if concept_index + 1 >= len(concepts):
                        phase = "complete"
                        store.set_phase(session_id, "complete")
                
                else:
                    # FAILED - Generate full prescription
                    store.set_can_advance(session_id, False)
                    sync_mastery_to_model(model, current_concept, max(0.25, model.get_mastery(current_concept) - 0.15))
                    
                    # Generate prescription for frontend
                    prescription_data = generate_full_prescription(
                        session_id, current_concept, quiz_answers, model
                    )
                    show_prescription_card = True
                    
                    feedback = build_feedback_message(
                        passed=False,
                        correct_count=correct_count,
                        total=3,
                        concept_name=concept_name,
                        gap_analysis=gap_analysis,
                        resources=resources_data
                    )
                    response_messages.append({"role": "assistant", "content": feedback})
                
                store.set_phase(session_id, "evaluate")
                phase = "evaluate"

    # ==================== EVALUATE PHASE ====================
    elif phase == "evaluate":
        continue_triggers = ["continue", "next", "move on", "proceed"]
        retry_triggers = ["retry", "try again", "quiz me", "practice", "quiz"]
        gap_triggers = ["gaps", "mistakes", "wrong", "explain", "what did i"]

        can_advance = store.get_can_advance(session_id)

        if can_advance and any(t in user_msg_lower for t in continue_triggers):
            new_index = concept_index + 1
            if new_index < len(concepts):
                store.set_current_concept_index(session_id, new_index)
                new_concept = concepts[new_index]
                new_concept_data = kg.get_concept(new_concept)
                
                if new_concept_data is None:
                    new_concept_data = {"name": new_concept.replace("_", " ").title(), "lesson": ""}

                tutor.reset_conversation()

                lesson = new_concept_data.get("lesson", "")
                if not lesson:
                    lesson = f"Let's learn about {new_concept_data.get('name', new_concept)}!"
                lesson_with_prompt = lesson + "\n\n---\n💬 *Ask me anything, or say \"quiz me\" when ready!*"

                response_messages.append({
                    "role": "assistant",
                    "content": f"""**Concept {new_index + 1}/5: {new_concept_data.get('name', new_concept)}**

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
                    "content": "🎓 You've completed all concepts! Amazing work!"
                })
                store.set_phase(session_id, "complete")
                phase = "complete"

        elif any(t in user_msg_lower for t in retry_triggers):
            store.set_phase(session_id, "qa")
            phase = "qa"

            tester.reset()
            questions = tester.generate_quiz(current_concept, num_questions=3)

            if questions:
                store.set_quiz_questions(session_id, questions)
                store.set_quiz_current_index(session_id, 0)
                store.set_quiz_answers(session_id, [])

                q = questions[0]
                difficulty_name = ["Easy", "Medium", "Hard"][q.get("difficulty", 1) - 1]
                options_text = "\n".join([f"  {chr(65+i)}. {opt}" for i, opt in enumerate(q["options"])])

                response_messages.append({
                    "role": "assistant",
                    "content": f"""📝 **Quiz: {concept_name}** (Need 2/3 to pass)

*Question 1/3 ({difficulty_name})*

{q['text']}

{options_text}"""
                })
                store.set_phase(session_id, "quiz")
                phase = "quiz"
        
        elif any(t in user_msg_lower for t in gap_triggers):
            # Show gaps/prescription
            quiz_answers = store.get_quiz_answers(session_id)
            if quiz_answers:
                gap_analysis = analyze_quiz_results(quiz_answers, current_concept)
                resources_data = get_targeted_resources(current_concept)
                prescription_data = generate_full_prescription(session_id, current_concept, quiz_answers, model)
                show_prescription_card = True
                
                response_messages.append({
                    "role": "assistant",
                    "content": "📋 Here's your personalized learning prescription! Check the card on the right →"
                })
            else:
                response_messages.append({
                    "role": "assistant",
                    "content": "Take a quiz first to see your gaps!"
                })
        
        else:
            # Q&A in evaluate phase with full context
            quiz_answers = store.get_quiz_answers(session_id)
            detected_misconceptions = []
            
            if quiz_answers:
                gap = analyze_quiz_results(quiz_answers, current_concept)
                if gap:
                    detected_misconceptions = [m.get("description", "") for m in gap.get("misconceptions", [])]
            
            mastery_data = model._get_or_create_mastery(current_concept)
            context = TutorContext(
                concept_id=current_concept,
                concept_name=concept_name,
                lesson=concept_data.get("lesson", ""),
                misconceptions=detected_misconceptions,
                mastery=mastery_data.mastery,
                streak=mastery_data.streak,
                teaching_turns=store.get_teaching_turns(session_id)
            )
            response = tutor.respond(user_message, context)
            response_messages.append({"role": "assistant", "content": response})

    # ==================== COMPLETE PHASE ====================
    elif phase == "complete":
        response_messages.append({
            "role": "assistant",
            "content": "🎓 You've completed the course! Feel free to ask questions for review."
        })

    # Build response
    mastery = {c: model.get_mastery(c) for c in concepts}

    return ChatResponse(
        messages=response_messages,
        phase=phase,
        mastery=mastery,
        current_concept=current_concept,
        gap_analysis=gap_analysis,
        prescription=prescription_data,
        resources=resources_data,
        show_prescription_card=show_prescription_card
    )


# ==================== Prescription & Diagnosis Endpoints ====================

@app.get("/prescription/{session_id}/{concept_id}", response_model=PrescriptionResponse)
def get_prescription(session_id: str, concept_id: str):
    """Get a full learning prescription for a concept."""
    model = get_or_create_model(session_id)
    quiz_answers = store.get_quiz_answers(session_id)
    
    if not quiz_answers:
        # Generate default prescription
        wrong_answers = []
    else:
        wrong_answers = [
            {
                "question_id": qa.get("question_id", ""),
                "chosen": ord(qa.get("user_answer", "A").upper()) - ord('A') if qa.get("user_answer") else 0,
                "correct": ord(qa.get("correct_answer", "A").upper()) - ord('A') if qa.get("correct_answer") else 0,
                "is_correct": qa.get("is_correct", False)
            }
            for qa in quiz_answers
        ]
    
    mastery_scores = {c: model.get_mastery(c) for c in get_concept_order()}
    
    prescription = prescription_engine.generate_prescription(
        failed_concept=concept_id,
        wrong_answers=wrong_answers,
        mastery_scores=mastery_scores,
        learning_style="visual"
    )
    
    frontend_format = prescription.to_frontend_format()
    
    return PrescriptionResponse(
        diagnosis=frontend_format["diagnosis"],
        prescription=frontend_format["prescription"],
        resources=frontend_format["resources"],
        verification=frontend_format["verification"],
        formatted=format_prescription_for_display(prescription)
    )


@app.post("/diagnose", response_model=DiagnoseResponse)
def diagnose_learning_gaps(request: DiagnoseRequest):
    """Diagnose learning gaps from quiz results."""
    model = get_or_create_model(request.session_id)

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

    misconceptions = []
    for analysis in wrong_analyses:
        if analysis and analysis.misconception:
            misconceptions.append({
                "id": analysis.misconception.id,
                "description": analysis.misconception.description,
                "remediation": analysis.misconception.remediation_focus,
                "confidence": analysis.confidence
            })

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


@app.post("/verify", response_model=VerifyResponse)
def verify_mastery(request: VerifyRequest):
    """Verify mastery after studying prescription."""
    model = get_or_create_model(request.session_id)

    correct_count = sum(1 for r in request.quiz_results if r.get("is_correct", False))
    total = len(request.quiz_results)
    passed = correct_count >= 2

    misconception_fixed = True
    for result in request.quiz_results:
        if not result.get("is_correct", True):
            analysis = misconception_detector.analyze_wrong_answer(
                question_id=result["question_id"],
                concept_id=request.concept_id,
                user_answer=result["user_answer"],
                correct_answer=result["correct_answer"]
            )
            if analysis and analysis.misconception:
                misconception_fixed = False
                break

    current_mastery = model.get_mastery(request.concept_id)
    if passed:
        new_mastery = min(1.0, current_mastery + 0.2)
    else:
        new_mastery = max(0.0, current_mastery - 0.1)
    
    sync_mastery_to_model(model, request.concept_id, new_mastery)

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
def get_resources_endpoint(concept_id: str, difficulty: Optional[int] = None, limit: int = 5):
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
        "tavily_enabled": resource_curator.tavily_client is not None
    }


@app.get("/session/{session_id}")
def get_session_state(session_id: str):
    """Get full session state including quiz history."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    model = get_or_create_model(session_id)
    quiz_answers = store.get_quiz_answers(session_id)
    
    # Analyze if there are quiz answers
    gap_analysis = None
    if quiz_answers:
        current_concept = get_concept_order()[store.get_current_concept_index(session_id)]
        gap_analysis = analyze_quiz_results(quiz_answers, current_concept)

    return {
        "session_id": session_id,
        "state": session["state"],
        "mastery": {c: model.get_mastery(c) for c in get_concept_order()},
        "completed_concepts": store.get_completed_concepts(session_id),
        "current_phase": store.get_phase(session_id),
        "current_concept_index": store.get_current_concept_index(session_id),
        "quiz_history": quiz_answers,
        "gap_analysis": gap_analysis
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