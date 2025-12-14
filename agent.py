"""
Mahavihara AI Tutor - Linear Learning with Soft Gates

APPROACH: Allow flexibility but warn about prerequisites
- Students CAN skip ahead if they want
- But they get warned about missing prerequisites
- If they fail, suggest going back to prerequisites
- Track completed vs skipped concepts

Phases:
    lesson -> qa -> quiz -> evaluate -> (next/back/retry)
"""

import os
import random
from typing import TypedDict, Literal, Optional, List, Dict
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from knowledge_graph import KnowledgeGraph
from redis_store import RedisStore

load_dotenv()

# ==================== State Definition ====================

class AgentState(TypedDict):
    """State that flows through the graph."""
    session_id: str
    phase: Literal["lesson", "qa", "quiz", "evaluate", "complete"]
    messages: List
    current_question: Optional[dict]
    current_concept_index: int
    mastery: dict
    quiz_answers: List[dict]
    teaching_turns: int


# ==================== Constants ====================

CONCEPT_ORDER = ["vectors", "matrix_ops", "determinants", "inverse_matrix", "eigenvalues"]
REQUIRED_CORRECT = 2  # Need 2/3 to pass
QUESTIONS_PER_QUIZ = 3


# ==================== Initialize Components ====================

kg = KnowledgeGraph()
store = RedisStore()
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7
)


# ==================== Helper Functions ====================

def get_current_concept_id(state: AgentState) -> str:
    """Get the current concept ID based on index."""
    idx = state.get("current_concept_index", 0)
    if idx < len(CONCEPT_ORDER):
        return CONCEPT_ORDER[idx]
    return CONCEPT_ORDER[-1]


def get_concept_index(concept_id: str) -> int:
    """Get index of a concept."""
    try:
        return CONCEPT_ORDER.index(concept_id)
    except ValueError:
        return 0


def get_incomplete_prerequisites(session_id: str, concept_index: int) -> List[str]:
    """Get list of prerequisites that haven't been completed."""
    completed = store.get_completed_concepts(session_id)
    incomplete = []
    
    for i in range(concept_index):
        concept_id = CONCEPT_ORDER[i]
        if concept_id not in completed:
            incomplete.append(concept_id)
    
    return incomplete


def get_progressive_questions(concept_id: str, asked_ids: List[str]) -> List[dict]:
    """Get 3 questions with progressive difficulty: Easy → Medium → Hard."""
    questions = []
    
    for difficulty in [1, 2, 3]:
        available = kg.get_unseen_questions(concept_id, asked_ids, difficulty)
        if available:
            q = random.choice(available)
            q["asked_difficulty"] = difficulty
            questions.append(q)
            asked_ids.append(q["id"])
        else:
            fallback = kg.get_unseen_questions(concept_id, asked_ids)
            if fallback:
                q = random.choice(fallback)
                q["asked_difficulty"] = difficulty
                questions.append(q)
                asked_ids.append(q["id"])
    
    return questions


def generate_gap_analysis(quiz_answers: List[dict], concept_data: dict, incomplete_prereqs: List[str]) -> str:
    """Generate detailed gap analysis with prerequisite suggestions."""
    correct_count = sum(1 for a in quiz_answers if a["is_correct"])
    total = len(quiz_answers)
    
    if correct_count == total:
        return f"🎉 **Perfect score!** You got all {total} questions correct!"
    
    passed = correct_count >= REQUIRED_CORRECT
    
    if passed:
        header = f"✅ **Passed!** You got {correct_count}/{total} correct."
    else:
        header = f"📚 **Not quite yet.** You got {correct_count}/{total} correct. You need {REQUIRED_CORRECT}/{total} to advance."
    
    analysis_parts = [header, ""]
    
    # Show what they got wrong
    wrong_answers = [a for a in quiz_answers if not a["is_correct"]]
    if wrong_answers:
        analysis_parts.append("**What to review:**")
        for i, answer in enumerate(wrong_answers):
            difficulty_name = ["Easy", "Medium", "Hard"][answer.get("difficulty", 1) - 1]
            analysis_parts.append(f"• **{difficulty_name}**: {answer['question_text'][:60]}...")
            analysis_parts.append(f"  → Correct: {answer['correct_answer']} | *{answer['explanation']}*")
            analysis_parts.append("")
    
    # If failed AND has incomplete prerequisites, suggest going back
    if not passed and incomplete_prereqs:
        prereq_names = [kg.get_concept(pid)["name"] for pid in incomplete_prereqs]
        analysis_parts.append("💡 **Tip:** This concept builds on:")
        for name in prereq_names:
            analysis_parts.append(f"  • {name}")
        analysis_parts.append("")
        analysis_parts.append("Consider saying **'go back'** to strengthen these foundations first!")
    elif not passed:
        analysis_parts.append("💡 Ask me questions about the parts you found confusing, then say **'quiz me'** to try again!")
    
    if passed:
        analysis_parts.append("🎯 Say **'continue'** to move to the next concept, or ask questions to review!")
    
    return "\n".join(analysis_parts)


