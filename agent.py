

import os
from typing import TypedDict, Literal, Optional, List, Annotated
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
    current_question: Optional[dict]  # Current question being asked
    mastery: dict  # concept_id -> score
    weak_concepts: List[str]  # Concepts with low mastery
    root_cause: Optional[str]  # The identified root cause concept
    teaching_turns: int  # Count of teaching exchanges


# ==================== Initialize Components ====================

kg = KnowledgeGraph()
store = RedisStore()
llm = ChatOpenAI(
    model="gpt-4o-mini",  # Fast and cheap, good for hackathon
    temperature=0.7
)


# ==================== Node Functions ====================

def diagnostic_node(state: AgentState) -> AgentState:
    """
    Ask diagnostic questions to assess student's knowledge.
    
    Picks one medium-difficulty question from each concept.
    After 5 questions, moves to analyzing phase.
    """
    session_id = state["session_id"]
    questions_asked = store.get_questions_asked(session_id)
    
    # Get diagnostic question set
    diagnostic_set = kg.get_diagnostic_set()
    
    if questions_asked < len(diagnostic_set):
        # Get next question
        question = diagnostic_set[questions_asked]
        
        # Format question for display
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
    
    # Get the last human message (the answer)
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return state
    
    answer = last_message.content.strip().upper()
    
    # Convert A/B/C/D to index
    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    answer_idx = answer_map.get(answer, -1)
    
    # Check if correct
    is_correct = (answer_idx == question["correct"])
    concept_id = question["concept_id"]
    
    # Update mastery in Redis
    new_score = store.update_mastery(session_id, concept_id, is_correct)
    state["mastery"][concept_id] = new_score
    
    # Record answer
    store.record_answer(session_id, question["id"], concept_id, is_correct)
    store.increment_questions_asked(session_id)
    
    # Feedback message
    if is_correct:
        feedback = f"✅ Correct!"
    else:
        correct_option = chr(65 + question["correct"])
        feedback = f"❌ Incorrect. The answer was **{correct_option}**.\n\n💡 *{question['hint']}*"
    
    state["messages"].append(AIMessage(content=feedback))
    state["current_question"] = None
    
    return state


def analyze_node(state: AgentState) -> AgentState:
    """
    Analyze diagnostic results and find root cause.
    
    Uses the knowledge graph to trace back from weak concepts
    to find the earliest prerequisite that's weak.
    """
    session_id = state["session_id"]
    mastery = state["mastery"]
    
    # Find weak concepts (mastery < 0.6)
    weak_concepts = [c for c, score in mastery.items() if score < 0.6]
    state["weak_concepts"] = weak_concepts
    
    if not weak_concepts:
        # All concepts strong! Skip to complete
        state["messages"].append(AIMessage(content="🎉 **Excellent!** You've demonstrated strong understanding across all concepts!"))
        state["phase"] = "complete"
        store.set_phase(session_id, "complete")
        return state
    
    # Find the root cause - trace back to earliest weak prerequisite
    # Start from the most advanced weak concept
    most_advanced_weak = weak_concepts[-1]  # Last in topological order
    root_cause = kg.trace_root_cause(most_advanced_weak, mastery)
    
    state["root_cause"] = root_cause
    store.set_root_cause(session_id, root_cause)
    
    # Get concept name for display
    concept_data = kg.get_concept(root_cause)
    concept_name = concept_data["name"]
    
    # Analysis message
    analysis_msg = f"""📊 **Diagnosis Complete!**

I've analyzed your responses and found some knowledge gaps.

🔍 **Root Cause Identified:** **{concept_name}**

This is the foundational concept we need to strengthen. Let me help you understand it better through some guided questions."""
    
    state["messages"].append(AIMessage(content=analysis_msg))
    state["phase"] = "teaching"
    state["teaching_turns"] = 0
    store.set_phase(session_id, "teaching")
    
    return state


def teach_node(state: AgentState) -> AgentState:
    """
    Teach the root cause concept.

    FLOW:
    - Turn 0: Show the structured mini-lesson from JSON
    - Turn 1+: Interactive GPT dialogue
    """
    session_id = state["session_id"]
    root_cause = state["root_cause"]
    concept_data = kg.get_concept(root_cause)

    # Get teaching turns from Redis (persisted!)
    teaching_turns = store.get_teaching_turns(session_id)

    # TURN 0: Show the pre-written lesson FIRST
    if teaching_turns == 0:
        lesson = concept_data.get("lesson", concept_data.get("explanation", ""))
        if lesson:
            lesson_with_prompt = lesson + "\n\n---\n💬 *Does this make sense? Ask me anything or say 'yes' to continue.*"
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
- If they say "yes" / "got it" / "makes sense" → Say "Great!" and move on
- If they say "no" / "confused" → Re-explain simpler with a NEW analogy
- If they ask a question (like "what is X?") → Answer it DIRECTLY and simply
- If they attempt an answer → Give feedback, correct gently if needed

RULES:
- Be SHORT (2-3 sentences max)
- Be warm ("Great question!", "Good thinking!")
- Answer questions DIRECTLY - don't deflect with more questions
- Use everyday analogies (spreadsheets, grids, tables)

