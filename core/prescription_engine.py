"""
Prescription Engine - The Doctor's Prescription for Learning.

"ChatGPT writes explanations. Mahavihara prescribes the perfect YouTube timestamp."

This engine creates personalized learning prescriptions:
    Diagnosis -> Treatment Plan -> Verification
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import time

from core.knowledge_graph import KnowledgeGraph
from core.student_model import StudentModel
from core.misconception_detector import MisconceptionDetector, WrongAnswerAnalysis, Misconception


class PrescriptionPhase(Enum):
    """Phases in the learning prescription."""
    UNDERSTAND = "understand"  # Watch/read to build intuition
    PRACTICE = "practice"  # Try problems with guidance
    VERIFY = "verify"  # Prove mastery independently


@dataclass
class LearningResource:
    """A prescribed learning resource."""
    title: str
    url: str
    type: str  # youtube, article, interactive
    timestamp: Optional[str] = None  # For YouTube: "2:34"
    duration_minutes: int = 10
    why_prescribed: str = ""


@dataclass
class TreatmentPhase:
    """One phase of the treatment plan."""
    phase: PrescriptionPhase
    title: str
    icon: str
    resources: List[LearningResource]
    instructions: str
    estimated_minutes: int


@dataclass
class LearningPrescription:
    """A complete learning prescription - like a doctor's prescription."""
    # Patient info
    session_id: str
    timestamp: float = field(default_factory=time.time)

    # Diagnosis
    diagnosed_concept: str = ""
    diagnosed_concept_name: str = ""
    misconceptions: List[Misconception] = field(default_factory=list)
    root_cause_concept: Optional[str] = None
    root_cause_name: Optional[str] = None
    severity: int = 1  # 1-3

    # Treatment plan
    phases: List[TreatmentPhase] = field(default_factory=list)
    total_estimated_minutes: int = 0

    # Verification criteria
    questions_to_pass: int = 2
    questions_total: int = 3
    must_show_work: bool = False