def parse_concept_request(message: str) -> Optional[str]:
    """Check if user is requesting a specific concept."""
    message_lower = message.lower()
    
    concept_triggers = {
        "vectors": ["vector", "vectors"],
        "matrix_ops": ["matrix op", "matrix operations", "matrix addition", "matrix multiplication"],
        "determinants": ["determinant", "determinants", "det"],
        "inverse_matrix": ["inverse", "inverse matrix", "inverses"],
        "eigenvalues": ["eigen", "eigenvalue", "eigenvalues", "eigenvector"]
    }
    
    for concept_id, triggers in concept_triggers.items():
        for trigger in triggers:
            if trigger in message_lower:
                return concept_id
    
    return None


# ==================== Node Functions ====================

def lesson_node(state: AgentState, show_warning: bool = False, skipped_prereqs: List[str] = None) -> AgentState:
    """Show the lesson for the current concept."""
    session_id = state["session_id"]
    concept_id = get_current_concept_id(state)
    concept_data = kg.get_concept(concept_id)
    concept_index = state.get("current_concept_index", 0)
    total_concepts = len(CONCEPT_ORDER)
    
    # Build progress indicator
    completed = store.get_completed_concepts(session_id)
    
    progress_lines = []
    for i, cid in enumerate(CONCEPT_ORDER):
        c = kg.get_concept(cid)
        if cid in completed:
            status = "✅"
        elif i == concept_index:
            status = "📍"
        else:
            status = "⬜"
        progress_lines.append(f"{status} {c['name']}")
    
    progress_display = " → ".join(progress_lines)
    
    messages_to_add = []
    
    # Welcome message for first time
    if concept_index == 0 and not completed:
        welcome = f"""🎓 **Welcome to Mahavihara!**

I'll guide you through Linear Algebra, building from foundations to advanced topics.

**Your learning path:**
{chr(10).join(progress_lines)}

You can learn in order, or jump to any topic. But I'll warn you if you're missing prerequisites!

---

"""
        messages_to_add.append(AIMessage(content=welcome))
    
    # Warning if skipping prerequisites
    if show_warning and skipped_prereqs:
        prereq_names = [kg.get_concept(pid)["name"] for pid in skipped_prereqs]
        warning = f"""⚠️ **Heads up!** 

**{concept_data['name']}** builds on concepts you haven't completed yet:
"""
        for name in prereq_names:
            warning += f"• {name}\n"
        
        warning += f"""
You can continue, but you might find some parts tricky. 
If you get stuck, consider saying **'go back'** to strengthen the foundations.

---

"""
        messages_to_add.append(AIMessage(content=warning))
    
    # Concept header with progress
    header = f"""📚 **Concept {concept_index + 1}/{total_concepts}: {concept_data['name']}**

{progress_display}

---

"""
    messages_to_add.append(AIMessage(content=header))
    
    # Show the lesson
    lesson = concept_data.get("lesson", concept_data.get("explanation", ""))
    lesson_with_prompt = lesson + "\n\n---\n💬 *Ask me anything about this, or say \"quiz me\" when ready to test yourself!*"
    messages_to_add.append(AIMessage(content=lesson_with_prompt))
    
    state["messages"].extend(messages_to_add)
    state["phase"] = "qa"
    state["teaching_turns"] = 0
    state["quiz_answers"] = []
    
    store.set_phase(session_id, "qa")
    store.set_current_concept_index(session_id, concept_index)
    store.reset_teaching_turns(session_id)
    
    return state


