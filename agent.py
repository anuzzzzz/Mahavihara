"""
LangGraph Agent for Mahavihara AI Tutor

Implements a state machine with phases:
    diagnostic -> analyzing -> teaching -> verifying -> complete
    
Key Features:
    - Diagnoses knowledge gaps through 5 questions
    - Traces root cause through knowledge graph
    - Teaches using structured lessons + GPT dialogue
    - Verifies with UNSEEN questions (no memorization)
    - Handles MULTIPLE weak concepts in queue
"""

import os
import random
from typing import TypedDict, Literal, Optional, List
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
    phase: Literal["diagnostic", "analyzing", "teaching", "verifying", "complete"]
    messages: List  # Chat history
    current_question: Optional[dict]
    mastery: dict  # concept_id -> score
    weak_concepts: List[str]
    root_cause: Optional[str]
    teaching_turns: int


# ==================== Initialize Components ====================

kg = KnowledgeGraph()
store = RedisStore()
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7
)


# ==================== Node Functions ====================

def diagnostic_node(state: AgentState) -> AgentState:
    """
    Ask diagnostic questions to assess student's knowledge.
    One medium-difficulty question from each concept.
    """
    session_id = state["session_id"]
    questions_asked = store.get_questions_asked(session_id)
    
    diagnostic_set = kg.get_diagnostic_set()
    
    if questions_asked < len(diagnostic_set):
        question = diagnostic_set[questions_asked]
        
        options_text = "\n".join([
            f"  {chr(65+i)}. {opt}" 
            for i, opt in enumerate(question["options"])
        ])
        
        message = f"**Question {questions_asked + 1}/5** ({question['concept_id'].replace('_', ' ').title()})\n\n{question['text']}\n\n{options_text}"
        
        state["messages"].append(AIMessage(content=message))
        state["current_question"] = question
        
    return state


def process_answer_node(state: AgentState) -> AgentState:
    """
    Process the student's answer to a diagnostic question.
    Updates mastery scores and records the answer.
    """
    session_id = state["session_id"]
    question = state["current_question"]
    
    if not question:
        return state
    
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return state
    
    answer = last_message.content.strip().upper()
    
    # Handle answers like "A" or "a" or "A." or "Option A"
    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    answer_idx = -1
    for key in answer_map:
        if key in answer.upper():
            answer_idx = answer_map[key]
            break
    
    is_correct = (answer_idx == question["correct"])
    concept_id = question["concept_id"]
    
    new_score = store.update_mastery(session_id, concept_id, is_correct)
    state["mastery"][concept_id] = new_score
    
    store.record_answer(session_id, question["id"], concept_id, is_correct)
    store.increment_questions_asked(session_id)
    
    if is_correct:
        feedback = "✅ Correct!"
    else:
        correct_option = chr(65 + question["correct"])
        feedback = f"❌ Incorrect. The answer was **{correct_option}**.\n\n💡 *{question['hint']}*"
    
    state["messages"].append(AIMessage(content=feedback))
    state["current_question"] = None
    
    return state


def analyze_node(state: AgentState) -> AgentState:
    """
    Analyze diagnostic results and find ALL weak concepts.
    Queues them for sequential teaching.
    """
    session_id = state["session_id"]
    mastery = state["mastery"]
    
    # Find ALL weak concepts (mastery < 0.6)
    weak_concepts = [c for c, score in mastery.items() if score < 0.6]
    state["weak_concepts"] = weak_concepts
    
    if not weak_concepts:
        state["messages"].append(AIMessage(content="🎉 **Excellent!** You've demonstrated strong understanding across all concepts!"))
        state["phase"] = "complete"
        store.set_phase(session_id, "complete")
        return state
    
    # Store ALL weak concepts in queue for sequential teaching
    store.set_weak_concepts_queue(session_id, weak_concepts)
    
    # Find root cause (earliest weak prerequisite)
    most_advanced_weak = weak_concepts[-1]
    root_cause = kg.trace_root_cause(most_advanced_weak, mastery)
    
    state["root_cause"] = root_cause
    store.set_root_cause(session_id, root_cause)
    store.reset_teaching_turns(session_id)
    store.reset_verify_progress(session_id)
    
    concept_data = kg.get_concept(root_cause)
    concept_name = concept_data["name"]
    
    # Show count of weak concepts
    if len(weak_concepts) > 1:
        analysis_msg = f"""📊 **Diagnosis Complete!**

I've analyzed your responses and found **{len(weak_concepts)} knowledge gaps**.

🔍 **Starting with:** **{concept_name}**

This is the foundational concept we need to strengthen first. After mastering this, we'll move to the next."""
    else:
        analysis_msg = f"""📊 **Diagnosis Complete!**

I've analyzed your responses and found a knowledge gap.

🔍 **Root Cause Identified:** **{concept_name}**

Let me help you understand this concept better."""
    
    state["messages"].append(AIMessage(content=analysis_msg))
    state["phase"] = "teaching"
    state["teaching_turns"] = 0
    store.set_phase(session_id, "teaching")
    
    return state


