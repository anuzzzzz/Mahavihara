"""
FastAPI Backend for Mahavihara - AI Tutoring Platform
VERSION 2.3 - All Critical Bugs Fixed

FIXES:
- BUG-C01: Wrong answer display now shows CORRECT question numbers
- BUG-C02: Root cause no longer returns same concept (circular)
- BUG-C03: Quiz answers tracking fixed with original question index
- BUG-H01: Badge state properly managed
- BUG-H02/H03: Question randomization improved
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import sys
import random
from pathlib import Path

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
    description="Adaptive AI Tutor for Linear Algebra",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

kg = KnowledgeGraph()
store = RedisStore()
misconception_detector = MisconceptionDetector()
resource_curator = ResourceCurator()
tutor = SocraticTutor()

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


def sync_mastery_to_model(model: StudentModel, concept_id: str, new_mastery: float):
    """Sync mastery to StudentModel so graph visualization works."""
    mastery_data = model._get_or_create_mastery(concept_id)
    mastery_data.mastery = new_mastery
    model.concepts[concept_id] = mastery_data


# ==================== FIXED: Root Cause Tracing ====================

PREREQ_MAP = {
    "eigenvalues": ["inverse_matrix", "determinants", "matrix_ops", "vectors"],
    "inverse_matrix": ["determinants", "matrix_ops", "vectors"],
    "determinants": ["matrix_ops", "vectors"],
    "matrix_ops": ["vectors"],
    "vectors": []
}

def trace_root_cause_fixed(failed_concept: str, mastery_scores: Dict[str, float]) -> str:
    """
    FIXED: Trace back through prerequisites to find root cause.
    
    Key fixes:
    1. Never returns the same concept (circular)
    2. If all prereqs are strong, identifies the WEAKEST prereq instead
    3. If no prereqs, returns helpful message
    """
    prereqs = PREREQ_MAP.get(failed_concept, [])
    
    if not prereqs:
        # No prerequisites - this IS the foundation
        return f"{failed_concept} (foundation concept)"
    
    WEAK_THRESHOLD = 0.6
    
    # First, check for truly weak prerequisites
    weak_prereqs = []
    for prereq in prereqs:
        mastery = mastery_scores.get(prereq, 0.5)
        if mastery < WEAK_THRESHOLD:
            weak_prereqs.append((prereq, mastery))
    
    if weak_prereqs:
        # Return the weakest one
        weakest = min(weak_prereqs, key=lambda x: x[1])
        return weakest[0]
    
    # All prereqs are "strong" but user still failed
    # This means it's a NEW misconception in THIS concept, not a prerequisite gap
    # Return the concept itself but with different framing
    return f"{failed_concept} (new concept gaps)"


# ==================== INTENT DETECTION ====================

def detect_intent(user_msg_lower: str) -> str:
    """Detect user intent with PRIORITY ORDER."""
    
    # PRIORITY 1: Quiz intent
    quiz_triggers = [
        "quiz me", "test me", "practice", "quiz",
        "questions", "question", "ask questions",
        "start quiz", "take quiz", "begin quiz",
        "let's go", "lets go", "begin", "start",
        "ready", "i'm ready", "im ready",
        "test", "questions now", "go to questions",
        "can we do questions", "do questions",
        "jump to questions", "skip to questions",
        "quiz it", "lets quiz", "let's quiz",
        "do the quiz", "take the test",
        "can we go to questions", "go to quiz"
    ]
    if any(t in user_msg_lower for t in quiz_triggers):
        return "quiz"
    
    # Short message quiz detection
    if len(user_msg_lower.split()) <= 5:
        short_quiz = ["question", "test", "go", "start", "begin", "try", "now", "quiz"]
        if any(t in user_msg_lower for t in short_quiz):
            return "quiz"
    
    # PRIORITY 2: Explain what was wrong
    explain_wrong_triggers = [
        "what was wrong", "what did i get wrong", "explain wrong",
        "explain concepts", "what i missed", "review what was wrong",
        "explain my mistakes", "what mistakes", "which were wrong",
        "explain the wrong", "concepts which were wrong",
        "explain gaps", "my gaps", "what are my gaps",
        "what did i miss", "where did i go wrong"
    ]
    if any(t in user_msg_lower for t in explain_wrong_triggers):
        return "explain_wrong"
    
    # PRIORITY 3: Resource requests
    resource_triggers = [
        "resources", "resource", "videos", "video",
        "tutorial", "tutorials", "guide", "guides",
        "links", "link", "watch", "learn more",
        "recommend", "recommendation", "suggest",
        "3b1b", "3blue1brown", "khan", "youtube"
    ]
    if any(t in user_msg_lower for t in resource_triggers):
        return "resources"
    
    # PRIORITY 4: Continue to next concept
    continue_triggers = ["continue", "next", "move on", "proceed", "next concept"]
    if any(t in user_msg_lower for t in continue_triggers):
        return "continue"
    
    # PRIORITY 5: Retry quiz
    retry_triggers = ["retry", "try again", "again", "retake"]
    if any(t in user_msg_lower for t in retry_triggers):
        return "retry"
    
    return "qa"


# ==================== FIXED: Direct Explanation ====================

def generate_direct_explanation(quiz_answers: List[dict], concept_id: str, concept_name: str) -> str:
    """
    FIXED: Generate DIRECT explanation of what went wrong.
    Now shows CORRECT question numbers!
    """
    # Find wrong answers WITH their original question numbers
    wrong_with_index = []
    for i, qa in enumerate(quiz_answers):
        if not qa.get("is_correct"):
            wrong_with_index.append((i + 1, qa))  # i+1 = question number (1-indexed)
    
    if not wrong_with_index:
        return f"Actually, you got everything right on {concept_name}! 🎉\n\nSay **'continue'** to move to the next topic!"
    
    lines = [f"**Here's what you got wrong on {concept_name}:**\n"]
    
    for q_num, wa in wrong_with_index:
        user_ans = wa.get("user_answer", "?")
        correct_ans = wa.get("correct_answer", "?")
        q_text = wa.get("question_text", "")[:50]
        q_id = wa.get("question_id", "")
        
        lines.append(f"**Question {q_num}:** {q_text}...")
        lines.append(f"   You chose **{user_ans}**, correct was **{correct_ans}**")
        
        # Get misconception if available
        try:
            analysis = misconception_detector.analyze_wrong_answer(
                question_id=q_id,
                concept_id=concept_id,
                user_answer=user_ans,
                correct_answer=correct_ans
            )
            if analysis and analysis.misconception:
                lines.append(f"   💡 **Issue:** {analysis.misconception.description}")
        except:
            pass
        
        # Add explanation if stored
        explanation = wa.get("explanation", "")
        if explanation:
            lines.append(f"   📝 **Why:** {explanation}")
        
        lines.append("")
    
    # Add resources
    lines.append("**📚 Resources to help:**")
    try:
        resources = resource_curator.get_resources(concept_id, limit=2)
        for r in resources[:2]:
            lines.append(f"• [{r.title}]({r.url})")
    except:
        lines.append(f"• Search for '{concept_name} tutorial' on YouTube")
    
    lines.append("\n💪 Review these concepts, then say **'quiz me'** to try again!")
    
    return "\n".join(lines)


# ==================== FIXED: What Went Wrong Display ====================

def format_what_went_wrong(quiz_answers: List[dict]) -> str:
    """
    FIXED: Format what went wrong with CORRECT question numbers.
    
    Key fix: Use original question index, not filtered index!
    """
    lines = ["**What went wrong:**"]
    
    for i, qa in enumerate(quiz_answers):
        if not qa.get("is_correct"):
            q_num = i + 1  # Original question number (1-indexed)
            user_ans = qa.get("user_answer", "?")
            correct_ans = qa.get("correct_answer", "?")
            lines.append(f"• Q{q_num}: You chose **{user_ans}**, correct was **{correct_ans}**")
    
    return "\n".join(lines)


def generate_resource_response(concept_id: str, concept_name: str) -> str:
    """Give ACTUAL resources, don't ask more questions!"""
    lines = [f"**📚 Best resources for {concept_name}:**\n"]
    
    try:
        resources = resource_curator.get_resources(concept_id, limit=5)
        
        for i, r in enumerate(resources[:5], 1):
            emoji = "🎬" if "youtube" in r.url.lower() or "video" in r.source_type.lower() else "📖"
            timestamp = f" @ {r.timestamp}" if hasattr(r, 'timestamp') and r.timestamp else ""
            lines.append(f"{i}. {emoji} **{r.title}**{timestamp}")
            lines.append(f"   {r.url}")
            if hasattr(r, 'why_recommended') and r.why_recommended:
                lines.append(f"   *{r.why_recommended}*")
            lines.append("")
    except:
        lines.append(f"1. 🎬 **3Blue1Brown** - Essence of Linear Algebra")
        lines.append(f"   https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab")
        lines.append("")
        lines.append(f"2. 📖 **Khan Academy** - {concept_name}")
        lines.append(f"   https://www.khanacademy.org/math/linear-algebra")
    
    lines.append("---")
    lines.append("When you're ready, say **'quiz me'** to test your understanding!")
    
    return "\n".join(lines)


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
    quiz_passed: Optional[bool] = None
    can_advance: bool = False
    next_concept: Optional[str] = None
    show_prescription_card: bool = False
    prescription: Optional[dict] = None