def qa_node(state: AgentState) -> AgentState:
    """Handle Q&A dialogue about the current concept."""
    session_id = state["session_id"]
    concept_id = get_current_concept_id(state)
    concept_data = kg.get_concept(concept_id)
    
    system_prompt = f"""You are a warm, encouraging tutor teaching "{concept_data['name']}".

The student is learning this concept:
---
{concept_data.get('lesson', concept_data['explanation'])}
---

YOUR ROLE:
- Answer questions about THIS CONCEPT thoroughly
- If they ask about a different LINEAR ALGEBRA topic, you can briefly explain but remind them: "We'll cover that in depth later! For now, let's focus on {concept_data['name']}."
- Be detailed when explaining - use multiple paragraphs if needed
- Use concrete examples with actual numbers
- Use **bold** for key terms

FORMATTING:
- Use **bold** for emphasis
- Use bullet points for lists
- Do NOT use LaTeX - write math as plain text: "det = ad - bc"
- For matrices: [[a, b], [c, d]]

RESPONSE PATTERNS:
- "yes" / "got it" → "Great! Ask more questions or say 'quiz me' when ready!"
- "no" / "confused" → Give a DIFFERENT explanation with new analogies, step-by-step
- Specific question → Answer thoroughly with examples

Be encouraging! Say things like "Great question!", "That's a common confusion!", "You're thinking about this the right way!"
"""

    gpt_messages = [SystemMessage(content=system_prompt)]
    
    for msg in state["messages"][-8:]:
        if isinstance(msg, HumanMessage):
            gpt_messages.append(msg)
        elif isinstance(msg, AIMessage):
            gpt_messages.append(msg)
    
    response = llm.invoke(gpt_messages)
    state["messages"].append(AIMessage(content=response.content))
    
    store.increment_teaching_turns(session_id)
    
    return state


def quiz_node(state: AgentState) -> AgentState:
    """Start a 3-question quiz with progressive difficulty."""
    session_id = state["session_id"]
    concept_id = get_current_concept_id(state)
    concept_data = kg.get_concept(concept_id)
    
    asked_ids = store.get_asked_questions(session_id)
    questions = get_progressive_questions(concept_id, asked_ids)
    
    if not questions:
        state["messages"].append(AIMessage(
            content="You've answered all available questions! Great job! Say 'continue' to move on."
        ))
        store.mark_concept_completed(session_id, concept_id)
        state["phase"] = "evaluate"
        return state
    
    store.set_quiz_questions(session_id, questions)
    store.set_quiz_current_index(session_id, 0)
    store.set_quiz_answers(session_id, [])
    
    question = questions[0]
    difficulty_name = ["Easy", "Medium", "Hard"][question.get("asked_difficulty", 1) - 1]
    
    options_text = "\n".join([
        f"  {chr(65+i)}. {opt}" 
        for i, opt in enumerate(question["options"])
    ])
    
    message = f"""📝 **Quiz: {concept_data['name']}** (Need {REQUIRED_CORRECT}/{QUESTIONS_PER_QUIZ} to pass)

*Question 1/{QUESTIONS_PER_QUIZ} ({difficulty_name})*

{question['text']}

{options_text}"""
    
    state["messages"].append(AIMessage(content=message))
    state["current_question"] = question
    state["phase"] = "quiz"
    state["quiz_answers"] = []
    
    store.set_phase(session_id, "quiz")
    
    return state