def teach_node(state: AgentState) -> AgentState:
    """
    Teach the root cause concept.
    
    FLOW:
    - Turn 0: Show structured mini-lesson from JSON
    - Turn 1+: Interactive GPT dialogue with DETAILED explanations
    """
    session_id = state["session_id"]
    root_cause = state["root_cause"]
    concept_data = kg.get_concept(root_cause)
    
    teaching_turns = store.get_teaching_turns(session_id)
    
    # TURN 0: Show pre-written lesson FIRST
    if teaching_turns == 0:
        lesson = concept_data.get("lesson", concept_data.get("explanation", ""))
        if lesson:
            lesson_with_prompt = lesson + "\n\n---\n💬 *Does this make sense? Ask me anything, or say \"quiz me\" when you're ready to practice!*"
            state["messages"].append(AIMessage(content=lesson_with_prompt))
            store.increment_teaching_turns(session_id)
            return state
    
    # TURN 1+: Interactive GPT dialogue
    system_prompt = f"""You are a warm, encouraging tutor helping a student understand "{concept_data['name']}".

The student has already read this lesson:
---
{concept_data.get('lesson', concept_data['explanation'])}
---

HOW TO RESPOND:

**If they say "yes" / "got it" / "makes sense" / "okay":**
→ Brief response: "Great! Feel free to ask questions, or say 'quiz me' when you're ready to practice!"

**If they say "no" / "confused" / "don't understand" / "what?" / "huh?":**
→ Give a DETAILED explanation:
  - Start with a completely different analogy (everyday objects like spreadsheets, arrows, shadows, stretching rubber)
  - Break it down step-by-step
  - Give a concrete example with actual numbers
  - Explain WHY it works that way, not just WHAT it is
  - End by asking if this new explanation helps

**If they ask a specific question like "what is X?" or "why does Y happen?" or "how do I Z?":**
→ Give a THOROUGH answer:
  - First, directly answer their question in simple terms
  - Then explain the concept in more depth
  - Provide 1-2 concrete examples with numbers
  - Connect it to concepts they already know
  - If relevant, show the formula and explain each part

**If they attempt an answer or share their thinking:**
→ Acknowledge their effort warmly
→ If correct: celebrate and reinforce why they're right
→ If incorrect: gently correct with a clear explanation of the right answer

IMPORTANT GUIDELINES:
- Be warm and encouraging throughout ("Great question!", "That's a really common confusion!", "Good thinking!")
- Use everyday analogies they can visualize (spreadsheets, arrows, stretching, shadows, transformations)
- Build from simple → complex
- Use **bold** for key terms
- Use concrete numbers in examples (don't say "some matrix", say "[[2,0],[0,3]]")

RESPONSE LENGTH:
- BRIEF for simple confirmations ("Great!", "Exactly right!")
- DETAILED (multiple paragraphs) for explanations, questions, and confusion
- Don't be afraid to write 4-6 paragraphs if they're genuinely confused

FORMATTING:
- Use **bold** for emphasis and key terms
- Use bullet points (•) or dashes (-) for lists
- Do NOT use LaTeX (\\[ \\] or $ $) - it won't render
- Write math inline as plain text: "det = ad - bc" not "\\det = ad - bc"
- For matrices, use simple notation: [[a, b], [c, d]] or write them out
- Use → for arrows and = for equations

NEVER:
- Never deflect with "What do you think?" when they asked YOU a question
- Never give vague answers like "it depends" without explaining what it depends on
- Never assume they understand jargon - define terms when you use them"""

    gpt_messages = [SystemMessage(content=system_prompt)]
    
    for msg in state["messages"][-8:]:  # Increased context window
        if isinstance(msg, HumanMessage):
            gpt_messages.append(msg)
        elif isinstance(msg, AIMessage):
            gpt_messages.append(msg)
    
    response = llm.invoke(gpt_messages)
    state["messages"].append(AIMessage(content=response.content))
    store.increment_teaching_turns(session_id)
    
    return state


