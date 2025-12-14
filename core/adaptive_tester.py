"""
Adaptive Tester - Computerized Adaptive Testing (CAT).

Features:
    - Dynamic question selection based on ability
    - Maximum Information criterion
    - Stopping rules (SE threshold, max questions)
    - Progressive difficulty within quizzes
"""

import math
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .student_model import StudentModel
from .knowledge_graph import KnowledgeGraph


@dataclass
class QuestionCandidate:
    """A question candidate with its selection metrics."""
    question: dict
    concept_id: str
    difficulty: float
    information: float  # Fisher information at current ability


class AdaptiveTester:
    """
    Computerized Adaptive Testing implementation.

    Selects questions to maximize information about student ability.
    Uses Item Response Theory for question selection.
    """

    # Stopping criteria
    MAX_QUESTIONS = 20
    MIN_QUESTIONS = 5
    SE_THRESHOLD = 0.3  # Stop when standard error is below this

    # Question selection
    DIFFICULTY_RANGE = 1.5  # Only consider questions within this range of ability

    def __init__(self, knowledge_graph: KnowledgeGraph, student_model: StudentModel):
        self.kg = knowledge_graph
        self.model = student_model
        self.asked_ids: List[str] = []
        self.responses: List[dict] = []

    # ==================== Question Selection ====================

    def select_next_question(self, concept_id: str,
                             strategy: str = "maximum_information") -> Optional[dict]:
        """
        Select the next optimal question.

        Strategies:
            - maximum_information: Pick question with highest Fisher information
            - progressive: Easy → Medium → Hard
            - random: Random from unseen questions
        """
        if strategy == "maximum_information":
            return self._select_max_info(concept_id)
        elif strategy == "progressive":
            return self._select_progressive(concept_id)
        else:
            return self._select_random(concept_id)

    def _select_max_info(self, concept_id: str) -> Optional[dict]:
        """Select question with maximum Fisher information."""
        candidates = self._get_candidates(concept_id)
        if not candidates:
            return None

        # Get current ability
        ability = self.model._get_or_create_mastery(concept_id).ability

        # Calculate information for each candidate
        scored = []
        for q in candidates:
            difficulty = self._get_question_difficulty(q)
            info = self._fisher_information(ability, difficulty)
            scored.append(QuestionCandidate(
                question=q,
                concept_id=concept_id,
                difficulty=difficulty,
                information=info
            ))

        # Sort by information (descending)
        scored.sort(key=lambda c: c.information, reverse=True)

        # Add some randomness among top candidates to avoid predictability
        top_n = min(3, len(scored))
        selected = random.choice(scored[:top_n])

        return selected.question

    def _select_progressive(self, concept_id: str) -> Optional[dict]:
        """Select questions in progressive difficulty: Easy → Medium → Hard."""
        num_asked = len([r for r in self.responses if r.get("concept_id") == concept_id])

        # Determine target difficulty based on number asked
        if num_asked < 1:
            target_difficulty = 1  # Easy
        elif num_asked < 2:
            target_difficulty = 2  # Medium
        else:
            target_difficulty = 3  # Hard

        # Get questions at target difficulty
        questions = self.kg.get_unseen_questions(concept_id, self.asked_ids, target_difficulty)

        if questions:
            return random.choice(questions)

        # Fallback to any unseen question
        questions = self.kg.get_unseen_questions(concept_id, self.asked_ids)
        return random.choice(questions) if questions else None

    def _select_random(self, concept_id: str) -> Optional[dict]:
        """Select a random unseen question."""
        questions = self._get_candidates(concept_id)
        return random.choice(questions) if questions else None

    def _get_candidates(self, concept_id: str) -> List[dict]:
        """Get all unseen questions for a concept."""
        return self.kg.get_unseen_questions(concept_id, self.asked_ids)

    # ==================== Information Metrics ====================

    def _fisher_information(self, ability: float, difficulty: float) -> float:
        """
        Calculate Fisher Information for a question.

        I(θ) = P(θ) * (1 - P(θ))

        Maximum information is at P = 0.5 (when ability = difficulty).
        """
        p = self.model.probability_correct(ability, difficulty)
        return p * (1 - p)

    def _get_question_difficulty(self, question: dict) -> float:
        """
        Convert question difficulty (1-3) to IRT scale (-3 to 3).
        """
        diff = question.get("difficulty", 2)

        # Map 1,2,3 to -1, 0, 1
        return (diff - 2)

    # ==================== Response Processing ====================

    def record_response(self, question: dict, concept_id: str, is_correct: bool) -> dict:
        """Record a response and update the model."""
        question_id = question["id"]
        difficulty = self._get_question_difficulty(question)

        # Mark as asked
        self.asked_ids.append(question_id)

        # Update student model
        result = self.model.record_response(
            concept_id=concept_id,
            question_id=question_id,
            difficulty=difficulty,
            is_correct=is_correct
        )

        # Record for analysis
        self.responses.append({
            "question_id": question_id,
            "concept_id": concept_id,
            "is_correct": is_correct,
            "difficulty": difficulty
        })

        return result

    # ==================== Stopping Rules ====================

    def should_stop(self, concept_id: str) -> Tuple[bool, str]:
        """
        Check if testing should stop.

        Returns (should_stop, reason).
        """
        concept_responses = [r for r in self.responses if r.get("concept_id") == concept_id]
        num_asked = len(concept_responses)

        # Minimum questions not reached
        if num_asked < self.MIN_QUESTIONS:
            return False, "min_not_reached"

        # Maximum questions reached
        if num_asked >= self.MAX_QUESTIONS:
            return True, "max_reached"

        # Check standard error
        se = self._estimate_standard_error(concept_id)
        if se < self.SE_THRESHOLD:
            return True, "precision_reached"

        # Check for consistent performance (early stop)
        if num_asked >= 3:
            recent = concept_responses[-3:]
            all_correct = all(r["is_correct"] for r in recent)
            all_wrong = all(not r["is_correct"] for r in recent)

            if all_correct or all_wrong:
                return True, "consistent_performance"

        return False, "continue"

    def _estimate_standard_error(self, concept_id: str) -> float:
        """
        Estimate standard error of ability estimate.

        SE = 1 / sqrt(sum of information)
        """
        concept_responses = [r for r in self.responses if r.get("concept_id") == concept_id]

        if not concept_responses:
            return float('inf')

        ability = self.model._get_or_create_mastery(concept_id).ability

        total_info = sum(
            self._fisher_information(ability, r["difficulty"])
            for r in concept_responses
        )

        if total_info == 0:
            return float('inf')

        return 1.0 / math.sqrt(total_info)

    # ==================== Quiz Generation ====================

    def generate_quiz(self, concept_id: str, num_questions: int = 3,
                      strategy: str = "progressive") -> List[dict]:
        """
        Generate a quiz with specified number of questions.

        Returns list of questions.
        """
        questions = []

        for _ in range(num_questions):
            q = self.select_next_question(concept_id, strategy)
            if q:
                questions.append(q)
                self.asked_ids.append(q["id"])  # Temporarily mark as asked

        return questions

    def get_quiz_result(self) -> dict:
        """Get summary of quiz results."""
        if not self.responses:
            return {"error": "No responses recorded"}

        correct = sum(1 for r in self.responses if r["is_correct"])
        total = len(self.responses)

        return {
            "total_questions": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0,
            "responses": self.responses
        }

    # ==================== State Management ====================

    def reset(self):
        """Reset tester state for new session."""
        self.asked_ids = []
        self.responses = []
