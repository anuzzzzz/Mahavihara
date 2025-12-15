"""
Prescription Engine - The "Doctor's Prescription" for Learning
VERSION 2.1 - Fixed circular root cause bug

FIXES:
- BUG-C02: Root cause no longer returns same concept (was circular)
- Now returns informative message when all prereqs are strong
"""

import os
import sys
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.misconception_detector import MisconceptionDetector
from teaching.resource_curator import ResourceCurator


@dataclass
class LearningPrescription:
    """A complete learning prescription - the 'doctor's note' for education"""

    # Diagnosis
    failed_concept: str
    root_cause: str
    misconception: Optional[str]
    misconception_explanation: Optional[str]
    confidence: float

    # Treatment
    phases: List[Dict]
    resources: List[Dict]

    # Verification
    verification_questions: List[str]
    success_criteria: str

    # Metadata
    estimated_time: str
    generated_at: str

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_frontend_format(self) -> Dict:
        """Format for beautiful frontend display"""
        return {
            "diagnosis": {
                "title": f"Why You're Struggling with {self.failed_concept}",
                "failed_concept": self.failed_concept,
                "root_cause": self.root_cause,
                "misconception": self.misconception,
                "explanation": self.misconception_explanation,
                "confidence": self.confidence
            },
            "prescription": {
                "title": "Your Learning Prescription",
                "phases": self.phases,
                "total_time": self.estimated_time
            },
            "resources": {
                "title": "Curated Resources",
                "items": self.resources
            },
            "verification": {
                "title": "Prove You've Got It",
                "criteria": self.success_criteria,
                "question_ids": self.verification_questions,
                "success_criteria": self.success_criteria
            }
        }