def verify_node(state: AgentState) -> AgentState:
    """
    Verify understanding with a question the student HASN'T seen.
    Picks difficulty based on current mastery.
    """
    session_id = state["session_id"]
    root_cause = state["root_cause"]
    mastery = state["mastery"]
    current_score = mastery.get(root_cause, 0.5)
    
    # Get questions already asked
    asked_ids = store.get_asked_questions(session_id)
    
    # Pick difficulty based on mastery
    if current_score < 0.4:
        preferred_difficulty = 1  # Easy
    elif current_score < 0.6:
        preferred_difficulty = 2  # Medium
    else:
        preferred_difficulty = 3  # Hard
    
    # Get a random UNSEEN question
    question = kg.get_random_unseen_question(root_cause, asked_ids, preferred_difficulty)
    
    if question:
        options_text = "\n".join([
            f"  {chr(65+i)}. {opt}" 
            for i, opt in enumerate(question["options"])
        ])
        
        message = f"""📝 **Let's check your understanding!**

{question['text']}

{options_text}"""
        
        state["messages"].append(AIMessage(content=message))
        state["current_question"] = question
    else:
        # No questions available (shouldn't happen)
        state["messages"].append(AIMessage(content="Great progress! Let's continue learning."))
    
    return state


def process_verify_answer_node(state: AgentState) -> AgentState:
    """
    Process answer to verification question.
    Updates mastery and decides next step.
    """
    session_id = state["session_id"]
    question = state["current_question"]
    root_cause = state["root_cause"]
    
    if not question:
        return state
    
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return state
    
    answer = last_message.content.strip().upper()
    
    # Parse answer
    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    answer_idx = -1
    for key in answer_map:
        if key in answer.upper():
            answer_idx = answer_map[key]
            break
    
    is_correct = (answer_idx == question["correct"])
    
    new_score = store.update_mastery(session_id, root_cause, is_correct)
    state["mastery"][root_cause] = new_score
    
    store.record_answer(session_id, question["id"], root_cause, is_correct)
    
    concept_name = kg.get_concept(root_cause)['name']
    
    if is_correct:
        state["messages"].append(AIMessage(content=f"✅ **Correct!** Great job! Your mastery of {concept_name} is now at {new_score:.0%}."))
    else:
        correct_option = chr(65 + question["correct"])
        state["messages"].append(AIMessage(content=f"❌ Not quite. The answer was **{correct_option}**.\n\n💡 {question['explanation']}"))
    
    state["current_question"] = None
    
    return state


# ==================== Routing Functions ====================

def route_after_diagnostic(state: AgentState) -> str:
    """Decide next step after diagnostic question."""
    session_id = state["session_id"]
    questions_asked = store.get_questions_asked(session_id)
    
    if questions_asked >= 5:
        return "analyze"
    return "diagnostic"


def route_after_teaching(state: AgentState) -> str:
    """Decide whether to verify or continue teaching."""
    if state["teaching_turns"] >= 2:
        return "verify"
    return "wait_for_input"


def route_after_verify(state: AgentState) -> str:
    """Decide whether teaching is complete or needs more work."""
    root_cause = state["root_cause"]
    mastery = state["mastery"]
    
    if mastery.get(root_cause, 0) >= 0.6:
        return "complete"
    return "teach"


# ==================== Build the Graph ====================