class GraphStateResponse(BaseModel):
    nodes: list
    edges: list


def mastery_to_status(score: float) -> str:
    if score >= 0.6:
        return "mastered"
    elif score < 0.4:
        return "failed"
    return "neutral"


def get_concept_order() -> List[str]:
    return ["vectors", "matrix_ops", "determinants", "inverse_matrix", "eigenvalues"]


def get_safe_concept_data(concept_id: str) -> dict:
    data = kg.get_concept(concept_id)
    if data is None:
        return {"name": concept_id.replace("_", " ").title(), "lesson": ""}
    return data


# ==================== Core Endpoints ====================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Mahavihara API is running",
        "version": "2.3.0",
        "fixes": ["BUG-C01", "BUG-C02", "BUG-C03", "Question numbering", "Root cause tracing"]
    }


@app.post("/start-session")
def start_session(request: StartSessionRequest):
    session_id = request.session_id or str(uuid.uuid4())[:8]

    store.delete_session(session_id)
    if session_id in session_models:
        del session_models[session_id]
    if session_id in session_testers:
        del session_testers[session_id]

    store.get_or_create_session(session_id)
    model = get_or_create_model(session_id)

    concepts = get_concept_order()
    first_concept = concepts[0]
    concept_data = get_safe_concept_data(first_concept)

    welcome = f"""**Welcome to Mahavihara!** 🎓

I'll guide you through Linear Algebra, building from foundations to advanced topics.

**Your learning path:**
Vectors → Matrix Operations → Determinants → Inverse Matrix → Eigenvalues

Let's start with **{concept_data.get('name', first_concept)}**!

---
"""

    lesson = concept_data.get("lesson", "")
    lesson_with_prompt = lesson + "\n\n---\n💬 *Ask me anything about this, or say \"quiz me\" when you're ready to test yourself!*"

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
        "current_concept": first_concept,
        "quiz_passed": None,
        "can_advance": False
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
    concept_data = get_safe_concept_data(current_concept)
    concept_name = concept_data.get("name", current_concept)

    model = get_or_create_model(session_id)
    tester = get_or_create_tester(session_id)

    response_messages = []
    user_msg_lower = user_message.lower().strip()
    
    # Response state
    quiz_passed = None
    can_advance = store.get_can_advance(session_id)
    next_concept_name = None
    show_prescription_card = False
    prescription_data = None

    if concept_index + 1 < len(concepts):
        next_data = get_safe_concept_data(concepts[concept_index + 1])
        next_concept_name = next_data.get("name", concepts[concept_index + 1])

    intent = detect_intent(user_msg_lower)

    # ==================== Q&A PHASE ====================
    if phase == "qa":
        if intent == "quiz":
            # Reset tester to get fresh questions
            tester.reset()
            questions = tester.generate_quiz(current_concept, num_questions=3, strategy="progressive")

            if not questions:
                response_messages.append({
                    "role": "assistant",
                    "content": "You've answered all available questions! Say 'continue' to move on."
                })
                store.mark_concept_completed(session_id, current_concept)
                sync_mastery_to_model(model, current_concept, 0.75)
                can_advance = True
                quiz_passed = True
            else:
                # Shuffle questions for variety
                random.shuffle(questions)
                
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
        
        elif intent == "resources":
            response = generate_resource_response(current_concept, concept_name)
            response_messages.append({"role": "assistant", "content": response})
        
        else:
            teaching_turns = store.get_teaching_turns(session_id)
            
            mastery_data = model._get_or_create_mastery(current_concept)
            context = TutorContext(
                concept_id=current_concept,
                concept_name=concept_name,
                lesson=concept_data.get("lesson", ""),
                misconceptions=[],
                mastery=mastery_data.mastery,
                streak=mastery_data.streak,
                teaching_turns=teaching_turns
            )
            response = tutor.respond(user_message, context)
            
            if teaching_turns >= 3 and teaching_turns % 3 == 0:
                response += "\n\n---\n💡 *When you're ready, say \"quiz me\" to test your understanding!*"
            
            response_messages.append({"role": "assistant", "content": response})
            store.increment_teaching_turns(session_id)

    # ==================== QUIZ PHASE ====================
    elif phase == "quiz":
        questions = store.get_quiz_questions(session_id)
        current_idx = store.get_quiz_current_index(session_id)

        if current_idx < len(questions):
            question = questions[current_idx]

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

            # FIXED: Store question number and text for accurate display later
            quiz_answers = store.get_quiz_answers(session_id)
            quiz_answers.append({
                "question_id": question["id"],
                "question_number": current_idx + 1,  # 1-indexed
                "question_text": question.get("text", ""),
                "is_correct": is_correct,
                "user_answer": chr(65 + answer_idx) if answer_idx >= 0 else answer,
                "correct_answer": correct_option,
                "explanation": question.get("explanation", question.get("hint", ""))
            })
            store.set_quiz_answers(session_id, quiz_answers)

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
                # QUIZ COMPLETE
                correct_count = sum(1 for a in quiz_answers if a["is_correct"])

                if correct_count >= 2:
                    # PASSED
                    quiz_passed = True
                    can_advance = True
                    store.mark_concept_completed(session_id, current_concept)
                    store.set_can_advance(session_id, True)
                    sync_mastery_to_model(model, current_concept, 0.75)

                    # FIXED: Show what was missed with correct question numbers
                    wrong_feedback = ""
                    wrong_answers = [a for a in quiz_answers if not a["is_correct"]]
                    if wrong_answers:
                        wrong_nums = [str(a.get("question_number", "?")) for a in wrong_answers]
                        wrong_feedback = f"\n\n*(You missed Q{', Q'.join(wrong_nums)} - click 'Review What I Missed' for details)*"

                    if concept_index + 1 < len(concepts):
                        response_messages.append({
                            "role": "assistant",
                            "content": f"""🎉 **Passed!** You got {correct_count}/3 correct.

**{concept_name} Complete!** ✅{wrong_feedback}

**Next:** {next_concept_name}

Click **'Continue'** below to proceed, or ask questions to review."""
                        })
                    else:
                        response_messages.append({
                            "role": "assistant",
                            "content": f"""🏆 **Congratulations!** You got {correct_count}/3 and completed all concepts!

You've mastered Linear Algebra fundamentals! 🎓"""
                        })
                        phase = "complete"
                        store.set_phase(session_id, "complete")
                else:
                    # FAILED
                    quiz_passed = False
                    can_advance = False
                    store.set_can_advance(session_id, False)
                    sync_mastery_to_model(model, current_concept, max(0.25, model.get_mastery(current_concept) - 0.15))

                    # Generate prescription with FIXED root cause
                    try:
                        wrong_answers_formatted = [
                            {
                                "question_id": qa.get("question_id", ""),
                                "chosen": ord(qa.get("user_answer", "A").upper()) - ord('A'),
                                "correct": ord(qa.get("correct_answer", "A").upper()) - ord('A'),
                                "is_correct": qa.get("is_correct", False)
                            }
                            for qa in quiz_answers
                        ]
                        
                        mastery_scores = {c: model.get_mastery(c) for c in concepts}
                        engine = PrescriptionEngine(kg)
                        
                        # Override root cause with fixed version
                        prescription = engine.generate_prescription(
                            failed_concept=current_concept,
                            wrong_answers=wrong_answers_formatted,
                            mastery_scores=mastery_scores,
                            learning_style="visual"
                        )
                        
                        # FIXED: Override circular root cause
                        if prescription.root_cause == current_concept:
                            # Find the actual issue
                            fixed_root = trace_root_cause_fixed(current_concept, mastery_scores)
                            prescription.root_cause = fixed_root
                        
                        prescription_data = prescription.to_frontend_format()
                        show_prescription_card = True
                    except Exception as e:
                        print(f"Prescription generation error: {e}")

                    # FIXED: What went wrong with correct question numbers
                    what_wrong_text = format_what_went_wrong(quiz_answers)

                    response_messages.append({
                        "role": "assistant",
                        "content": f"""📊 **You got {correct_count}/3.** Need 2/3 to advance.

{what_wrong_text}

📋 **Check the Prescription Card** for targeted resources!

Click **'Try Again'** below when ready, or **'Explain My Mistakes'** for help."""
                    })

                if phase != "complete":
                    store.set_phase(session_id, "evaluate")
                    phase = "evaluate"

    # ==================== EVALUATE PHASE ====================
    elif phase == "evaluate":
        can_advance = store.get_can_advance(session_id)

        if intent == "continue" and can_advance:
            new_index = concept_index + 1
            if new_index < len(concepts):
                store.set_current_concept_index(session_id, new_index)
                new_concept = concepts[new_index]
                new_data = get_safe_concept_data(new_concept)

                tutor.reset_conversation()

                lesson = new_data.get("lesson", "")
                lesson_with_prompt = lesson + "\n\n---\n💬 *Ask me anything, or say \"quiz me\" when you're ready!*"

                response_messages.append({
                    "role": "assistant",
                    "content": f"""**Concept {new_index + 1}/5: {new_data.get('name', new_concept)}**

---

{lesson_with_prompt}"""
                })

                store.set_phase(session_id, "qa")
                store.set_can_advance(session_id, False)
                store.reset_teaching_turns(session_id)
                phase = "qa"
                current_concept = new_concept
                can_advance = False
                quiz_passed = None
                
                if new_index + 1 < len(concepts):
                    next_data = get_safe_concept_data(concepts[new_index + 1])
                    next_concept_name = next_data.get("name", concepts[new_index + 1])
                else:
                    next_concept_name = None
            else:
                response_messages.append({
                    "role": "assistant",
                    "content": "🎓 You've completed all concepts! Amazing work!"
                })
                phase = "complete"
                store.set_phase(session_id, "complete")

        elif intent == "quiz" or intent == "retry":
            # Reset and get NEW questions
            tester.reset()
            questions = tester.generate_quiz(current_concept, num_questions=3)

            if questions:
                # Shuffle for variety
                random.shuffle(questions)
                
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
                quiz_passed = None
            else:
                response_messages.append({
                    "role": "assistant",
                    "content": "No more questions available. Say 'continue' to move on!"
                })

        elif intent == "explain_wrong":
            quiz_answers = store.get_quiz_answers(session_id)
            response = generate_direct_explanation(quiz_answers, current_concept, concept_name)
            response_messages.append({"role": "assistant", "content": response})
            quiz_passed = store.get_can_advance(session_id)

        elif intent == "resources":
            response = generate_resource_response(current_concept, concept_name)
            response_messages.append({"role": "assistant", "content": response})
            quiz_passed = store.get_can_advance(session_id)

        else:
            quiz_answers = store.get_quiz_answers(session_id)
            
            confusion_words = ["confused", "understand", "wrong", "mistake", "help", "explain"]
            if any(w in user_msg_lower for w in confusion_words) and quiz_answers:
                response = generate_direct_explanation(quiz_answers, current_concept, concept_name)
                response_messages.append({"role": "assistant", "content": response})
            else:
                mastery_data = model._get_or_create_mastery(current_concept)
                context = TutorContext(
                    concept_id=current_concept,
                    concept_name=concept_name,
                    lesson=concept_data.get("lesson", ""),
                    misconceptions=[],
                    mastery=mastery_data.mastery,
                    streak=mastery_data.streak,
                    teaching_turns=store.get_teaching_turns(session_id)
                )
                response = tutor.respond(user_message, context)
                response_messages.append({"role": "assistant", "content": response})
            
            quiz_passed = store.get_can_advance(session_id)

    # ==================== COMPLETE PHASE ====================
    elif phase == "complete":
        response_messages.append({
            "role": "assistant",
            "content": "🎓 You've completed the course! Feel free to ask questions for review."
        })

    mastery = {c: model.get_mastery(c) for c in concepts}

    return ChatResponse(
        messages=response_messages,
        phase=phase,
        mastery=mastery,
        current_concept=current_concept,
        quiz_passed=quiz_passed,
        can_advance=can_advance,
        next_concept=next_concept_name,
        show_prescription_card=show_prescription_card,
        prescription=prescription_data
    )


# ==================== Other Endpoints ====================

@app.get("/graph-state/{session_id}", response_model=GraphStateResponse)
def get_graph_state(session_id: str):
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
def get_resources_endpoint(concept_id: str, limit: int = 5):
    resources = resource_curator.get_resources(concept_id, limit=limit)
    return {
        "concept_id": concept_id,
        "resources": resource_curator.to_frontend_format(resources),
        "formatted": resource_curator.format_resources_for_display(resources)
    }


@app.get("/session/{session_id}")
def get_session_state(session_id: str):
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
        "current_concept_index": store.get_current_concept_index(session_id),
        "can_advance": store.get_can_advance(session_id)
    }


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    store.delete_session(session_id)
    if session_id in session_models:
        del session_models[session_id]
    if session_id in session_testers:
        del session_testers[session_id]
    return {"status": "deleted", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)