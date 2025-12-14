"""
Misconception Detection System

THE KEY INSIGHT: Every wrong answer tells a story.

When a student chooses option A instead of B, they're not just "wrong" -
they have a specific misconception that led them there.

Squirrel AI's secret sauce: They've catalogued 10,000+ misconception patterns.
We can start smaller but smarter.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class Misconception:
    """A detected misconception"""
    id: str
    name: str
    description: str
    severity: str  # "critical", "moderate", "minor"
    remediation_concept: str  # Which concept to revisit
    remediation_focus: str  # Specific aspect to focus on
    common_in: List[str]  # Demographics where this is common


@dataclass
class WrongAnswerAnalysis:
    """Analysis of a wrong answer"""
    question_id: str
    chosen_answer: int
    correct_answer: int
    misconception: Misconception
    explanation: str  # Why this specific wrong answer indicates this misconception
    suggested_resource: Optional[str] = None


class MisconceptionDetector:
    """
    Detects misconceptions from wrong answer patterns.

    This is the 10x feature: Instead of "Wrong, the answer is B",
    we say "You chose A because you confused eigenvectors with eigenvalues.
    Here's exactly why that's wrong and how to fix it."
    """

    # ==================== MISCONCEPTION DATABASE ====================
    # Format: question_id -> {wrong_answer_index -> misconception}

    MISCONCEPTION_MAP = {
        # ===== VECTORS =====
        "vec_1": {  # "What is the magnitude of vector [3, 4]?"
            0: Misconception(  # Chose "7" (3+4)
                id="vec_add_not_pythag",
                name="Addition Instead of Pythagorean",
                description="Adding components instead of using Pythagorean theorem",
                severity="critical",
                remediation_concept="vectors",
                remediation_focus="magnitude_formula",
                common_in=["JEE beginners", "physics background"]
            ),
            2: Misconception(  # Chose "12" (3*4)
                id="vec_multiply_magnitude",
                name="Multiplying Components for Magnitude",
                description="Multiplying components instead of squaring and adding",
                severity="moderate",
                remediation_concept="vectors",
                remediation_focus="magnitude_formula",
                common_in=["rushing through"]
            ),
            3: Misconception(  # Chose "1"
                id="vec_unit_confusion",
                name="Confusing Magnitude with Unit Vector",
                description="Thinking all vectors have magnitude 1, or confusing with unit vectors",
                severity="moderate",
                remediation_concept="vectors",
                remediation_focus="unit_vectors",
                common_in=["first exposure"]
            )
        },

        "vec_2": {  # "Dot product of orthogonal vectors is:"
            0: Misconception(  # Chose "1"
                id="vec_unit_dot_confusion",
                name="Unit Vector Dot Product Confusion",
                description="Confusing orthogonal dot product with unit vector dot product",
                severity="moderate",
                remediation_concept="vectors",
                remediation_focus="dot_product_geometric",
                common_in=["memorization over understanding"]
            ),
            2: Misconception(  # Chose "-1"
                id="vec_antiparallel_confusion",
                name="Orthogonal vs Antiparallel Confusion",
                description="Confusing perpendicular (90 deg) with opposite direction (180 deg)",
                severity="critical",
                remediation_concept="vectors",
                remediation_focus="angle_between_vectors",
                common_in=["spatial reasoning weak"]
            ),
            3: Misconception(  # Chose "Infinite"
                id="vec_division_confusion",
                name="Division in Dot Product",
                description="Thinking dot product involves division (like tangent)",
                severity="minor",
                remediation_concept="vectors",
                remediation_focus="dot_product_formula",
                common_in=["trig background"]
            )
        },

        "vec_4": {  # "Which is a unit vector?"
            0: Misconception(  # Chose "[1, 1]"
                id="vec_ones_unit",
                name="Ones Vector is Unit",
                description="Thinking [1,1] is a unit vector (magnitude is sqrt(2), not 1)",
                severity="critical",
                remediation_concept="vectors",
                remediation_focus="unit_vector_definition",
                common_in=["very common"]
            ),
            2: Misconception(  # Chose "[1, 0.5]"
                id="vec_first_component_unit",
                name="First Component Determines Unit",
                description="Thinking if first component is 1, it's a unit vector",
                severity="moderate",
                remediation_concept="vectors",
                remediation_focus="magnitude_formula",
                common_in=["rushing"]
            )
        },

        # ===== MATRIX OPERATIONS =====
        "mat_1": {  # "Can you multiply a 2x3 matrix by a 2x2 matrix?"
            0: Misconception(  # Chose "Yes"
                id="mat_dim_match_cols",
                name="Column-Column Matching",
                description="Thinking columns must match columns, not inner dimensions",
                severity="critical",
                remediation_concept="matrix_ops",
                remediation_focus="multiplication_dimensions",
                common_in=["very common"]
            ),
            2: Misconception(  # Chose "Only if square"
                id="mat_square_only",
                name="Square Matrix Multiplication Only",
                description="Thinking only square matrices can be multiplied",
                severity="moderate",
                remediation_concept="matrix_ops",
                remediation_focus="multiplication_dimensions",
                common_in=["incomplete learning"]
            )
        },

        "mat_2": {  # "The Identity Matrix I has what property?"
            1: Misconception(  # Chose "AI = 0"
                id="mat_identity_zero",
                name="Identity Equals Zero",
                description="Confusing identity matrix with zero matrix",
                severity="critical",
                remediation_concept="matrix_ops",
                remediation_focus="special_matrices",
                common_in=["terminology confusion"]
            ),
            2: Misconception(  # Chose "AI = -A"
                id="mat_identity_negative",
                name="Identity Negates",
                description="Thinking identity matrix negates the original",
                severity="moderate",
                remediation_concept="matrix_ops",
                remediation_focus="identity_matrix",
                common_in=["guessing"]
            )
        },

        # ===== DETERMINANTS =====
        "det_1": {  # "What is the determinant of [[2, 0], [0, 2]]?"
            0: Misconception(  # Chose "2"
                id="det_diagonal_sum",
                name="Diagonal Sum Not Product",
                description="Adding diagonal elements instead of multiplying for diagonal matrices",
                severity="moderate",
                remediation_concept="determinants",
                remediation_focus="diagonal_matrix_det",
                common_in=["formula confusion"]
            ),
            2: Misconception(  # Chose "0"
                id="det_zero_confusion",
                name="Zero Off-Diagonal Means Zero Det",
                description="Thinking zero off-diagonal elements make determinant zero",
                severity="critical",
                remediation_concept="determinants",
                remediation_focus="2x2_formula",
                common_in=["incomplete formula"]
            ),
            3: Misconception(  # Chose "1"
                id="det_identity_confusion",
                name="Diagonal Matrix = Identity",
                description="Confusing any diagonal matrix with identity matrix",
                severity="moderate",
                remediation_concept="determinants",
                remediation_focus="special_matrices",
                common_in=["terminology gaps"]
            )
        },

        "det_2": {  # "If det(A) = 0, the matrix is:"
            0: Misconception(  # Chose "Invertible"
                id="det_zero_invertible",
                name="Zero Determinant Invertible",
                description="Thinking det=0 matrices are invertible",
                severity="critical",
                remediation_concept="determinants",
                remediation_focus="geometric_meaning",
                common_in=["no geometric intuition"]
            ),
            2: Misconception(  # Chose "Identity"
                id="det_zero_identity",
                name="Zero Determinant Identity",
                description="Confusing det=0 with identity matrix",
                severity="moderate",
                remediation_concept="determinants",
                remediation_focus="special_matrices",
                common_in=["memorization gaps"]
            )
        },

        "det_5": {  # "For a 2x2 matrix [[a, b], [c, d]], the determinant is:"
            0: Misconception(  # Chose "ad + bc"
                id="det_ad_plus_bc",
                name="Addition in Determinant",
                description="Using ad + bc instead of ad - bc",
                severity="critical",
                remediation_concept="determinants",
                remediation_focus="2x2_formula",
                common_in=["formula confusion"]
            ),
            2: Misconception(  # Chose "ab - cd"
                id="det_wrong_pairs",
                name="Wrong Element Pairs",
                description="Pairing wrong elements (rows instead of diagonals)",
                severity="moderate",
                remediation_concept="determinants",
                remediation_focus="2x2_formula",
                common_in=["visual confusion"]
            )
        },

        # ===== INVERSE MATRIX =====
        "inv_1": {  # "A matrix has an inverse ONLY if:"
            0: Misconception(  # Chose "It is square"
                id="inv_square_only",
                name="Square = Invertible",
                description="Thinking all square matrices are invertible",
                severity="critical",
                remediation_concept="inverse_matrix",
                remediation_focus="invertibility_conditions",
                common_in=["incomplete knowledge"]
            )
        },

        "inv_2": {  # "What is A multiplied by A inverse?"
            0: Misconception(  # Chose "A"
                id="inv_gives_original",
                name="Inverse Returns Original",
                description="Thinking A * A^-1 = A instead of I",
                severity="moderate",
                remediation_concept="inverse_matrix",
                remediation_focus="inverse_definition",
                common_in=["conceptual gap"]
            ),
            1: Misconception(  # Chose "0"
                id="inv_gives_zero",
                name="Inverse Cancels to Zero",
                description="Thinking inverse cancels like subtraction (x - x = 0)",
                severity="critical",
                remediation_concept="inverse_matrix",
                remediation_focus="inverse_definition",
                common_in=["arithmetic thinking"]
            )
        },

        # ===== EIGENVALUES =====
        "eig_1": {  # "If Av = lv, then l is the:"
            0: Misconception(  # Chose "Eigenvector"
                id="eig_vector_value_swap",
                name="Eigenvector-Eigenvalue Swap",
                description="Confusing the scalar lambda with the vector v",
                severity="critical",
                remediation_concept="eigenvalues",
                remediation_focus="definition",
                common_in=["very common", "terminology confusion"]
            ),
            2: Misconception(  # Chose "Matrix"
                id="eig_matrix_confusion",
                name="Matrix as Eigenvalue",
                description="Confusing A (the matrix) with lambda (the eigenvalue)",
                severity="moderate",
                remediation_concept="eigenvalues",
                remediation_focus="equation_parts",
                common_in=["equation parsing"]
            )
        },

        "eig_3": {  # "Sum of eigenvalues equals:"
            0: Misconception(  # Chose "Determinant"
                id="eig_sum_det",
                name="Sum = Determinant Confusion",
                description="Confusing trace (sum of diagonal = sum of eigenvalues) with determinant",
                severity="moderate",
                remediation_concept="eigenvalues",
                remediation_focus="trace_connection",
                common_in=["formula mixing"]
            ),
            2: Misconception(  # Chose "0"
                id="eig_sum_zero",
                name="Eigenvalues Sum to Zero",
                description="Thinking eigenvalues always sum to zero",
                severity="minor",
                remediation_concept="eigenvalues",
                remediation_focus="trace_examples",
                common_in=["specific examples only"]
            )
        },

        "eig_4": {  # "Product of eigenvalues equals:"
            0: Misconception(  # Chose "Trace"
                id="eig_prod_trace",
                name="Product = Trace Confusion",
                description="Confusing product of eigenvalues with trace",
                severity="moderate",
                remediation_concept="eigenvalues",
                remediation_focus="determinant_connection",
                common_in=["formula swapping"]
            )
        },

        "eig_5": {  # "If a matrix has eigenvalue 0, then:"
            0: Misconception(  # Chose "It is invertible"
                id="eig_zero_invertible",
                name="Eigenvalue 0 = Invertible",
                description="Not connecting eigenvalue 0 -> det 0 -> singular",
                severity="critical",
                remediation_concept="eigenvalues",
                remediation_focus="determinant_connection",
                common_in=["missing prerequisite link"]
            ),
            2: Misconception(  # Chose "It is identity"
                id="eig_zero_identity",
                name="Eigenvalue 0 = Identity",
                description="Confusing eigenvalue 0 with identity matrix properties",
                severity="moderate",
                remediation_concept="eigenvalues",
                remediation_focus="special_cases",
                common_in=["terminology gaps"]
            )
        }
    }

    # ==================== DETECTION METHODS ====================

    def __init__(self, data_dir: str = "data/misconceptions"):
        """Initialize detector. data_dir kept for API compatibility."""
        self.misconceptions = self._build_misconception_index()
        self.concept_misconceptions = self._build_concept_index()

    def _build_misconception_index(self) -> Dict[str, Misconception]:
        """Build a flat index of all misconceptions by ID."""
        index = {}
        for question_id, answers in self.MISCONCEPTION_MAP.items():
            for answer_idx, misconception in answers.items():
                index[misconception.id] = misconception
        return index

    def _build_concept_index(self) -> Dict[str, List[str]]:
        """Build index of misconception IDs by concept."""
        index = {}
        for misconception in self.misconceptions.values():
            concept = misconception.remediation_concept
            if concept not in index:
                index[concept] = []
            if misconception.id not in index[concept]:
                index[concept].append(misconception.id)
        return index

    def analyze_wrong_answer(
        self,
        question_id: str,
        chosen_answer: int = None,
        correct_answer: int = None,
        # Also accept string format from API
        user_answer: str = None,
        concept_id: str = None
    ) -> Optional[WrongAnswerAnalysis]:
        """
        Analyze a wrong answer to detect the underlying misconception.

        Accepts both numeric indices and letter answers (A, B, C, D).
        """
        # Convert letter answer to index if needed
        if chosen_answer is None and user_answer:
            answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            chosen_answer = answer_map.get(user_answer.strip().upper(), -1)

        if chosen_answer is None or chosen_answer == -1:
            return None

        if correct_answer is not None and chosen_answer == correct_answer:
            return None  # Not a wrong answer

        question_misconceptions = self.MISCONCEPTION_MAP.get(question_id, {})
        misconception = question_misconceptions.get(chosen_answer)

        if not misconception:
            # Unknown misconception - use generic analysis
            misconception = Misconception(
                id="unknown",
                name="Unclassified Error",
                description="Error pattern not yet catalogued",
                severity="moderate",
                remediation_concept=concept_id or self._infer_concept(question_id),
                remediation_focus="general_review",
                common_in=[]
            )

        # Generate explanation for why this specific choice indicates this misconception
        explanation = self._generate_explanation(question_id, chosen_answer, misconception)

        return WrongAnswerAnalysis(
            question_id=question_id,
            chosen_answer=chosen_answer,
            correct_answer=correct_answer if correct_answer is not None else -1,
            misconception=misconception,
            explanation=explanation
        )

    def analyze_answer_pattern(
        self,
        answers: List[Dict]
    ) -> Dict:
        """
        Analyze a pattern of answers to find systematic misconceptions.

        Args:
            answers: List of {"question_id", "chosen"/"user_answer", "correct", "is_correct"}

        Returns:
            Analysis with primary misconception and patterns
        """
        wrong_answers = [a for a in answers if not a.get("is_correct")]

        if not wrong_answers:
            return {
                "status": "all_correct",
                "misconceptions": [],
                "primary_weakness": None
            }

        # Detect misconceptions for each wrong answer
        misconceptions = []
        for answer in wrong_answers:
            # Handle both formats
            chosen = answer.get("chosen", answer.get("chosen_answer"))
            if chosen is None:
                user_ans = answer.get("user_answer", "")
                answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
                chosen = answer_map.get(str(user_ans).strip().upper(), -1)

            analysis = self.analyze_wrong_answer(
                answer["question_id"],
                chosen_answer=chosen,
                correct_answer=answer.get("correct", answer.get("correct_answer"))
            )
            if analysis and analysis.misconception.id != "unknown":
                misconceptions.append(analysis)

        # Find patterns
        severity_order = {"critical": 0, "moderate": 1, "minor": 2}
        misconceptions.sort(key=lambda m: severity_order.get(m.misconception.severity, 1))

        # Group by remediation concept
        concept_counts = {}
        for m in misconceptions:
            concept = m.misconception.remediation_concept
            concept_counts[concept] = concept_counts.get(concept, 0) + 1

        primary_weakness = max(concept_counts, key=concept_counts.get) if concept_counts else None

        return {
            "status": "misconceptions_detected",
            "misconceptions": misconceptions,
            "primary_weakness": primary_weakness,
            "concept_distribution": concept_counts,
            "most_critical": misconceptions[0] if misconceptions else None
        }

    def get_remediation_plan(
        self,
        misconception: Misconception
    ) -> Dict:
        """
        Generate a remediation plan for a detected misconception.

        Returns actionable steps to fix the misconception.
        """
        plan = {
            "misconception": misconception.name,
            "severity": misconception.severity,
            "what_went_wrong": misconception.description,
            "fix_strategy": self._get_fix_strategy(misconception),
            "target_concept": misconception.remediation_concept,
            "focus_area": misconception.remediation_focus,
            "estimated_time": self._estimate_remediation_time(misconception),
            "success_criteria": self._get_success_criteria(misconception)
        }
        return plan

    def get_concept_misconceptions(self, concept_id: str) -> List[Misconception]:
        """Get all known misconceptions for a concept."""
        ids = self.concept_misconceptions.get(concept_id, [])
        return [self.misconceptions[mid] for mid in ids if mid in self.misconceptions]

    # ==================== HELPER METHODS ====================

    def _infer_concept(self, question_id: str) -> str:
        """Infer concept from question ID prefix"""
        prefix_map = {
            "vec": "vectors",
            "mat": "matrix_ops",
            "det": "determinants",
            "inv": "inverse_matrix",
            "eig": "eigenvalues"
        }
        prefix = question_id.split("_")[0]
        return prefix_map.get(prefix, "unknown")

    def _generate_explanation(
        self,
        question_id: str,
        chosen: int,
        misconception: Misconception
    ) -> str:
        """Generate human-readable explanation for the misconception"""

        # Specific explanations for known question/answer combos
        specific_explanations = {
            ("vec_1", 0): "You added 3 + 4 = 7. But magnitude uses Pythagorean theorem: sqrt(3^2 + 4^2) = sqrt(25) = 5",
            ("vec_1", 2): "You multiplied 3 * 4 = 12. Magnitude is sqrt(x^2 + y^2), not x * y",
            ("vec_1", 3): "A unit vector has magnitude 1, but [3,4] has magnitude 5. Unit vectors are normalized versions.",
            ("vec_2", 0): "You chose 1, which is the dot product of parallel unit vectors. Orthogonal means 90 degrees, so cos(90) = 0.",
            ("vec_2", 2): "You chose -1, which is for antiparallel (180 deg) vectors. Orthogonal (90 deg) gives cos(90) = 0.",
            ("vec_4", 0): "[1,1] has magnitude sqrt(1^2 + 1^2) = sqrt(2) ≈ 1.41, not 1. A unit vector must have magnitude exactly 1.",
            ("mat_1", 0): "For matrix multiplication, inner dimensions must match. (2x3) * (2x2) fails because 3 != 2.",
            ("det_1", 0): "You added 2 + 2 = 4? Actually correct! But if you got here by adding instead of multiplying, remember: for diagonal matrices, det = product of diagonal.",
            ("det_1", 2): "The zeros are off-diagonal. The formula ad - bc = (2)(2) - (0)(0) = 4, not 0.",
            ("det_5", 0): "The determinant formula is ad - bc (MINUS), not ad + bc. The 'cross' pattern goes in opposite directions.",
            ("eig_1", 0): "lambda is the eigenVALUE (a number), not the eigenVECTOR (v). Think: lambda = scalar, v = arrow.",
            ("eig_3", 0): "Sum of eigenvalues = Trace (diagonal sum). Product of eigenvalues = Determinant. You swapped them!",
            ("eig_5", 0): "If any eigenvalue = 0, then product of eigenvalues = 0, so determinant = 0, so NOT invertible.",
            ("inv_2", 1): "Inverse isn't like subtraction (x - x = 0). A * A^-1 = Identity Matrix (I), not zero.",
        }

        key = (question_id, chosen)
        if key in specific_explanations:
            return specific_explanations[key]

        # Generic explanation
        return f"This answer pattern suggests: {misconception.description}"

    def _get_fix_strategy(self, misconception: Misconception) -> List[str]:
        """Get fix strategy based on misconception type"""

        strategies = {
            "critical": [
                "Watch foundational video explanation",
                "Work through 3-5 basic examples by hand",
                "Take diagnostic quiz to verify fix"
            ],
            "moderate": [
                "Review the specific formula/concept",
                "Practice 2-3 targeted problems",
                "Retry similar question"
            ],
            "minor": [
                "Quick review of edge cases",
                "Retry the question"
            ]
        }

        return strategies.get(misconception.severity, strategies["moderate"])

    def _estimate_remediation_time(self, misconception: Misconception) -> str:
        """Estimate time to fix misconception"""
        times = {
            "critical": "10-15 minutes",
            "moderate": "5-10 minutes",
            "minor": "2-5 minutes"
        }
        return times.get(misconception.severity, "5-10 minutes")

    def _get_success_criteria(self, misconception: Misconception) -> str:
        """Define what success looks like"""
        return f"Answer 2 questions on {misconception.remediation_focus} correctly"


# ==================== USAGE EXAMPLE ====================

if __name__ == "__main__":
    detector = MisconceptionDetector()

    print("=== Misconception Detector Test ===\n")

    # Test 1: Single wrong answer analysis
    print("1. Analyzing wrong answer: vec_1, chose 0 (said '7' instead of '5')")
    analysis = detector.analyze_wrong_answer("vec_1", chosen_answer=0, correct_answer=1)
    if analysis:
        print(f"   Misconception: {analysis.misconception.name}")
        print(f"   Severity: {analysis.misconception.severity}")
        print(f"   Explanation: {analysis.explanation}")
        print(f"   Remediation: {analysis.misconception.remediation_focus}")

    # Test 2: Pattern analysis
    print("\n2. Analyzing answer pattern...")
    sample_answers = [
        {"question_id": "vec_1", "chosen": 0, "correct": 1, "is_correct": False},
        {"question_id": "vec_4", "chosen": 0, "correct": 1, "is_correct": False},
        {"question_id": "mat_1", "chosen": 1, "correct": 1, "is_correct": True},
        {"question_id": "eig_1", "chosen": 0, "correct": 1, "is_correct": False},
    ]

    pattern = detector.analyze_answer_pattern(sample_answers)
    print(f"   Primary weakness: {pattern['primary_weakness']}")
    print(f"   Most critical: {pattern['most_critical'].misconception.name if pattern['most_critical'] else 'None'}")
    print(f"   Concept distribution: {pattern['concept_distribution']}")

    # Test 3: Remediation plan
    print("\n3. Generating remediation plan...")
    if pattern['most_critical']:
        plan = detector.get_remediation_plan(pattern['most_critical'].misconception)
        print(f"   What went wrong: {plan['what_went_wrong']}")
        print(f"   Time needed: {plan['estimated_time']}")
        print(f"   Fix strategy:")
        for step in plan['fix_strategy']:
            print(f"      - {step}")