def process_quiz_answer_node(state: AgentState) -> AgentState:
    """Process quiz answer and show next question or evaluate."""
    session_id = state["session_id"]
    question = state["current_question"]
    concept_id = get_current_concept_id(state)
    concept_data = kg.get_concept(concept_id)
    
    if not question:
        return state
    
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return state
    
    answer = last_message.content.strip().upper()
    
    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    answer_idx = -1
    for key in answer_map:
        if key in answer:
            answer_idx = answer_map[key]
            break
    
    is_correct = (answer_idx == question["correct"])
    correct_option = chr(65 + question["correct"])
    user_answer = chr(65 + answer_idx) if answer_idx >= 0 else answer
    
    quiz_answer = {
        "question_id": question["id"],
        "question_text": question["text"],
        "user_answer": user_answer,
        "correct_answer": correct_option,
        "is_correct": is_correct,
        "difficulty": question.get("asked_difficulty", 2),
        "explanation": question.get("explanation", question.get("hint", ""))
    }
    
    quiz_answers = store.get_quiz_answers(session_id)
    quiz_answers.append(quiz_answer)
    store.set_quiz_answers(session_id, quiz_answers)
    state["quiz_answers"] = quiz_answers
    
    store.record_answer(session_id, question["id"], concept_id, is_correct)
    store.update_mastery(session_id, concept_id, is_correct)
    
    # Quick feedback
    if is_correct:
        feedback = "✅ Correct!"
    else:
        feedback = f"❌ The answer was **{correct_option}**."
    
    state["messages"].append(AIMessage(content=feedback))
    
    # Next question or evaluate
    questions = store.get_quiz_questions(session_id)
    current_index = store.get_quiz_current_index(session_id) + 1
    store.set_quiz_current_index(session_id, current_index)
    
    if current_index < len(questions):
        question = questions[current_index]
        difficulty_name = ["Easy", "Medium", "Hard"][question.get("asked_difficulty", 1) - 1]
        
        options_text = "\n".join([
            f"  {chr(65+i)}. {opt}" 
            for i, opt in enumerate(question["options"])
        ])
        
        correct_so_far = sum(1 for a in quiz_answers if a["is_correct"])
        
        message = f"""*Question {current_index + 1}/{QUESTIONS_PER_QUIZ} ({difficulty_name})* — {correct_so_far}/{current_index} correct so far

{question['text']}

{options_text}"""
        
        state["messages"].append(AIMessage(content=message))
        state["current_question"] = question
    else:
        # Quiz complete
        state["phase"] = "evaluate"
        state["current_question"] = None
        store.set_phase(session_id, "evaluate")
        
        # Get incomplete prerequisites for context
        concept_index = state.get("current_concept_index", 0)
        incomplete_prereqs = get_incomplete_prerequisites(session_id, concept_index)
        
        analysis = generate_gap_analysis(quiz_answers, concept_data, incomplete_prereqs)
        state["messages"].append(AIMessage(content=analysis))
        
        # Check if passed
        correct_count = sum(1 for a in quiz_answers if a["is_correct"])
        
        if correct_count >= REQUIRED_CORRECT:
            store.mark_concept_completed(session_id, concept_id)
            store.set_can_advance(session_id, True)
            
            # Check if more concepts
            if concept_index + 1 < len(CONCEPT_ORDER):
                next_concept = kg.get_concept(CONCEPT_ORDER[concept_index + 1])
                state["messages"].append(AIMessage(
                    content=f"\n🎉 **{concept_data['name']} Complete!**\n\n"
                           f"**Next:** {next_concept['name']}\n\n"
                           f"Say **'continue'** to proceed, or ask questions to review."
                ))
            else:
                state["messages"].append(AIMessage(
                    content=f"\n🏆 **Congratulations!** You've completed all 5 concepts!\n\n"
                           f"You've mastered Linear Algebra fundamentals! 🎓"
                ))
                state["phase"] = "complete"
                store.set_phase(session_id, "complete")
        else:
            store.set_can_advance(session_id, False)
    
    return state


# ==================== Main Agent Class ====================

