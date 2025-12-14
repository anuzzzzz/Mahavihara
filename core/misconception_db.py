"""
Misconception Database - Maps wrong answers to underlying misconceptions.

Features:
    - Pattern matching for common wrong answers
    - Misconception explanations for targeted feedback
    - Remediation suggestions per misconception
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass


@dataclass
class Misconception:
    """A specific misconception pattern."""
    id: str
    concept_id: str
    pattern: str  # The wrong answer pattern (e.g., "adds exponents")
    description: str  # What the student likely thinks
    explanation: str  # Why it's wrong
    remediation: str  # What to teach


@dataclass
class DiagnosedMisconception:
    """Result of diagnosing a wrong answer."""
    misconception: Misconception
    confidence: float  # How confident we are in this diagnosis
    question_id: str
    wrong_answer: str


class MisconceptionDB:
    """
    Database of common misconceptions for targeted feedback.

    Maps (question_id, wrong_answer) -> Misconception
    """

    def __init__(self, data_dir: str = "data/misconceptions"):
        self.data_dir = Path(data_dir)
        self.misconceptions: Dict[str, Misconception] = {}
        self.question_patterns: Dict[str, Dict[str, str]] = {}  # question_id -> {wrong_answer -> misconception_id}
        self.concept_misconceptions: Dict[str, List[str]] = {}  # concept_id -> [misconception_ids]

        self._load_data()

    def _load_data(self):
        """Load misconception data from JSON files."""
        if not self.data_dir.exists():
            self._create_default_data()
            return

        for file_path in self.data_dir.glob("*.json"):
            with open(file_path, 'r') as f:
                data = json.load(f)
            self._process_data(data)

    def _process_data(self, data: dict):
        """Process loaded misconception data."""
        for m_data in data.get("misconceptions", []):
            misconception = Misconception(
                id=m_data["id"],
                concept_id=m_data["concept_id"],
                pattern=m_data["pattern"],
                description=m_data["description"],
                explanation=m_data["explanation"],
                remediation=m_data.get("remediation", "")
            )

            self.misconceptions[misconception.id] = misconception

            # Index by concept
            if misconception.concept_id not in self.concept_misconceptions:
                self.concept_misconceptions[misconception.concept_id] = []
            self.concept_misconceptions[misconception.concept_id].append(misconception.id)

        # Process question-specific patterns
        for q_pattern in data.get("question_patterns", []):
            question_id = q_pattern["question_id"]
            if question_id not in self.question_patterns:
                self.question_patterns[question_id] = {}

            for wrong_answer, misconception_id in q_pattern.get("mappings", {}).items():
                self.question_patterns[question_id][wrong_answer] = misconception_id

    def _create_default_data(self):
        """Create default misconception data for Linear Algebra."""
        # This would be called if no data files exist
        # In production, this would be extensive
        self.misconceptions = {
            "vec_magnitude_add": Misconception(
                id="vec_magnitude_add",
                concept_id="vectors",
                pattern="adds_components",
                description="Student adds components instead of using Pythagorean theorem",
                explanation="The magnitude is √(x² + y²), not x + y",
                remediation="Review: magnitude is the LENGTH of the arrow, found using distance formula"
            ),
            "matrix_mult_elementwise": Misconception(
                id="matrix_mult_elementwise",
                concept_id="matrix_ops",
                pattern="elementwise_multiply",
                description="Student multiplies element-by-element instead of row-by-column",
                explanation="Matrix multiplication uses dot products of rows and columns",
                remediation="Practice: row of A • column of B = one element of result"
            ),
            "det_add_elements": Misconception(
                id="det_add_elements",
                concept_id="determinants",
                pattern="adds_diagonal",
                description="Student adds diagonal elements instead of ad-bc",
                explanation="Determinant for 2x2 is (a*d) - (b*c), not a+d or a+b+c+d",
                remediation="Remember: main diagonal MINUS anti-diagonal"
            ),
            "inverse_just_reciprocal": Misconception(
                id="inverse_just_reciprocal",
                concept_id="inverse_matrix",
                pattern="element_reciprocal",
                description="Student takes 1/each element instead of proper inverse",
                explanation="Matrix inverse requires det and adjugate: (1/det) * adj(A)",
                remediation="Review: A⁻¹ ≠ 1/A for matrices. Use the formula."
            ),
            "eigen_just_diagonal": Misconception(
                id="eigen_just_diagonal",
                concept_id="eigenvalues",
                pattern="diagonal_values",
                description="Student thinks diagonal elements are eigenvalues",
                explanation="Eigenvalues require solving det(A - λI) = 0",
                remediation="Eigenvalues are only diagonal elements for diagonal matrices"
            )
        }

        # Index by concept
        for mid, m in self.misconceptions.items():
            if m.concept_id not in self.concept_misconceptions:
                self.concept_misconceptions[m.concept_id] = []
            self.concept_misconceptions[m.concept_id].append(mid)

    # ==================== Diagnosis ====================

    def diagnose(self, question_id: str, concept_id: str,
                 wrong_answer: str, correct_answer: str) -> Optional[DiagnosedMisconception]:
        """
        Diagnose the misconception behind a wrong answer.

        Returns the most likely misconception, or None if unknown.
        """
        # First check for exact question-answer pattern
        if question_id in self.question_patterns:
            patterns = self.question_patterns[question_id]
            wrong_answer_normalized = str(wrong_answer).strip().upper()

            if wrong_answer_normalized in patterns:
                misconception_id = patterns[wrong_answer_normalized]
                if misconception_id in self.misconceptions:
                    return DiagnosedMisconception(
                        misconception=self.misconceptions[misconception_id],
                        confidence=0.9,
                        question_id=question_id,
                        wrong_answer=wrong_answer
                    )

        # Check for concept-level patterns
        if concept_id in self.concept_misconceptions:
            # Return most common misconception for concept (lower confidence)
            misconception_ids = self.concept_misconceptions[concept_id]
            if misconception_ids:
                misconception = self.misconceptions[misconception_ids[0]]
                return DiagnosedMisconception(
                    misconception=misconception,
                    confidence=0.5,
                    question_id=question_id,
                    wrong_answer=wrong_answer
                )

        return None

    def get_remediation(self, misconception_id: str) -> Optional[str]:
        """Get remediation suggestion for a misconception."""
        if misconception_id in self.misconceptions:
            return self.misconceptions[misconception_id].remediation
        return None

    def get_concept_misconceptions(self, concept_id: str) -> List[Misconception]:
        """Get all known misconceptions for a concept."""
        ids = self.concept_misconceptions.get(concept_id, [])
        return [self.misconceptions[mid] for mid in ids if mid in self.misconceptions]

    # ==================== Feedback Generation ====================

    def generate_feedback(self, diagnosis: DiagnosedMisconception) -> str:
        """Generate targeted feedback based on diagnosed misconception."""
        m = diagnosis.misconception

        if diagnosis.confidence >= 0.8:
            # High confidence: direct feedback
            return f"""💡 **Common Mistake Detected!**

It looks like you might be thinking: *"{m.description}"*

**Why this is wrong:** {m.explanation}

**How to fix it:** {m.remediation}"""
        else:
            # Lower confidence: gentler feedback
            return f"""💡 **Tip for Improvement**

{m.explanation}

**Remember:** {m.remediation}"""

    # ==================== Statistics ====================

    def get_stats(self) -> dict:
        """Get statistics about the misconception database."""
        return {
            "total_misconceptions": len(self.misconceptions),
            "concepts_covered": list(self.concept_misconceptions.keys()),
            "questions_with_patterns": len(self.question_patterns)
        }
