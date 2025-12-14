"""
Socratic Tutor - LLM-based teaching with Socratic method.

Features:
    - Context-aware prompts with concept data
    - Socratic questioning (guide, don't tell)
    - Misconception-aware responses
    - Adaptive tone based on student state
"""

import os
from typing import List, Dict, Optional
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


@dataclass
class TutorContext:
    """Context for tutor conversation."""
    concept_id: str
    concept_name: str
    lesson: str
    misconceptions: List[str]
    mastery: float
    streak: int
    teaching_turns: int


class SocraticTutor:
    """
    Socratic tutoring using LLM with context injection.

    Philosophy:
    - Ask questions to lead student to understanding
    - Never give answers directly (unless stuck)
    - Celebrate correct thinking
    - Gently correct misconceptions
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7):
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        self.conversation_history: List = []

    def create_system_prompt(self, context: TutorContext) -> str:
        """Create context-aware system prompt."""
        # Adjust tone based on mastery
        if context.mastery < 0.3:
            tone = "extra patient and encouraging. Break things down into tiny steps."
        elif context.mastery < 0.5:
            tone = "supportive and clear. Use simple analogies."
        elif context.mastery < 0.7:
            tone = "conversational and engaging. Challenge them a bit."
        else:
            tone = "peer-like and intellectually stimulating. Push for deeper understanding."

        # Streak-based encouragement
        if context.streak >= 3:
            encouragement = "The student is on a streak! Acknowledge their momentum."
        elif context.streak == 0 and context.teaching_turns > 2:
            encouragement = "The student may be struggling. Be extra supportive."
        else:
            encouragement = ""

        # Misconception awareness
        misconception_section = ""
        if context.misconceptions:
            misconception_section = f"""
COMMON MISCONCEPTIONS TO WATCH FOR:
{chr(10).join(f'• {m}' for m in context.misconceptions)}

If you detect any of these, gently address them without making the student feel bad."""

        return f"""You are a Socratic tutor teaching **{context.concept_name}**.

YOUR TEACHING PHILOSOPHY (Socratic Method):
1. **Ask, don't tell** - Guide with questions, not answers
2. **Build on their knowledge** - Connect new ideas to what they know
3. **Celebrate thinking** - Praise the process, not just correct answers
4. **Make it concrete** - Use real examples with actual numbers
5. **One step at a time** - Don't overwhelm

CURRENT LESSON:
---
{context.lesson}
---

YOUR TONE: Be {tone}
{encouragement}
{misconception_section}

RESPONSE PATTERNS:

If they say "yes" / "got it" / "makes sense":
→ "Great! Let's test that understanding. [Follow-up question about the concept]"

If they say "no" / "confused" / "don't understand":
→ Use a DIFFERENT analogy
→ Break into smaller steps
→ Ask: "What part is confusing - X or Y?"
→ Give a concrete example with numbers

If they ask a specific question:
→ Instead of answering directly, ask a guiding question back
→ "What do you think would happen if...?"
→ Only give the answer if they're truly stuck after 2-3 attempts

If they give a wrong answer:
→ Don't say "wrong" - say "Interesting! Let's think about that..."
→ Ask them to explain their reasoning
→ Guide them to discover the error themselves

FORMATTING:
- Use **bold** for key terms
- Use bullet points for lists
- NO LaTeX - write math as plain text: "det = ad - bc"
- Matrices as: [[a, b], [c, d]]
- Keep responses focused - one main idea at a time

IMPORTANT: You are here to TEACH, not to quiz. Ask questions that lead to understanding, not trick questions."""

    def respond(self, user_message: str, context: TutorContext) -> str:
        """Generate a Socratic response."""
        system_prompt = self.create_system_prompt(context)

        messages = [SystemMessage(content=system_prompt)]

        # Add conversation history (last 8 messages)
        for msg in self.conversation_history[-8:]:
            messages.append(msg)

        # Add current message
        messages.append(HumanMessage(content=user_message))

        # Generate response
        response = self.llm.invoke(messages)

        # Update history
        self.conversation_history.append(HumanMessage(content=user_message))
        self.conversation_history.append(AIMessage(content=response.content))

        return response.content

    def generate_guiding_question(self, concept_name: str, lesson: str,
                                   student_statement: str) -> str:
        """Generate a Socratic guiding question based on student's statement."""
        prompt = f"""The student is learning about "{concept_name}".

They just said: "{student_statement}"

Generate ONE Socratic question that:
1. Acknowledges what they said
2. Guides them toward deeper understanding
3. Makes them think without giving the answer

Respond with ONLY the question, nothing else."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return response.content

    def explain_misconception(self, misconception_description: str,
                               correct_concept: str) -> str:
        """Generate a gentle explanation for a misconception."""
        prompt = f"""A student has this misconception: "{misconception_description}"

The correct understanding is: "{correct_concept}"

Generate a gentle, Socratic response that:
1. Doesn't make them feel bad
2. Acknowledges why the misconception is understandable
3. Uses a concrete example to show the correct way
4. Ends with a question to check understanding

Keep it under 100 words."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return response.content

    def generate_celebration(self, concept_name: str, streak: int) -> str:
        """Generate an encouraging message for correct answers."""
        if streak >= 5:
            intensity = "very enthusiastic"
        elif streak >= 3:
            intensity = "enthusiastic"
        else:
            intensity = "warmly encouraging"

        prompt = f"""The student just got a {concept_name} question correct.
They're on a streak of {streak} correct answers.

Generate a {intensity} one-line celebration.
Be genuine, not cheesy. Vary your responses."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return response.content

    def reset_conversation(self):
        """Reset conversation history for new concept/session."""
        self.conversation_history = []

    # ==================== Preset Responses ====================

    def get_lesson_intro(self, context: TutorContext) -> str:
        """Generate an engaging lesson introduction."""
        prompt = f"""You're introducing the concept "{context.concept_name}" to a student.

The lesson content is:
{context.lesson}

Generate a brief, engaging introduction (2-3 sentences) that:
1. Hooks their interest
2. Connects to something they might already know
3. Ends with an engaging question

Don't include the full lesson - just introduce it."""

        messages = [
            SystemMessage(content="You are a warm, engaging tutor. Be concise and interesting."),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        return response.content

    def get_hint(self, question_text: str, concept_name: str) -> str:
        """Generate a Socratic hint for a question (not the answer!)."""
        prompt = f"""The student is stuck on this question about {concept_name}:
"{question_text}"

Generate a Socratic HINT that:
1. Points them in the right direction
2. Does NOT give the answer
3. Asks a simpler question that leads to the answer

Keep it to 1-2 sentences."""

        messages = [HumanMessage(content=prompt)]
        response = self.llm.invoke(messages)
        return response.content