def create_agent_graph():
    """Build and compile the LangGraph state machine."""
    
    graph = StateGraph(AgentState)
    
    graph.add_node("diagnostic", diagnostic_node)
    graph.add_node("process_answer", process_answer_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("teach", teach_node)
    graph.add_node("verify", verify_node)
    graph.add_node("process_verify_answer", process_verify_answer_node)
    
    graph.set_entry_point("diagnostic")
    
    graph.add_edge("diagnostic", "wait_for_input")
    graph.add_edge("process_answer", "route_diagnostic")
    
    graph.add_conditional_edges(
        "route_diagnostic",
        route_after_diagnostic,
        {
            "diagnostic": "diagnostic",
            "analyze": "analyze"
        }
    )
    
    graph.add_edge("analyze", "teach")
    graph.add_edge("teach", "wait_for_input")
    graph.add_edge("verify", "wait_for_input")
    graph.add_edge("process_verify_answer", "route_verify")
    
    graph.add_conditional_edges(
        "route_verify",
        route_after_verify,
        {
            "complete": END,
            "teach": "teach"
        }
    )
    
    return graph.compile()


# ==================== Agent Interface ====================

class TutorAgent:
    """
    High-level interface for the tutor agent.
    Handles session management and message processing.
    """
    
    def __init__(self):
        self.graph = None
    
    def _ensure_graph(self):
        if self.graph is None:
            self.graph = create_agent_graph()
    
    def start_session(self, session_id: str) -> dict:
        """Start a new tutoring session. Returns first diagnostic question."""
        session_data = store.get_or_create_session(session_id)
        
        state = AgentState(
            session_id=session_id,
            phase="diagnostic",
            messages=[],
            current_question=None,
            mastery=session_data["mastery"],
            weak_concepts=[],
            root_cause=None,
            teaching_turns=0
        )
        
        state = diagnostic_node(state)
        
        return {
            "messages": [{"role": "assistant", "content": m.content} for m in state["messages"]],
            "phase": state["phase"],
            "mastery": state["mastery"],
            "current_question": state["current_question"]
        }
    
    def process_message(self, session_id: str, user_message: str) -> dict:
        """
        Process a user message and return the agent's response.
        Main routing logic based on current phase.
        """
        session_data = store.get_or_create_session(session_id)
        phase = store.get_phase(session_id)
        root_cause = store.get_root_cause(session_id)
        
        state = AgentState(
            session_id=session_id,
            phase=phase,
            messages=[HumanMessage(content=user_message)],
            current_question=None,
            mastery=session_data["mastery"],
            weak_concepts=[],
            root_cause=root_cause if root_cause else None,
            teaching_turns=0
        )
        
        response_messages = []
        
        # ==================== DIAGNOSTIC PHASE ====================
        if phase == "diagnostic":
            questions_asked = store.get_questions_asked(session_id)
            diagnostic_set = kg.get_diagnostic_set()
            
            if questions_asked < len(diagnostic_set):
                state["current_question"] = diagnostic_set[questions_asked]
            
            state = process_answer_node(state)
            response_messages.extend(state["messages"][1:])
            
            questions_asked = store.get_questions_asked(session_id)
            
            if questions_asked >= 5:
                state["mastery"] = store.get_mastery(session_id)
                state = analyze_node(state)
                response_messages.extend(state["messages"][len(response_messages)+1:])
                
                if state["phase"] == "teaching":
                    state = teach_node(state)
                    response_messages.append(state["messages"][-1])
            else:
                state = diagnostic_node(state)
                response_messages.append(state["messages"][-1])
        
        # ==================== TEACHING PHASE ====================
        elif phase == "teaching":
            user_msg_lower = user_message.lower().strip()
            
            # Check if student wants to be quizzed
            quiz_triggers = ["quiz me", "test me", "i'm ready", "im ready", "ready", 
                          "let's practice", "lets practice", "check my understanding",
                          "practice", "try a question", "give me a question"]
            wants_quiz = any(trigger in user_msg_lower for trigger in quiz_triggers)
            
            teaching_turns = store.get_teaching_turns(session_id)
            
            if wants_quiz and teaching_turns >= 1:
                # Student requested quiz - go to verify
                store.set_phase(session_id, "verifying")
                store.reset_verify_progress(session_id)
                state = verify_node(state)
                response_messages.append(state["messages"][-1])
                state["phase"] = "verifying"
            else:
                # Continue teaching dialogue
                state = teach_node(state)
                response_messages.append(state["messages"][-1])
                
                # After 5+ turns, gently suggest quiz
                teaching_turns = store.get_teaching_turns(session_id)
                if teaching_turns >= 5 and not wants_quiz:
                    response_messages.append(AIMessage(content="\n💡 *Tip: Say \"quiz me\" when you're ready to test your understanding!*"))
        
        # ==================== VERIFYING PHASE ====================
        elif phase == "verifying":
            mastery = store.get_mastery(session_id)
            current_score = mastery.get(root_cause, 0.5)

            # Get an unseen question
            asked_ids = store.get_asked_questions(session_id)
            difficulty = 1 if current_score < 0.4 else 2
            question = kg.get_random_unseen_question(root_cause, asked_ids, difficulty)

            if question:
                state["current_question"] = question

            state = process_verify_answer_node(state)
            response_messages.extend(state["messages"][1:])

            # Get verification progress and update
            verify_progress = store.get_verify_progress(session_id)
            last_answer_correct = state["mastery"].get(root_cause, 0) > current_score
            store.update_verify_progress(session_id, last_answer_correct)

            questions_asked = verify_progress["asked"] + 1
            correct_count = verify_progress["correct"] + (1 if last_answer_correct else 0)

            REQUIRED_QUESTIONS = 3
            REQUIRED_CORRECT = 2

            if questions_asked < REQUIRED_QUESTIONS:
                # Ask another verification question
                response_messages.append(AIMessage(
                    content=f"*({correct_count}/{questions_asked} correct so far)*"
                ))
                state = verify_node(state)
                response_messages.append(state["messages"][-1])
            else:
                # 3 questions answered - evaluate
                store.reset_verify_progress(session_id)

                if correct_count >= REQUIRED_CORRECT:
                    # PASSED! Check if more concepts in queue
                    weak_queue = store.get_weak_concepts_queue(session_id)

                    # Remove current concept from queue
                    if root_cause in weak_queue:
                        weak_queue.remove(root_cause)
                        store.set_weak_concepts_queue(session_id, weak_queue)

                    if weak_queue:
                        # More concepts to learn!
                        next_concept = weak_queue[0]
                        store.set_root_cause(session_id, next_concept)
                        store.reset_teaching_turns(session_id)
                        store.set_phase(session_id, "teaching")

                        concept_name = kg.get_concept(next_concept)["name"]
                        mastered_name = kg.get_concept(root_cause)["name"]

                        response_messages.append(AIMessage(
                            content=f"🎉 **Great job!** You got {correct_count}/3 correct and mastered **{mastered_name}**!\n\n📚 **Next up:** **{concept_name}**\n\n*{len(weak_queue)} concept(s) remaining*"
                        ))

                        # Start teaching next concept
                        state["root_cause"] = next_concept
                        state = teach_node(state)
                        response_messages.append(state["messages"][-1])
                        state["phase"] = "teaching"
                    else:
                        # All done!
                        store.set_phase(session_id, "complete")
                        response_messages.append(AIMessage(
                            content=f"🎉 **Congratulations!** You got {correct_count}/3 correct and mastered all the concepts! Your knowledge gaps have been filled. 🏆"
                        ))
                        state["phase"] = "complete"
                else:
                    # FAILED - back to teaching
                    store.set_phase(session_id, "teaching")
                    state["phase"] = "teaching"

                    response_messages.append(AIMessage(
                        content=f"📚 You got {correct_count}/3 correct. Let's review this concept a bit more before trying again."
                    ))

                    store.reset_teaching_turns(session_id)
                    state = teach_node(state)
                    response_messages.append(state["messages"][-1])
        
        # Get updated mastery
        final_mastery = store.get_mastery(session_id)
        
        return {
            "messages": [{"role": "assistant", "content": m.content} for m in response_messages if isinstance(m, AIMessage)],
            "phase": state["phase"],
            "mastery": final_mastery,
            "root_cause": state.get("root_cause")
        }


# Create global agent instance
agent = TutorAgent()