class PrescriptionEngine:
    """
    Generates learning prescriptions based on diagnosed learning gaps.

    Think of it as a doctor:
    1. Examine symptoms (wrong answers)
    2. Diagnose root cause (misconception + prerequisite gaps)
    3. Prescribe treatment (specific resources)
    4. Schedule follow-up (verification questions)
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        student_model: StudentModel,
        misconception_detector: Optional[MisconceptionDetector] = None
    ):
        self.kg = knowledge_graph
        self.model = student_model
        self.detector = misconception_detector or MisconceptionDetector()

    def generate_prescription(
        self,
        concept_id: str,
        wrong_answers: List[WrongAnswerAnalysis],
        session_id: str = ""
    ) -> LearningPrescription:
        """
        Generate a complete learning prescription for a struggling student.

        Args:
            concept_id: The concept they're struggling with
            wrong_answers: Analysis of their wrong answers
            session_id: Current session ID

        Returns:
            Complete prescription with diagnosis, treatment, and verification plan
        """
        # Get concept info
        concept = self.kg.get_concept(concept_id)
        concept_name = concept.get("name", concept_id) if concept else concept_id

        # Step 1: Diagnose - identify misconceptions and root cause
        misconceptions = self._extract_misconceptions(wrong_answers)
        root_cause_id, root_cause_name = self._trace_root_cause(concept_id, misconceptions)

        # Step 2: Calculate severity
        severity = self._calculate_severity(misconceptions, root_cause_id != concept_id)

        # Step 3: Build treatment phases
        phases = self._build_treatment_phases(
            concept_id=concept_id,
            concept_name=concept_name,
            misconceptions=misconceptions,
            root_cause_id=root_cause_id
        )

        # Step 4: Create prescription
        total_time = sum(p.estimated_minutes for p in phases)

        return LearningPrescription(
            session_id=session_id,
            diagnosed_concept=concept_id,
            diagnosed_concept_name=concept_name,
            misconceptions=misconceptions,
            root_cause_concept=root_cause_id if root_cause_id != concept_id else None,
            root_cause_name=root_cause_name if root_cause_id != concept_id else None,
            severity=severity,
            phases=phases,
            total_estimated_minutes=total_time,
            questions_to_pass=2,
            questions_total=3,
            must_show_work=severity >= 2
        )

    def _extract_misconceptions(self, wrong_answers: List[WrongAnswerAnalysis]) -> List[Misconception]:
        """Extract unique misconceptions from wrong answer analyses."""
        seen = set()
        misconceptions = []

        for analysis in wrong_answers:
            if analysis.misconception and analysis.misconception.id not in seen:
                seen.add(analysis.misconception.id)
                misconceptions.append(analysis.misconception)

        return misconceptions

    def _trace_root_cause(
        self,
        concept_id: str,
        misconceptions: List[Misconception]
    ) -> Tuple[str, str]:
        """
        Trace back to find the root cause of the learning gap.

        Sometimes the problem isn't with the current concept - it's a
        prerequisite that was never properly understood.
        """
        # Check mastery of prerequisites
        prerequisites = self.kg.get_prerequisites(concept_id)
        mastery_scores = self.model.get_all_mastery()

        weak_prereqs = [
            prereq for prereq in prerequisites
            if mastery_scores.get(prereq, 0.5) < 0.5
        ]

        if weak_prereqs:
            # Find the weakest prerequisite
            weakest = min(weak_prereqs, key=lambda p: mastery_scores.get(p, 0.5))
            concept = self.kg.get_concept(weakest)
            name = concept.get("name", weakest) if concept else weakest
            return weakest, name

        # No weak prereqs - root cause is this concept
        concept = self.kg.get_concept(concept_id)
        name = concept.get("name", concept_id) if concept else concept_id
        return concept_id, name

    def _calculate_severity(self, misconceptions: List[Misconception], has_prereq_gap: bool) -> int:
        """Calculate severity of learning gap (1-3)."""
        if has_prereq_gap:
            return 3  # Foundational gap is severe

        if len(misconceptions) >= 2:
            return 2  # Multiple misconceptions

        return 1  # Single issue

    def _calculate_diagnosis_confidence(
        self,
        num_wrong_answers: int,
        misconceptions: List
    ) -> float:
        """
        Calculate confidence in diagnosis based on evidence.

        More wrong answers + detected patterns = higher confidence.
        """
        if num_wrong_answers == 0:
            return 0.0

        # Base confidence from number of data points
        base_confidence = min(0.5, num_wrong_answers * 0.15)

        # Bonus for detected misconceptions
        if misconceptions:
            pattern_bonus = min(0.4, len(misconceptions) * 0.15)
            # Extra bonus if misconceptions are consistent (same concept)
            concepts = set(m.misconception.remediation_concept for m in misconceptions if hasattr(m, 'misconception'))
            if len(concepts) == 1:
                pattern_bonus += 0.1
        else:
            pattern_bonus = 0.0

        return min(0.95, base_confidence + pattern_bonus)

    def trace_root_cause_from_mastery(
        self,
        failed_concept: str,
        mastery_scores: Dict[str, float]
    ) -> str:
        """
        Trace root cause using provided mastery scores (API-friendly version).

        Returns the concept ID of the root cause.
        """
        prerequisites = self.kg.get_prerequisites(failed_concept)

        weak_prereqs = [
            prereq for prereq in prerequisites
            if mastery_scores.get(prereq, 0.5) < 0.5
        ]

        if weak_prereqs:
            return min(weak_prereqs, key=lambda p: mastery_scores.get(p, 0.5))

        return failed_concept

    def _build_treatment_phases(
        self,
        concept_id: str,
        concept_name: str,
        misconceptions: List[Misconception],
        root_cause_id: str
    ) -> List[TreatmentPhase]:
        """Build the treatment phases with specific resources."""
        phases = []

        # Phase 1: UNDERSTAND - Build intuition with videos
        understand_resources = self._get_understanding_resources(concept_id, misconceptions)
        if understand_resources:
            phases.append(TreatmentPhase(
                phase=PrescriptionPhase.UNDERSTAND,
                title="Build Understanding",
                icon="🎬",
                resources=understand_resources,
                instructions=f"Watch these to build intuition about {concept_name}. "
                           "Focus on the visual explanations, not memorizing formulas.",
                estimated_minutes=sum(r.duration_minutes for r in understand_resources)
            ))

        # Phase 2: PRACTICE - Guided practice
        practice_resources = self._get_practice_resources(concept_id)
        if practice_resources:
            phases.append(TreatmentPhase(
                phase=PrescriptionPhase.PRACTICE,
                title="Guided Practice",
                icon="✍️",
                resources=practice_resources,
                instructions="Work through these problems step by step. "
                           "If you get stuck, re-watch the relevant video section.",
                estimated_minutes=15
            ))

        # Phase 3: VERIFY - Come back for quiz
        phases.append(TreatmentPhase(
            phase=PrescriptionPhase.VERIFY,
            title="Prove Mastery",
            icon="🎯",
            resources=[],
            instructions="After studying, return here and say 'quiz me' to test your understanding. "
                       "Need 2/3 correct to advance.",
            estimated_minutes=5
        ))

        return phases

    def _get_understanding_resources(
        self,
        concept_id: str,
        misconceptions: List[Misconception]
    ) -> List[LearningResource]:
        """Get video/article resources for understanding phase."""
        # Curated resources per concept
        CONCEPT_RESOURCES = {
            "vectors": [
                LearningResource(
                    title="Vectors | Essence of linear algebra",
                    url="https://youtube.com/watch?v=fNk_zzaMoSs",
                    type="youtube",
                    timestamp="0:00",
                    duration_minutes=10,
                    why_prescribed="Best visual introduction to vectors"
                ),
            ],
            "matrix_ops": [
                LearningResource(
                    title="Linear transformations and matrices",
                    url="https://youtube.com/watch?v=kYB8IZa5AuE",
                    type="youtube",
                    timestamp="0:00",
                    duration_minutes=11,
                    why_prescribed="See matrices as transformations, not just numbers"
                ),
                LearningResource(
                    title="Matrix multiplication as composition",
                    url="https://youtube.com/watch?v=XkY2DOUCWMU",
                    type="youtube",
                    timestamp="0:00",
                    duration_minutes=10,
                    why_prescribed="Understand WHY matrix multiplication works the way it does"
                ),
            ],
            "determinants": [
                LearningResource(
                    title="The determinant | Essence of linear algebra",
                    url="https://youtube.com/watch?v=Ip3X9LOh2dk",
                    type="youtube",
                    timestamp="0:00",
                    duration_minutes=10,
                    why_prescribed="Visual meaning of determinants as scaling factors"
                ),
            ],
            "inverse_matrix": [
                LearningResource(
                    title="Inverse matrices, column space and null space",
                    url="https://youtube.com/watch?v=uQhTuRlWMxw",
                    type="youtube",
                    timestamp="0:00",
                    duration_minutes=12,
                    why_prescribed="When inverses exist and what they mean geometrically"
                ),
            ],
            "eigenvalues": [
                LearningResource(
                    title="Eigenvectors and eigenvalues",
                    url="https://youtube.com/watch?v=PFDu9oVAE-g",
                    type="youtube",
                    timestamp="0:00",
                    duration_minutes=17,
                    why_prescribed="The most intuitive eigenvalue explanation"
                ),
            ],
        }

        return CONCEPT_RESOURCES.get(concept_id, [])

    def _get_practice_resources(self, concept_id: str) -> List[LearningResource]:
        """Get interactive practice resources."""
        PRACTICE_RESOURCES = {
            "vectors": [
                LearningResource(
                    title="Khan Academy: Vectors",
                    url="https://www.khanacademy.org/math/linear-algebra/vectors-and-spaces",
                    type="interactive",
                    duration_minutes=20,
                    why_prescribed="Practice problems with instant feedback"
                ),
            ],
            "matrix_ops": [
                LearningResource(
                    title="Khan Academy: Matrix multiplication",
                    url="https://www.khanacademy.org/math/algebra-home/alg-matrices/alg-multiplying-matrices",
                    type="interactive",
                    duration_minutes=15,
                    why_prescribed="Step-by-step practice"
                ),
            ],
            "determinants": [
                LearningResource(
                    title="Khan Academy: Determinants",
                    url="https://www.khanacademy.org/math/linear-algebra/matrix-transformations/determinant-depth/v/linear-algebra-determinant-when-row-multiplied-by-scalar",
                    type="interactive",
                    duration_minutes=15,
                    why_prescribed="Practice calculating determinants"
                ),
            ],
            "inverse_matrix": [
                LearningResource(
                    title="Khan Academy: Matrix inverses",
                    url="https://www.khanacademy.org/math/algebra-home/alg-matrices/alg-intro-to-matrix-inverses",
                    type="interactive",
                    duration_minutes=20,
                    why_prescribed="Practice finding inverses"
                ),
            ],
            "eigenvalues": [
                LearningResource(
                    title="Khan Academy: Eigenvalues and eigenvectors",
                    url="https://www.khanacademy.org/math/linear-algebra/alternate-bases/eigen-everything/v/linear-algebra-introduction-to-eigenvalues-and-eigenvectors",
                    type="interactive",
                    duration_minutes=25,
                    why_prescribed="Step-by-step eigenvalue calculations"
                ),
            ],
        }

        return PRACTICE_RESOURCES.get(concept_id, [])

    # ==================== Formatting for Display ====================

    def format_prescription_for_display(self, prescription: LearningPrescription) -> str:
        """Format prescription as markdown for terminal/chat display."""
        lines = []

        # Header
        severity_emoji = ["🟢", "🟡", "🔴"][prescription.severity - 1]
        lines.append(f"# 📋 Learning Prescription")
        lines.append(f"**Concept:** {prescription.diagnosed_concept_name} {severity_emoji}")
        lines.append("")

        # Root cause if different
        if prescription.root_cause_name:
            lines.append(f"⚠️ **Root Cause Found:** Your foundation in **{prescription.root_cause_name}** needs strengthening first.")
            lines.append("")

        # Misconceptions
        if prescription.misconceptions:
            lines.append("## 🔍 Detected Issues")
            for m in prescription.misconceptions:
                lines.append(f"- {m.description}")
            lines.append("")

        # Treatment phases
        lines.append("## 💊 Treatment Plan")
        lines.append(f"*Total time: ~{prescription.total_estimated_minutes} minutes*")
        lines.append("")

        for i, phase in enumerate(prescription.phases, 1):
            lines.append(f"### {phase.icon} Phase {i}: {phase.title}")
            lines.append(phase.instructions)
            lines.append("")

            for r in phase.resources:
                timestamp_str = f" (start at {r.timestamp})" if r.timestamp else ""
                lines.append(f"- [{r.title}]({r.url}){timestamp_str}")
                if r.why_prescribed:
                    lines.append(f"  *{r.why_prescribed}*")
            lines.append("")

        # Verification
        lines.append("## ✅ Verification")
        lines.append(f"Pass {prescription.questions_to_pass}/{prescription.questions_total} questions to advance.")
        if prescription.must_show_work:
            lines.append("*Show your work for full credit.*")

        return "\n".join(lines)

    def to_frontend_format(self, prescription: LearningPrescription) -> Dict:
        """Convert prescription to structured format for frontend display."""
        return {
            "diagnosed_concept": prescription.diagnosed_concept,
            "diagnosed_concept_name": prescription.diagnosed_concept_name,
            "severity": prescription.severity,
            "root_cause": {
                "concept_id": prescription.root_cause_concept,
                "concept_name": prescription.root_cause_name
            } if prescription.root_cause_concept else None,
            "misconceptions": [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "severity": m.severity,
                    "remediation_concept": m.remediation_concept,
                    "remediation_focus": m.remediation_focus
                }
                for m in prescription.misconceptions
            ],
            "phases": [
                {
                    "phase": p.phase.value,
                    "title": p.title,
                    "icon": p.icon,
                    "instructions": p.instructions,
                    "estimated_minutes": p.estimated_minutes,
                    "resources": [
                        {
                            "title": r.title,
                            "url": r.url,
                            "type": r.type,
                            "timestamp": r.timestamp,
                            "duration_minutes": r.duration_minutes,
                            "why_prescribed": r.why_prescribed
                        }
                        for r in p.resources
                    ]
                }
                for p in prescription.phases
            ],
            "total_estimated_minutes": prescription.total_estimated_minutes,
            "verification": {
                "questions_to_pass": prescription.questions_to_pass,
                "questions_total": prescription.questions_total,
                "must_show_work": prescription.must_show_work
            }
        }