class TutorAgent:
    """High-level interface for the tutor agent with soft gates."""
    
    def __init__(self):
        pass
    
    def start_session(self, session_id: str) -> dict:
        """Start a new tutoring session."""
        session_data = store.get_or_create_session(session_id)
        
        state = AgentState(
            session_id=session_id,
            phase="lesson",
            messages=[],
            current_question=None,
            current_concept_index=0,
            mastery=session_data["mastery"],
            quiz_answers=[],
            teaching_turns=0
        )
        
        state = lesson_node(state)
        
        return {
            "messages": [{"role": "assistant", "content": m.content} for m in state["messages"]],
            "phase": state["phase"],
            "mastery": state["mastery"],
            "current_concept": get_current_concept_id(state)
        }
    
    def process_message(self, session_id: str, user_message: str) -> dict:
        """Process user message based on current phase."""
        session_data = store.get_or_create_session(session_id)
        phase = store.get_phase(session_id)
        concept_index = store.get_current_concept_index(session_id)
        
        state = AgentState(
            session_id=session_id,
            phase=phase,
            messages=[HumanMessage(content=user_message)],
            current_question=None,
            current_concept_index=concept_index,
            mastery=session_data["mastery"],
            quiz_answers=store.get_quiz_answers(session_id),
            teaching_turns=store.get_teaching_turns(session_id)
        )
        
        response_messages = []
        user_msg_lower = user_message.lower().strip()
        
        # ==================== NAVIGATION COMMANDS (work in any phase) ====================
        
        # Check if user wants to go to a specific concept
        requested_concept = parse_concept_request(user_message)
        if requested_concept and phase != "quiz":
            new_index = get_concept_index(requested_concept)
            incomplete_prereqs = get_incomplete_prerequisites(session_id, new_index)
            
            state["current_concept_index"] = new_index
            state = lesson_node(state, show_warning=bool(incomplete_prereqs), skipped_prereqs=incomplete_prereqs)
            response_messages.extend(state["messages"][1:])
            
            return {
                "messages": [{"role": "assistant", "content": m.content} for m in response_messages if isinstance(m, AIMessage)],
                "phase": state["phase"],
                "mastery": store.get_mastery(session_id),
                "current_concept": get_current_concept_id(state)
            }
        
        # Check for "go back" command
        if "go back" in user_msg_lower and phase != "quiz":
            if concept_index > 0:
                # Find first incomplete prerequisite, or just go back one
                incomplete = get_incomplete_prerequisites(session_id, concept_index)
                if incomplete:
                    new_index = get_concept_index(incomplete[0])
                else:
                    new_index = concept_index - 1
                
                state["current_concept_index"] = new_index
                state = lesson_node(state)
                response_messages.extend(state["messages"][1:])
            else:
                response_messages.append(AIMessage(content="You're already at the first concept! Ask questions or say 'quiz me'."))
            
            return {
                "messages": [{"role": "assistant", "content": m.content} for m in response_messages if isinstance(m, AIMessage)],
                "phase": state["phase"],
                "mastery": store.get_mastery(session_id),
                "current_concept": get_current_concept_id(state)
            }
        
        # ==================== Q&A PHASE ====================
        if phase == "qa":
            quiz_triggers = ["quiz me", "test me", "i'm ready", "im ready", "ready", 
                           "let's practice", "lets practice", "practice", "quiz"]
            wants_quiz = any(trigger in user_msg_lower for trigger in quiz_triggers)
            
            if wants_quiz:
                state = quiz_node(state)
                response_messages.extend(state["messages"][1:])
            else:
                state = qa_node(state)
                response_messages.append(state["messages"][-1])
        
        # ==================== QUIZ PHASE ====================
        elif phase == "quiz":
            questions = store.get_quiz_questions(session_id)
            current_idx = store.get_quiz_current_index(session_id)
            
            if current_idx < len(questions):
                state["current_question"] = questions[current_idx]
            
            state = process_quiz_answer_node(state)
            response_messages.extend(state["messages"][1:])
        
        # ==================== EVALUATE PHASE ====================
        elif phase == "evaluate":
            continue_triggers = ["continue", "next", "move on", "proceed", "yes"]
            retry_triggers = ["retry", "try again", "again", "quiz me", "practice"]
            
            can_advance = store.get_can_advance(session_id)
            
            if can_advance and any(t in user_msg_lower for t in continue_triggers):
                new_index = concept_index + 1
                if new_index < len(CONCEPT_ORDER):
                    state["current_concept_index"] = new_index
                    state = lesson_node(state)
                    response_messages.extend(state["messages"])
                else:
                    state["phase"] = "complete"
                    response_messages.append(AIMessage(content="🎓 You've completed all concepts! Amazing work!"))
            elif any(t in user_msg_lower for t in retry_triggers):
                store.set_phase(session_id, "qa")
                state["phase"] = "qa"
                state = quiz_node(state)
                response_messages.extend(state["messages"][1:])
            else:
                # Treat as Q&A
                store.set_phase(session_id, "qa")
                state["phase"] = "qa"
                state = qa_node(state)
                response_messages.append(state["messages"][-1])
        
        # ==================== COMPLETE PHASE ====================
        elif phase == "complete":
            response_messages.append(AIMessage(
                content="🎓 You've completed the course! Feel free to ask questions for review, or say a concept name to revisit it."
            ))
        
        # ==================== LESSON PHASE ====================
        elif phase == "lesson":
            store.set_phase(session_id, "qa")
            state = qa_node(state)
            response_messages.append(state["messages"][-1])
        
        final_mastery = store.get_mastery(session_id)
        
        return {
            "messages": [{"role": "assistant", "content": m.content} for m in response_messages if isinstance(m, AIMessage)],
            "phase": state["phase"],
            "mastery": final_mastery,
            "current_concept": get_current_concept_id(state)
        }


# Create global agent instance
agent = TutorAgent()