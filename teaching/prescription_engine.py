"""
Prescription Engine - The "Doctor's Prescription" for Learning
VERSION 3.0 - COMPLETE FIX

THE BUG WAS:
- _trace_root_cause_fixed() returns "Vectors core concepts" (human string)
- This gets used as target_concept for resource_curator.get_prescription_resources()
- ResourceCurator looks for concept_id "Vectors core concepts" → NOT FOUND
- Returns empty resources → Prescription shows (0) resources, (1) phase

THE FIX:
- Return BOTH concept_id AND human-readable string separately
- Use concept_id for resource lookup
- Use human-readable for display
"""

import os
import sys
import re
from typing import Dict, List, Optional, Tuple
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
    root_cause: str  # Human-readable for display
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
    
    Flow:
    1. Student fails a quiz
    2. Detect root cause (prerequisite tracing)
    3. Detect misconception (from wrong answers)
    4. Get targeted resources (curated videos/practice)
    5. Generate phased prescription (Watch → Practice → Verify)
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

        # FIXED: Get BOTH concept_id AND human-readable description
        target_concept_id, root_cause_display = self._trace_root_cause_v3(
            failed_concept, 
            mastery_scores
        )

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

        # FIXED: Use concept_id (NOT human-readable string) for resource lookup
        resources_data = self.resource_curator.get_prescription_resources(
            target_concept_id,  # ← NOW CORRECT: "vectors" not "Vectors core concepts"
            mastery=mastery_scores.get(target_concept_id, 0.5)
        )

        # Build treatment phases with the resources
        phases = self._build_treatment_phases(
            target_concept_id,
            primary_misconception,
            resources_data,
            learning_style
        )

        # Format resources for prescription
        resources = []
        for phase_key in ["understand", "practice"]:
            for r in resources_data.get(phase_key, []):
                resources.append({
                    "type": r.source_type,
                    "title": r.title,
                    "url": r.url,
                    "source": self._extract_source(r.url),
                    "why": r.why_recommended if hasattr(r, 'why_recommended') else "",
                    "timestamp": r.timestamp if hasattr(r, 'timestamp') else None
                })

        # ==================== STEP 3: VERIFICATION ====================

        target_weakness = pattern_analysis.get("most_critical")
        weakness_focus = target_weakness.misconception.remediation_focus if target_weakness else None

        verification_questions = self._select_verification_questions(
            target_concept_id,
            weakness_focus
        )

        success_criteria = self._generate_success_criteria(
            target_concept_id,
            primary_misconception
        )

        # ==================== GENERATE PRESCRIPTION ====================

        total_minutes = sum(
            self._parse_duration(p.get("duration", "0 min"))
            for p in phases
        )
        
        # Minimum time estimate
        if total_minutes < 5:
            total_minutes = 15

        prescription = LearningPrescription(
            failed_concept=failed_concept,
            root_cause=root_cause_display,  # Human-readable for display
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

    def _trace_root_cause_v3(
        self,
        failed_concept: str,
        mastery_scores: Dict[str, float]
    ) -> Tuple[str, str]:
        """
        FIXED V3: Returns BOTH concept_id AND human-readable description.
        
        Returns:
            Tuple[str, str]: (concept_id, human_readable_description)
            
        Examples:
            ("vectors", "weak foundation in Vectors")
            ("matrix_ops", "gaps in Matrix Operations")
            ("determinants", "new concepts in Determinants (prerequisites solid)")
        """
        prereqs = self.PREREQ_MAP.get(failed_concept, [])
        WEAK_THRESHOLD = 0.6
        failed_concept_name = self.CONCEPT_NAMES.get(failed_concept, failed_concept)

        # Case 1: No prerequisites (foundation concept)
        if not prereqs:
            return (failed_concept, f"{failed_concept_name} core concepts")

        # Case 2: Check for weak prerequisites
        weak_prereqs = []
        for prereq in prereqs:
            mastery = mastery_scores.get(prereq, 0.5)
            if mastery < WEAK_THRESHOLD:
                weak_prereqs.append((prereq, mastery))

        if weak_prereqs:
            # Return the weakest prerequisite
            weakest = min(weak_prereqs, key=lambda x: x[1])
            weakest_id = weakest[0]
            weakest_name = self.CONCEPT_NAMES.get(weakest_id, weakest_id)
            return (weakest_id, f"weak foundation in {weakest_name}")

        # Case 3: All prereqs strong - focus on the failed concept itself
        return (failed_concept, f"new concepts in {failed_concept_name} (prerequisites solid)")

    def _build_treatment_phases(
        self,
        target_concept: str,
        misconception: Optional[str],
        resources_data: Dict[str, List],
        learning_style: str
    ) -> List[Dict]:
        """Build a phased treatment plan: Watch → Practice → Verify"""
        phases = []
        phase_num = 1
        concept_name = self.CONCEPT_NAMES.get(target_concept, target_concept)

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
                "duration": f"{r.duration_minutes or 10} min",
                "instruction": self._get_watch_instruction(misconception),
                "icon": "🎬" if r.source_type == "youtube" else "📖"
            })
            phase_num += 1
        else:
            # FALLBACK: Add default 3Blue1Brown resource
            phases.append({
                "phase": phase_num,
                "action": "Watch",
                "title": f"3Blue1Brown - {concept_name}",
                "url": "https://youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab",
                "source": "3Blue1Brown",
                "duration": "10 min",
                "instruction": self._get_watch_instruction(misconception),
                "icon": "🎬"
            })
            phase_num += 1

        # Phase 2: Practice (if available)
        practice_resources = resources_data.get("practice", [])
        if practice_resources:
            r = practice_resources[0]
            phases.append({
                "phase": phase_num,
                "action": "Practice",
                "title": r.title,
                "url": r.url,
                "source": self._extract_source(r.url),
                "duration": f"{r.duration_minutes or 15} min",
                "instruction": "Work through the practice problems",
                "icon": "✏️"
            })
            phase_num += 1
        else:
            # FALLBACK: Add Khan Academy practice
            phases.append({
                "phase": phase_num,
                "action": "Practice",
                "title": f"Khan Academy - {concept_name}",
                "url": f"https://www.khanacademy.org/math/linear-algebra",
                "source": "Khan Academy",
                "duration": "15 min",
                "instruction": "Work through practice problems",
                "icon": "✏️"
            })
            phase_num += 1

        # Phase 3: Verification Quiz (always present)
        phases.append({
            "phase": phase_num,
            "action": "Verify",
            "title": "Take Verification Quiz",
            "url": None,
            "source": "Mahavihara",
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

    def _calculate_diagnosis_confidence(
        self,
        num_wrong: int,
        misconceptions: List
    ) -> float:
        """Calculate how confident we are in the diagnosis."""
        base_confidence = 0.5

        if num_wrong >= 3:
            base_confidence += 0.2
        elif num_wrong >= 2:
            base_confidence += 0.1

        if misconceptions:
            base_confidence += 0.1 * min(len(misconceptions), 3)

        return min(0.95, base_confidence)

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
        if not url:
            return "Mahavihara"
        url_lower = url.lower()
        if "youtube" in url_lower or "youtu.be" in url_lower:
            if "3blue1brown" in url_lower:
                return "3Blue1Brown"
            return "YouTube"
        elif "khanacademy" in url_lower:
            return "Khan Academy"
        elif "brilliant" in url_lower:
            return "Brilliant"
        return "Web"

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to minutes."""
        if not duration_str:
            return 5
        match = re.search(r'(\d+)', str(duration_str))
        return int(match.group(1)) if match else 5


def format_prescription_for_display(prescription: LearningPrescription) -> str:
    """Format prescription as readable text for chat."""
    output = []
    
    output.append("=" * 50)
    output.append("📋 YOUR LEARNING PRESCRIPTION")
    output.append("=" * 50)

    output.append("")
    output.append("🔍 DIAGNOSIS")
    output.append("-" * 30)
    output.append(f"Failed: {prescription.failed_concept}")
    output.append(f"Root Cause: {prescription.root_cause}")
    if prescription.misconception:
        output.append(f"Misconception: {prescription.misconception}")
        if prescription.misconception_explanation:
            output.append(f"  → {prescription.misconception_explanation}")
    output.append(f"Confidence: {int(prescription.confidence * 100)}%")

    output.append("")
    output.append("💊 TREATMENT PLAN")
    output.append("-" * 30)
    for phase in prescription.phases:
        icon = phase.get("icon", "•")
        output.append(f"{icon} Phase {phase['phase']}: {phase['action']} ({phase['duration']})")
        output.append(f"   {phase['title']}")
        if phase.get('url'):
            output.append(f"   🔗 {phase['url']}")
        if phase.get('instruction'):
            output.append(f"   💡 {phase['instruction']}")

    if prescription.resources:
        output.append("")
        output.append("📚 RESOURCES")
        output.append("-" * 30)
        for resource in prescription.resources[:3]:
            output.append(f"[{resource['type']}] {resource['title']}")
            output.append(f"   Source: {resource['source']}")
            if resource.get('why'):
                output.append(f"   Why: {resource['why']}")

    output.append("")
    output.append("✅ VERIFICATION")
    output.append("-" * 30)
    output.append(prescription.success_criteria)

    output.append("")
    output.append(f"⏱️  Estimated time: {prescription.estimated_time}")
    output.append("=" * 50)

    return "\n".join(output)


# ==================== TEST ====================

if __name__ == "__main__":
    print("=" * 60)
    print("PRESCRIPTION ENGINE V3 - COMPLETE FIX TEST")
    print("=" * 60)
    
    engine = PrescriptionEngine()

    # Test 1: Vectors failed (foundation concept)
    print("\n🧪 TEST 1: Vectors failed (foundation)")
    print("-" * 40)
    
    mastery1 = {
        "vectors": 0.3,
        "matrix_ops": 0.5,
        "determinants": 0.5,
        "inverse_matrix": 0.5,
        "eigenvalues": 0.5
    }

    p1 = engine.generate_prescription(
        failed_concept="vectors",
        wrong_answers=[
            {"question_id": "vec_1", "chosen": 0, "correct": 1, "is_correct": False},
        ],
        mastery_scores=mastery1
    )

    print(f"✅ Root cause: {p1.root_cause}")
    print(f"✅ Phases: {len(p1.phases)}")
    print(f"✅ Resources: {len(p1.resources)}")
    for i, phase in enumerate(p1.phases):
        print(f"   Phase {i+1}: {phase['action']} - {phase['title'][:50]}...")
    
    assert len(p1.phases) >= 3, "Should have at least 3 phases!"
    assert len(p1.resources) >= 1, "Should have at least 1 resource!"
    
    # Test 2: Matrix ops failed, vectors weak
    print("\n🧪 TEST 2: Matrix ops failed, vectors weak")
    print("-" * 40)
    
    mastery2 = {
        "vectors": 0.4,      # Weak!
        "matrix_ops": 0.3,
        "determinants": 0.5,
        "inverse_matrix": 0.5,
        "eigenvalues": 0.5
    }

    p2 = engine.generate_prescription(
        failed_concept="matrix_ops",
        wrong_answers=[
            {"question_id": "mat_1", "chosen": 0, "correct": 1, "is_correct": False},
        ],
        mastery_scores=mastery2
    )

    print(f"✅ Root cause: {p2.root_cause}")
    print(f"✅ Should focus on vectors (weak prereq)")
    print(f"✅ Phases: {len(p2.phases)}")
    print(f"✅ Resources: {len(p2.resources)}")
    
    assert "Vectors" in p2.root_cause or "vectors" in p2.root_cause.lower(), "Should identify weak vectors!"

    # Test 3: Determinants failed, prereqs strong (was circular bug)
    print("\n🧪 TEST 3: Determinants failed, prereqs strong")
    print("-" * 40)
    
    mastery3 = {
        "vectors": 0.75,      # Strong
        "matrix_ops": 0.75,   # Strong
        "determinants": 0.3,  # Just failed
        "inverse_matrix": 0.5,
        "eigenvalues": 0.5
    }

    p3 = engine.generate_prescription(
        failed_concept="determinants",
        wrong_answers=[
            {"question_id": "det_1", "chosen": 0, "correct": 1, "is_correct": False},
        ],
        mastery_scores=mastery3
    )

    print(f"✅ Root cause: {p3.root_cause}")
    print(f"✅ Is circular (bad)? {'determinants traces to determinants' in p3.root_cause.lower()}")
    print(f"✅ Phases: {len(p3.phases)}")
    print(f"✅ Resources: {len(p3.resources)}")
    
    assert "determinants traces to determinants" not in p3.root_cause.lower(), "Should NOT be circular!"
    assert len(p3.phases) >= 3, "Should have 3 phases!"
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nTO DEPLOY:")
    print("  cp prescription_engine.py teaching/prescription_engine.py")
    print("  uvicorn api.main:app --reload --port 8000")