BAD: "What do you think a matrix is?" (when they asked YOU)
GOOD: "A matrix is just a table of numbers, like a spreadsheet! Each cell has a value."
"""

    gpt_messages = [SystemMessage(content=system_prompt)]

    # Add recent conversation history
    for msg in state["messages"][-6:]:
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
    Verify understanding with a question on the root cause concept.
    
    Asks an easy question first, then medium if they get it right.
    """
    root_cause = state["root_cause"]
    mastery = state["mastery"]
    current_score = mastery.get(root_cause, 0.5)
    
    # Pick difficulty based on current mastery
    if current_score < 0.4:
        difficulty = 1  # Easy
    else:
        difficulty = 2  # Medium
    
    questions = kg.get_questions(root_cause, difficulty=difficulty)
    
    if questions:
        question = questions[0]
        
        options_text = "\n".join([
            f"  {chr(65+i)}. {opt}" 
            for i, opt in enumerate(question["options"])
        ])
        
        message = f"""📝 **Let's check your understanding!**

{question['text']}

{options_text}"""
        
        state["messages"].append(AIMessage(content=message))
        state["current_question"] = question
    
    return state


def process_verify_answer_node(state: AgentState) -> AgentState:
    """
    Process answer to verification question.
    
    Updates mastery and decides whether to continue teaching
    or mark as complete.
    """
    session_id = state["session_id"]
    question = state["current_question"]
    root_cause = state["root_cause"]
    
    if not question:
        return state
    
    # Get the answer
    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return state
    
    answer = last_message.content.strip().upper()
    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    answer_idx = answer_map.get(answer, -1)
    
    is_correct = (answer_idx == question["correct"])
    
    # Update mastery
    new_score = store.update_mastery(session_id, root_cause, is_correct)
    state["mastery"][root_cause] = new_score
    
    # Record answer
    store.record_answer(session_id, question["id"], root_cause, is_correct)
    
    if is_correct:
        state["messages"].append(AIMessage(content=f"✅ **Correct!** Great job! Your mastery of {kg.get_concept(root_cause)['name']} is now at {new_score:.0%}."))
    else:
        correct_option = chr(65 + question["correct"])
        state["messages"].append(AIMessage(content=f"❌ Not quite. The answer was **{correct_option}**.\n\n{question['explanation']}"))
    
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
    
    # Add nodes
    graph.add_node("diagnostic", diagnostic_node)
    graph.add_node("process_answer", process_answer_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("teach", teach_node)
    graph.add_node("verify", verify_node)
    graph.add_node("process_verify_answer", process_verify_answer_node)
    
    # Set entry point
    graph.set_entry_point("diagnostic")
    
    # Add edges
    graph.add_edge("diagnostic", "wait_for_input")
    graph.add_edge("process_answer", "route_diagnostic")
    
    # Conditional routing after diagnostic
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
    
    # Conditional routing after verify
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
        self.graph = None  # Lazy initialization
    
    def _ensure_graph(self):
        """Initialize graph if needed."""
        if self.graph is None:
            self.graph = create_agent_graph()
    
    def start_session(self, session_id: str) -> dict:
        """
        Start a new tutoring session.
        
        Returns the first diagnostic question.
        """
        # Create session in Redis
        session_data = store.get_or_create_session(session_id)
        
        # Initialize state
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
        
        # Run diagnostic node to get first question
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
        
        Args:
            session_id: Session identifier
            user_message: The user's input
            
        Returns:
            Dict with messages, phase, mastery, etc.
        """
        # Get session state from Redis
        session_data = store.get_or_create_session(session_id)
        phase = store.get_phase(session_id)
        root_cause = store.get_root_cause(session_id)
        
        # Build current state
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
        
        # Route based on phase
        if phase == "diagnostic":
            # Get current question from diagnostic set
            questions_asked = store.get_questions_asked(session_id)
            diagnostic_set = kg.get_diagnostic_set()
            
            if questions_asked < len(diagnostic_set):
                state["current_question"] = diagnostic_set[questions_asked]
            
            # Process answer
            state = process_answer_node(state)
            response_messages.extend(state["messages"][1:])  # Skip the human message
            
            # Check if we should analyze
            questions_asked = store.get_questions_asked(session_id)
            
            if questions_asked >= 5:
                # Move to analysis
                state["mastery"] = store.get_mastery(session_id)
                state = analyze_node(state)
                response_messages.extend(state["messages"][len(response_messages)+1:])
                
                if state["phase"] == "teaching":
                    # Start teaching
                    state = teach_node(state)
                    response_messages.append(state["messages"][-1])
            else:
                # Next diagnostic question
                state = diagnostic_node(state)
                response_messages.append(state["messages"][-1])
        
        elif phase == "teaching":
            # Process teaching dialogue
            state = teach_node(state)
            response_messages.append(state["messages"][-1])

            # Check if we should move to verification (after 3+ teaching exchanges)
            teaching_turns = store.get_teaching_turns(session_id)

            if teaching_turns >= 3:
                # Move to verify
                store.set_phase(session_id, "verifying")
                state = verify_node(state)
                response_messages.append(state["messages"][-1])
                state["phase"] = "verifying"
            # else: stay in teaching phase, wait for more dialogue
        
        elif phase == "verifying":
            # Get the verification question
            mastery = store.get_mastery(session_id)
            current_score = mastery.get(root_cause, 0.5)
            difficulty = 1 if current_score < 0.4 else 2
            questions = kg.get_questions(root_cause, difficulty=difficulty)
            
            if questions:
                state["current_question"] = questions[0]
            
            # Process answer
            state = process_verify_answer_node(state)
            response_messages.extend(state["messages"][1:])
            
            # Check mastery
            new_mastery = store.get_mastery(session_id)
            
            if new_mastery.get(root_cause, 0) >= 0.6:
                # Complete!
                store.set_phase(session_id, "complete")
                response_messages.append(AIMessage(content=f"🎉 **Congratulations!** You've mastered **{kg.get_concept(root_cause)['name']}**! The knowledge gap has been filled."))
                state["phase"] = "complete"
            else:
                # Back to teaching
                store.set_phase(session_id, "teaching")
                state["phase"] = "teaching"
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