class PrescriptionEngine:
    """
    Generates personalized learning prescriptions.
    """

    # Prerequisite map for root cause tracing
    PREREQ_MAP = {
        "eigenvalues": ["inverse_matrix", "determinants", "matrix_ops", "vectors"],
        "inverse_matrix": ["determinants", "matrix_ops", "vectors"],
        "determinants": ["matrix_ops", "vectors"],
        "matrix_ops": ["vectors"],
        "vectors": []
    }
    
    # Human-readable concept names
    CONCEPT_NAMES = {
        "vectors": "Vectors",
        "matrix_ops": "Matrix Operations",
        "determinants": "Determinants",
        "inverse_matrix": "Inverse Matrices",
        "eigenvalues": "Eigenvalues"
    }

    def __init__(self, knowledge_graph=None):
        self.misconception_detector = MisconceptionDetector()
        self.resource_curator = ResourceCurator()
        self.kg = knowledge_graph

    def generate_prescription(
        self,
        failed_concept: str,
        wrong_answers: List[Dict],
        mastery_scores: Dict[str, float],
        learning_style: str = "visual"
    ) -> LearningPrescription:
        """Generate a complete learning prescription."""

        # ==================== STEP 1: DIAGNOSIS ====================

        # FIXED: Trace root cause with improved logic
        root_cause = self._trace_root_cause_fixed(failed_concept, mastery_scores)

        # Analyze wrong answers for misconceptions
        pattern_analysis = self.misconception_detector.analyze_answer_pattern(wrong_answers)

        primary_misconception = None
        misconception_explanation = None

        if pattern_analysis.get("most_critical"):
            mc = pattern_analysis["most_critical"].misconception
            primary_misconception = mc.name
            misconception_explanation = pattern_analysis["most_critical"].explanation

        confidence = self._calculate_diagnosis_confidence(
            len(wrong_answers),
            pattern_analysis.get("misconceptions", [])
        )

        # ==================== STEP 2: TREATMENT ====================

        # Determine target concept for resources
        # If root cause is different from failed concept, focus on root cause
        if root_cause and root_cause != failed_concept and not root_cause.startswith(failed_concept):
            target_concept = root_cause
        else:
            target_concept = failed_concept
            
        target_weakness = pattern_analysis.get("most_critical")
        weakness_focus = target_weakness.misconception.remediation_focus if target_weakness else None

        resources_data = self.resource_curator.get_prescription_resources(
            target_concept,
            mastery=mastery_scores.get(target_concept, 0.5)
        )

        phases = self._build_treatment_phases(
            target_concept,
            primary_misconception,
            resources_data,
            learning_style
        )

        resources = []
        for phase_key in ["understand", "practice"]:
            for r in resources_data.get(phase_key, []):
                resources.append({
                    "type": r.source_type,
                    "title": r.title,
                    "url": r.url,
                    "source": self._extract_source(r.url),
                    "why": r.why_recommended,
                    "timestamp": r.timestamp if hasattr(r, 'timestamp') else None
                })

        # ==================== STEP 3: VERIFICATION ====================

        verification_questions = self._select_verification_questions(
            target_concept,
            weakness_focus
        )

        success_criteria = self._generate_success_criteria(
            target_concept,
            primary_misconception
        )

        # ==================== GENERATE PRESCRIPTION ====================

        total_minutes = sum(
            self._parse_duration(p.get("duration", "0 min"))
            for p in phases
        )

        prescription = LearningPrescription(
            failed_concept=failed_concept,
            root_cause=root_cause,
            misconception=primary_misconception,
            misconception_explanation=misconception_explanation,
            confidence=confidence,
            phases=phases,
            resources=resources,
            verification_questions=verification_questions,
            success_criteria=success_criteria,
            estimated_time=f"{total_minutes} minutes",
            generated_at=datetime.now().isoformat()
        )

        return prescription

    def _trace_root_cause_fixed(
        self,
        failed_concept: str,
        mastery_scores: Dict[str, float]
    ) -> str:
        """
        FIXED: Trace back through prerequisites to find root cause.
        
        Key improvements:
        1. NEVER returns the same concept name (avoids circular message)
        2. If all prereqs are strong, explains it's a NEW gap in this concept
        3. Returns human-readable explanation
        """
        # If we have a knowledge graph with trace_root_cause, use it
        if self.kg and hasattr(self.kg, 'trace_root_cause'):
            result = self.kg.trace_root_cause(failed_concept, mastery_scores)
            # Still check for circular result
            if result == failed_concept:
                return self._get_non_circular_diagnosis(failed_concept, mastery_scores)
            return result

        # Use simplified logic
        prereqs = self.PREREQ_MAP.get(failed_concept, [])
        WEAK_THRESHOLD = 0.6

        if not prereqs:
            # No prerequisites - this is a foundation concept
            concept_name = self.CONCEPT_NAMES.get(failed_concept, failed_concept)
            return f"{concept_name} fundamentals"

        # Check for weak prerequisites
        weak_prereqs = []
        for prereq in prereqs:
            mastery = mastery_scores.get(prereq, 0.5)
            if mastery < WEAK_THRESHOLD:
                weak_prereqs.append((prereq, mastery))

        if weak_prereqs:
            # Return the weakest prerequisite
            weakest = min(weak_prereqs, key=lambda x: x[1])
            return weakest[0]

        # All prereqs are strong - this is a NEW gap in THIS concept
        return self._get_non_circular_diagnosis(failed_concept, mastery_scores)

    def _get_non_circular_diagnosis(
        self, 
        failed_concept: str, 
        mastery_scores: Dict[str, float]
    ) -> str:
        """
        Generate a non-circular root cause message.
        
        Instead of "determinants traces to determinants", we say:
        "New gaps in Determinants (prerequisites are solid)"
        """
        concept_name = self.CONCEPT_NAMES.get(failed_concept, failed_concept)
        
        # Check if this is a foundation concept
        prereqs = self.PREREQ_MAP.get(failed_concept, [])
        if not prereqs:
            return f"{concept_name} core concepts"
        
        # Check prereq strength
        all_strong = all(
            mastery_scores.get(p, 0.5) >= 0.6 
            for p in prereqs
        )
        
        if all_strong:
            return f"new gaps in {concept_name} itself (prerequisites are solid)"
        else:
            # Find the borderline prereq
            weakest_prereq = min(prereqs, key=lambda p: mastery_scores.get(p, 0.5))
            weakest_score = mastery_scores.get(weakest_prereq, 0.5)
            if weakest_score < 0.7:  # Borderline
                prereq_name = self.CONCEPT_NAMES.get(weakest_prereq, weakest_prereq)
                return f"borderline understanding of {prereq_name}"
        
        return f"{concept_name} application"

    def _calculate_diagnosis_confidence(
        self,
        num_wrong: int,
        misconceptions: List
    ) -> float:
        """Calculate how confident we are in the diagnosis"""

        base_confidence = 0.5

        if num_wrong >= 3:
            base_confidence += 0.2
        elif num_wrong >= 2:
            base_confidence += 0.1

        if misconceptions:
            base_confidence += 0.1 * min(len(misconceptions), 3)

        return min(0.95, base_confidence)

    def _build_treatment_phases(
        self,
        target_concept: str,
        misconception: Optional[str],
        resources_data: Dict[str, List],
        learning_style: str
    ) -> List[Dict]:
        """Build a phased treatment plan."""

        phases = []
        phase_num = 1

        # Phase 1: Watch/Read to understand
        understand_resources = resources_data.get("understand", [])
        if understand_resources:
            r = understand_resources[0]
            phases.append({
                "phase": phase_num,
                "action": "Watch" if r.source_type == "youtube" else "Read",
                "title": r.title,
                "url": r.url,
                "source": self._extract_source(r.url),
                "duration": f"{r.duration_minutes or 5} min",
                "instruction": self._get_watch_instruction(misconception),
                "icon": "🎬" if r.source_type == "youtube" else "📖"
            })
            phase_num += 1

        # Phase 2: Practice
        practice_resources = resources_data.get("practice", [])
        if practice_resources:
            r = practice_resources[0]
            phases.append({
                "phase": phase_num,
                "action": "Practice",
                "title": r.title,
                "url": r.url,
                "source": self._extract_source(r.url),
                "duration": f"{r.duration_minutes or 10} min",
                "instruction": "Work through the practice problems",
                "icon": "✏️"
            })
            phase_num += 1

        # Phase 3: Verification Quiz
        phases.append({
            "phase": phase_num,
            "action": "Verify",
            "title": "Take Verification Quiz",
            "url": None,
            "source": "mahavihara",
            "duration": "3 min",
            "instruction": "Pass 2/3 questions to demonstrate mastery",
            "icon": "✅"
        })

        return phases

    def _get_watch_instruction(self, misconception: Optional[str]) -> str:
        """Get specific instruction for watching/reading."""
        if misconception:
            return f"Focus on understanding: {misconception}"
        return "Pay attention to the core concepts and examples"

    def _select_verification_questions(
        self,
        concept_id: str,
        weakness_focus: Optional[str]
    ) -> List[str]:
        """Select questions for verification."""
        return [f"{concept_id}_v1", f"{concept_id}_v2", f"{concept_id}_v3"]

    def _generate_success_criteria(
        self,
        concept_id: str,
        misconception: Optional[str]
    ) -> str:
        """Generate success criteria message."""
        concept_name = self.CONCEPT_NAMES.get(concept_id, concept_id)
        
        if misconception:
            return f"Answer 2/3 questions on {concept_name} correctly, demonstrating you no longer have the '{misconception}' issue"
        return f"Answer 2/3 questions on {concept_name} correctly"

    def _extract_source(self, url: str) -> str:
        """Extract source name from URL."""
        if "youtube" in url or "youtu.be" in url:
            return "YouTube"
        elif "khanacademy" in url:
            return "Khan Academy"
        elif "brilliant" in url:
            return "Brilliant"
        elif "3blue1brown" in url.lower():
            return "3Blue1Brown"
        return "Web"

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to minutes."""
        match = re.search(r'(\d+)', duration_str)
        return int(match.group(1)) if match else 5


def format_prescription_for_display(prescription: LearningPrescription) -> str:
    """Format prescription as readable text."""
    output = []
    
    output.append("=" * 60)
    output.append("📋 YOUR LEARNING PRESCRIPTION")
    output.append("=" * 60)

    output.append("")
    output.append("🔍 DIAGNOSIS")
    output.append("-" * 40)
    output.append(f"Failed: {prescription.failed_concept}")
    output.append(f"Root Cause: {prescription.root_cause}")
    if prescription.misconception:
        output.append(f"Misconception: {prescription.misconception}")
        if prescription.misconception_explanation:
            output.append(f"  → {prescription.misconception_explanation}")
    output.append(f"Confidence: {int(prescription.confidence * 100)}%")

    output.append("")
    output.append("💊 TREATMENT PLAN")
    output.append("-" * 40)
    for phase in prescription.phases:
        icon = phase.get("icon", "•")
        output.append(f"{icon} Phase {phase['phase']}: {phase['action']} ({phase['duration']})")
        output.append(f"   {phase['title']}")
        if phase.get('url'):
            output.append(f"   🔗 {phase['url']}")
        if phase.get('instruction'):
            output.append(f"   💡 {phase['instruction']}")

    output.append("")
    output.append("📚 RESOURCES")
    output.append("-" * 40)
    for resource in prescription.resources[:3]:
        output.append(f"[{resource['type']}] {resource['title']}")
        output.append(f"   Source: {resource['source']}")
        if resource.get('why'):
            output.append(f"   Why: {resource['why']}")

    output.append("")
    output.append("✅ VERIFICATION")
    output.append("-" * 40)
    output.append(prescription.success_criteria)

    output.append("")
    output.append(f"⏱️  Estimated time: {prescription.estimated_time}")
    output.append("=" * 60)

    return "\n".join(output)


if __name__ == "__main__":
    engine = PrescriptionEngine()

    print("=== Prescription Engine Test (Fixed) ===\n")

    # Test case 1: All prereqs strong (was causing circular bug)
    print("TEST 1: All prereqs strong (should NOT be circular)")
    print("-" * 40)
    
    mastery_scores_strong = {
        "vectors": 0.75,      # Strong (passed)
        "matrix_ops": 0.75,   # Strong (passed)
        "determinants": 0.3,  # Weak (just failed)
        "inverse_matrix": 0.5,
        "eigenvalues": 0.5
    }

    prescription = engine.generate_prescription(
        failed_concept="determinants",
        wrong_answers=[
            {"question_id": "det_1", "chosen": 0, "correct": 1, "is_correct": False},
            {"question_id": "det_2", "chosen": 0, "correct": 1, "is_correct": False},
        ],
        mastery_scores=mastery_scores_strong,
        learning_style="visual"
    )

    print(f"Failed concept: {prescription.failed_concept}")
    print(f"Root cause: {prescription.root_cause}")
    print(f"Is circular? {prescription.root_cause == prescription.failed_concept}")
    
    # Test case 2: Weak prerequisite exists
    print("\n\nTEST 2: Weak prerequisite exists")
    print("-" * 40)
    
    mastery_scores_weak = {
        "vectors": 0.75,
        "matrix_ops": 0.4,    # Weak!
        "determinants": 0.3,
        "inverse_matrix": 0.5,
        "eigenvalues": 0.5
    }

    prescription2 = engine.generate_prescription(
        failed_concept="determinants",
        wrong_answers=[
            {"question_id": "det_1", "chosen": 0, "correct": 1, "is_correct": False},
        ],
        mastery_scores=mastery_scores_weak,
        learning_style="visual"
    )

    print(f"Failed concept: {prescription2.failed_concept}")
    print(f"Root cause: {prescription2.root_cause}")
    print(f"Correctly identified weak prereq? {prescription2.root_cause == 'matrix_ops'}")