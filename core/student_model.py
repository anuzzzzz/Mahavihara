"""
Student Model - IRT-based ability estimation with forgetting curves.

Features:
    - Item Response Theory (IRT) for ability estimation
    - Ebbinghaus forgetting curves for memory decay
    - Spaced repetition scheduling
    - Mastery tracking per concept
"""

import math
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class ResponseRecord:
    """Record of a student's response to a question."""
    question_id: str
    concept_id: str
    is_correct: bool
    timestamp: float  # Unix timestamp
    difficulty: float  # Question difficulty (b parameter)
    response_time: Optional[float] = None  # Seconds


@dataclass
class ConceptMastery:
    """Mastery state for a single concept."""
    concept_id: str
    ability: float = 0.0  # IRT ability estimate (theta)
    mastery: float = 0.5  # Overall mastery [0, 1]
    last_practiced: float = 0.0  # Unix timestamp
    practice_count: int = 0
    correct_count: int = 0
    streak: int = 0  # Current correct streak


class StudentModel:
    """
    IRT-based student model with forgetting curves.

    Uses 1-Parameter Logistic (1PL/Rasch) model:
        P(correct) = 1 / (1 + exp(-(ability - difficulty)))

    Forgetting curve (Ebbinghaus):
        retention = exp(-time / strength)
    """

    # IRT Parameters
    LEARNING_RATE = 0.3  # How much ability changes per response
    MIN_ABILITY = -3.0
    MAX_ABILITY = 3.0

    # Forgetting Parameters
    BASE_HALF_LIFE = 1.0  # Days until 50% forgotten (before practice)
    HALF_LIFE_GROWTH = 1.5  # Multiplier per successful recall
    MIN_RETENTION = 0.3  # Never forget completely

    # Mastery thresholds
    MASTERY_THRESHOLD = 0.6  # Considered "mastered"
    WEAK_THRESHOLD = 0.4  # Considered "weak"

    def __init__(self):
        self.concepts: Dict[str, ConceptMastery] = {}
        self.responses: List[ResponseRecord] = []

    # ==================== Ability Estimation (IRT) ====================

    def probability_correct(self, ability: float, difficulty: float) -> float:
        """
        1PL IRT model: probability of correct response.

        Args:
            ability: Student ability (theta), typically -3 to 3
            difficulty: Question difficulty (b), typically -3 to 3

        Returns:
            Probability of correct response [0, 1]
        """
        return 1.0 / (1.0 + math.exp(-(ability - difficulty)))

    def update_ability(self, concept_id: str, difficulty: float, is_correct: bool) -> float:
        """
        Update ability estimate after a response.

        Uses gradient descent on log-likelihood.
        """
        mastery = self._get_or_create_mastery(concept_id)
        ability = mastery.ability

        # Expected probability
        p = self.probability_correct(ability, difficulty)

        # Gradient: (observed - expected)
        gradient = (1.0 if is_correct else 0.0) - p

        # Update ability
        new_ability = ability + self.LEARNING_RATE * gradient
        new_ability = max(self.MIN_ABILITY, min(self.MAX_ABILITY, new_ability))

        mastery.ability = new_ability
        return new_ability

    def estimate_difficulty(self, concept_id: str) -> float:
        """
        Estimate question difficulty that gives 50% chance of correct.

        This is the "sweet spot" for learning (zone of proximal development).
        """
        mastery = self._get_or_create_mastery(concept_id)
        return mastery.ability  # In 1PL, optimal difficulty = current ability

    # ==================== Mastery Tracking ====================

    def record_response(self, concept_id: str, question_id: str, difficulty: float,
                        is_correct: bool, response_time: Optional[float] = None) -> Dict:
        """
        Record a response and update all relevant scores.

        Returns dict with updated mastery info.
        """
        now = time.time()
        mastery = self._get_or_create_mastery(concept_id)

        # Record the response
        record = ResponseRecord(
            question_id=question_id,
            concept_id=concept_id,
            is_correct=is_correct,
            timestamp=now,
            difficulty=difficulty,
            response_time=response_time
        )
        self.responses.append(record)

        # Update IRT ability
        new_ability = self.update_ability(concept_id, difficulty, is_correct)

        # Update mastery counts
        mastery.practice_count += 1
        mastery.last_practiced = now

        if is_correct:
            mastery.correct_count += 1
            mastery.streak += 1
        else:
            mastery.streak = 0

        # Recalculate overall mastery
        mastery.mastery = self._calculate_mastery(mastery)

        return {
            "concept_id": concept_id,
            "ability": new_ability,
            "mastery": mastery.mastery,
            "streak": mastery.streak,
            "is_correct": is_correct
        }

    def _calculate_mastery(self, mastery: ConceptMastery) -> float:
        """
        Calculate overall mastery score combining IRT ability and practice.

        Formula combines:
        - Scaled ability (IRT estimate)
        - Recent accuracy
        - Retention (forgetting curve)
        """
        # Scale ability from [-3, 3] to [0, 1]
        ability_score = (mastery.ability + 3) / 6
        ability_score = max(0, min(1, ability_score))

        # Accuracy component
        if mastery.practice_count > 0:
            accuracy = mastery.correct_count / mastery.practice_count
        else:
            accuracy = 0.5

        # Retention component (forgetting curve)
        retention = self._get_retention(mastery)

        # Weighted combination
        # More weight on ability as practice count increases
        practice_weight = min(1.0, mastery.practice_count / 10)

        score = (
            ability_score * 0.4 * practice_weight +
            accuracy * 0.4 +
            retention * 0.2
        )

        # Boost for high practice count
        if mastery.practice_count < 3:
            score *= 0.8  # Penalize low practice

        return max(0.0, min(1.0, score))

    # ==================== Forgetting Curves ====================

    def _get_retention(self, mastery: ConceptMastery) -> float:
        """
        Calculate current retention based on forgetting curve.

        Uses Ebbinghaus curve with strength growing from practice.
        """
        if mastery.last_practiced == 0:
            return 1.0  # Never practiced = full retention (fresh start)

        # Time since last practice (in days)
        days_elapsed = (time.time() - mastery.last_practiced) / 86400

        # Strength grows with successful practice
        strength = self.BASE_HALF_LIFE * (self.HALF_LIFE_GROWTH ** mastery.correct_count)

        # Retention = exp(-time/strength)
        retention = math.exp(-days_elapsed / strength)

        # Apply minimum retention
        return max(self.MIN_RETENTION, retention)

    def get_due_concepts(self, concept_ids: List[str], threshold: float = 0.7) -> List[str]:
        """
        Get concepts that need review (retention dropped below threshold).

        Useful for spaced repetition scheduling.
        """
        due = []
        for cid in concept_ids:
            mastery = self._get_or_create_mastery(cid)
            retention = self._get_retention(mastery)
            if retention < threshold and mastery.practice_count > 0:
                due.append(cid)

        # Sort by retention (lowest first)
        due.sort(key=lambda c: self._get_retention(self._get_or_create_mastery(c)))
        return due

    def get_optimal_review_time(self, concept_id: str, target_retention: float = 0.7) -> float:
        """
        Calculate when to review a concept for optimal retention.

        Returns Unix timestamp.
        """
        mastery = self._get_or_create_mastery(concept_id)

        if mastery.last_practiced == 0:
            return time.time()  # Review now

        # Strength (half-life in days)
        strength = self.BASE_HALF_LIFE * (self.HALF_LIFE_GROWTH ** mastery.correct_count)

        # Time until retention drops to target
        # target = exp(-t/strength)
        # ln(target) = -t/strength
        # t = -strength * ln(target)
        days_until_review = -strength * math.log(target_retention)

        return mastery.last_practiced + (days_until_review * 86400)

    # ==================== State Management ====================

    def _get_or_create_mastery(self, concept_id: str) -> ConceptMastery:
        """Get or create mastery record for a concept."""
        if concept_id not in self.concepts:
            self.concepts[concept_id] = ConceptMastery(concept_id=concept_id)
        return self.concepts[concept_id]

    def get_mastery(self, concept_id: str) -> float:
        """Get current mastery score for a concept."""
        return self._get_or_create_mastery(concept_id).mastery

    def get_all_mastery(self) -> Dict[str, float]:
        """Get mastery scores for all practiced concepts."""
        return {cid: m.mastery for cid, m in self.concepts.items()}

    def get_weak_concepts(self, threshold: float = None) -> List[str]:
        """Get concepts below mastery threshold."""
        threshold = threshold or self.WEAK_THRESHOLD
        return [cid for cid, m in self.concepts.items() if m.mastery < threshold]

    def get_mastered_concepts(self, threshold: float = None) -> List[str]:
        """Get concepts at or above mastery threshold."""
        threshold = threshold or self.MASTERY_THRESHOLD
        return [cid for cid, m in self.concepts.items() if m.mastery >= threshold]

    # ==================== Serialization ====================

    def to_dict(self) -> dict:
        """Serialize model state to dict (for Redis storage)."""
        return {
            "concepts": {
                cid: {
                    "ability": m.ability,
                    "mastery": m.mastery,
                    "last_practiced": m.last_practiced,
                    "practice_count": m.practice_count,
                    "correct_count": m.correct_count,
                    "streak": m.streak
                }
                for cid, m in self.concepts.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StudentModel":
        """Deserialize model from dict."""
        model = cls()
        for cid, m_data in data.get("concepts", {}).items():
            model.concepts[cid] = ConceptMastery(
                concept_id=cid,
                ability=m_data.get("ability", 0.0),
                mastery=m_data.get("mastery", 0.5),
                last_practiced=m_data.get("last_practiced", 0.0),
                practice_count=m_data.get("practice_count", 0),
                correct_count=m_data.get("correct_count", 0),
                streak=m_data.get("streak", 0)
            )
        return model
