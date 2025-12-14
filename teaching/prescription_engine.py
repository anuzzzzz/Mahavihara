"""
Prescription Engine - The "Doctor's Prescription" for Learning

This is the CORE DIFFERENTIATOR:

ChatGPT says: "You got eigenvalues wrong. Let me explain eigenvalues..."
Mahavihara says: "You confused eigenvector with eigenvalue. Watch 3B1B at 4:32,
                  then do these 3 problems. Expected fix time: 8 minutes."

The prescription is:
1. Diagnosis (what's wrong, why)
2. Treatment (specific resources, specific problems)
3. Verification (prove you fixed it)
"""

import os
import sys
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Import our modules
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
    phases: List[Dict]  # [{action, resource, duration, instruction}]
    resources: List[Dict]  # Full resource details

    # Verification
    verification_questions: List[str]  # Question IDs to verify fix
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

    The flow:
    1. Student fails a concept
    2. Detect root cause (knowledge graph tracing)
    3. Detect specific misconception (from wrong answer)
    4. Find targeted resources (web search + curated)
    5. Generate phased prescription
    6. Define verification criteria
    """

    # Prerequisite map for root cause tracing
    PREREQ_MAP = {
        "eigenvalues": ["inverse_matrix", "determinants", "matrix_ops", "vectors"],
        "inverse_matrix": ["determinants", "matrix_ops", "vectors"],
        "determinants": ["matrix_ops", "vectors"],
        "matrix_ops": ["vectors"],
        "vectors": []
    }

    def __init__(self, knowledge_graph=None):
        self.misconception_detector = MisconceptionDetector()
        self.resource_curator = ResourceCurator()
        self.kg = knowledge_graph  # Optional: for root cause tracing

    def generate_prescription(
        self,
        failed_concept: str,
        wrong_answers: List[Dict],  # From quiz
        mastery_scores: Dict[str, float],
        learning_style: str = "visual"
    ) -> LearningPrescription:
        """
        Generate a complete learning prescription.

        Args:
            failed_concept: The concept the student failed
            wrong_answers: List of wrong answer data from quiz
            mastery_scores: Current mastery scores for all concepts
            learning_style: "visual", "reading", or "practice"

        Returns:
            LearningPrescription with diagnosis, treatment, verification
        """

        # ==================== STEP 1: DIAGNOSIS ====================

        # Trace root cause through knowledge graph
        root_cause = self._trace_root_cause(failed_concept, mastery_scores)

        # Analyze wrong answers for misconceptions
        pattern_analysis = self.misconception_detector.analyze_answer_pattern(wrong_answers)

        primary_misconception = None
        misconception_explanation = None

        if pattern_analysis.get("most_critical"):
            mc = pattern_analysis["most_critical"].misconception
            primary_misconception = mc.name
            misconception_explanation = pattern_analysis["most_critical"].explanation

        # Calculate confidence
        confidence = self._calculate_diagnosis_confidence(
            len(wrong_answers),
            pattern_analysis.get("misconceptions", [])
        )

        # ==================== STEP 2: TREATMENT ====================

        # Get targeted resources
        target_concept = root_cause if root_cause != failed_concept else failed_concept
        target_weakness = pattern_analysis.get("most_critical")
        weakness_focus = target_weakness.misconception.remediation_focus if target_weakness else None

        resources_data = self.resource_curator.get_prescription_resources(
            target_concept,
            mastery=mastery_scores.get(target_concept, 0.5)
        )

        # Build phased treatment plan
        phases = self._build_treatment_phases(
            target_concept,
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
                    "why": r.why_recommended,
                    "timestamp": r.timestamp
                })

        # ==================== STEP 3: VERIFICATION ====================

        # Select verification questions
        verification_questions = self._select_verification_questions(
            target_concept,
            weakness_focus
        )

        success_criteria = self._generate_success_criteria(
            target_concept,
            primary_misconception
        )

        # ==================== GENERATE PRESCRIPTION ====================

        # Calculate total time
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

    def _trace_root_cause(
        self,
        failed_concept: str,
        mastery_scores: Dict[str, float]
    ) -> str:
        """Trace back through prerequisites to find root cause"""

        # If we have a knowledge graph, use it
        if self.kg and hasattr(self.kg, 'trace_root_cause'):
            return self.kg.trace_root_cause(failed_concept, mastery_scores)

        # Otherwise, use simplified logic
        prereqs = self.PREREQ_MAP.get(failed_concept, [])
        WEAK_THRESHOLD = 0.6

        for prereq in prereqs:
            if mastery_scores.get(prereq, 0.5) < WEAK_THRESHOLD:
                return prereq

        return failed_concept

    def _calculate_diagnosis_confidence(
        self,
        num_wrong: int,
        misconceptions: List
    ) -> float:
        """Calculate how confident we are in the diagnosis"""

        base_confidence = 0.5

        # More wrong answers = more data = higher confidence
        if num_wrong >= 3:
            base_confidence += 0.2
        elif num_wrong >= 2:
            base_confidence += 0.1

        # Detected misconceptions increase confidence
        if misconceptions:
            known_misconceptions = [m for m in misconceptions if m.misconception.id != "unknown"]
            if len(known_misconceptions) >= 2:
                base_confidence += 0.2
            elif len(known_misconceptions) >= 1:
                base_confidence += 0.1

        return min(base_confidence, 0.95)

    def _build_treatment_phases(
        self,
        target_concept: str,
        misconception: Optional[str],
        resources_data: Dict,
        learning_style: str
    ) -> List[Dict]:
        """Build the phased treatment plan"""

        phases = []
        phase_num = 1

        # Get resources by type
        understand_resources = resources_data.get("understand", [])
        practice_resources = resources_data.get("practice", [])

        videos = [r for r in understand_resources if r.source_type == "youtube"]
        articles = [r for r in understand_resources if r.source_type == "article"]
        interactives = [r for r in practice_resources if r.source_type == "interactive"]

        # Phase 1: Understand (video/article)
        if learning_style == "visual" and videos:
            primary_resource = videos[0]
            phases.append({
                "phase": phase_num,
                "action": "Watch",
                "title": primary_resource.title,
                "url": primary_resource.url,
                "source": self._extract_source(primary_resource.url),
                "duration": f"{primary_resource.duration_minutes or 5} min",
                "timestamp": primary_resource.timestamp,
                "instruction": f"Focus on: {misconception or 'core concept'}",
                "icon": "🎬"
            })
        elif articles:
            primary_resource = articles[0]
            phases.append({
                "phase": phase_num,
                "action": "Read",
                "title": primary_resource.title,
                "url": primary_resource.url,
                "source": self._extract_source(primary_resource.url),
                "duration": "5 min",
                "instruction": "Focus on the examples",
                "icon": "📖"
            })
        elif videos:
            # Fallback to video even if not visual learning style
            primary_resource = videos[0]
            phases.append({
                "phase": phase_num,
                "action": "Watch",
                "title": primary_resource.title,
                "url": primary_resource.url,
                "source": self._extract_source(primary_resource.url),
                "duration": f"{primary_resource.duration_minutes or 5} min",
                "timestamp": primary_resource.timestamp,
                "instruction": f"Focus on: {misconception or 'core concept'}",
                "icon": "🎬"
            })
        else:
            # Fallback: LLM explanation
            phases.append({
                "phase": phase_num,
                "action": "Review",
                "title": f"AI-Guided {target_concept} Review",
                "url": None,
                "source": "mahavihara",
                "duration": "3 min",
                "instruction": "I'll walk you through the key concepts",
                "icon": "🤖"
            })
        phase_num += 1

        # Phase 2: Interact (if interactive resource available)
        if interactives:
            phases.append({
                "phase": phase_num,
                "action": "Experiment",
                "title": interactives[0].title,
                "url": interactives[0].url,
                "source": self._extract_source(interactives[0].url),
                "duration": "3 min",
                "instruction": "Play until it clicks - try edge cases",
                "icon": "🔬"
            })
            phase_num += 1

        # Phase 3: Practice
        phases.append({
            "phase": phase_num,
            "action": "Practice",
            "title": f"Targeted {target_concept} Problems",
            "url": None,
            "source": "mahavihara",
            "duration": "5 min",
            "instruction": "3 problems specifically testing your weak spot",
            "icon": "✏️"
        })
        phase_num += 1

        # Phase 4: Verify
        phases.append({
            "phase": phase_num,
            "action": "Prove It",
            "title": "Verification Quiz",
            "url": None,
            "source": "mahavihara",
            "duration": "2 min",
            "instruction": "Show me you've got it - 2/3 correct to pass",
            "icon": "✅"
        })

        return phases

    def _extract_source(self, url: str) -> str:
        """Extract source name from URL"""
        if not url:
            return "mahavihara"

        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            # Try to extract channel from title or default to YouTube
            if "3blue1brown" in url_lower or "3b1b" in url_lower:
                return "3Blue1Brown"
            elif "khan" in url_lower:
                return "Khan Academy"
            return "YouTube"
        elif "khanacademy.org" in url_lower:
            return "Khan Academy"
        elif "brilliant.org" in url_lower:
            return "Brilliant"
        elif "mit.edu" in url_lower:
            return "MIT"
        elif "wolfram" in url_lower:
            return "Wolfram"
        return "Web"

    def _select_verification_questions(
        self,
        concept: str,
        weakness_focus: Optional[str]
    ) -> List[str]:
        """Select questions to verify the fix"""

        # In a real implementation, this would query the knowledge graph
        concept_prefix = {
            "vectors": "vec",
            "matrix_ops": "mat",
            "determinants": "det",
            "inverse_matrix": "inv",
            "eigenvalues": "eig"
        }.get(concept, "q")

        return [f"{concept_prefix}_{i}" for i in range(1, 4)]

    def _generate_success_criteria(
        self,
        concept: str,
        misconception: Optional[str]
    ) -> str:
        """Generate human-readable success criteria"""

        if misconception:
            return f"Answer 2/3 questions on {concept} correctly, demonstrating you no longer have the '{misconception}' issue"
        return f"Answer 2/3 questions on {concept} correctly"

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to minutes"""
        match = re.search(r'(\d+)', duration_str)
        return int(match.group(1)) if match else 0


# ==================== FRONTEND-FRIENDLY OUTPUT ====================

def format_prescription_for_display(prescription: LearningPrescription) -> str:
    """Format prescription as beautiful terminal output (for testing)"""

    output = []
    output.append("=" * 60)
    output.append("📋 YOUR LEARNING PRESCRIPTION")
    output.append("=" * 60)

    # Diagnosis
    output.append("")
    output.append("🔍 DIAGNOSIS")
    output.append("-" * 40)
    output.append(f"Failed: {prescription.failed_concept}")
    output.append(f"Root Cause: {prescription.root_cause}")
    if prescription.misconception:
        output.append(f"Misconception: {prescription.misconception}")
        output.append(f"  → {prescription.misconception_explanation}")
    output.append(f"Confidence: {int(prescription.confidence * 100)}%")

    # Treatment
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

    # Resources
    output.append("")
    output.append("📚 RESOURCES")
    output.append("-" * 40)
    for resource in prescription.resources[:3]:  # Top 3
        output.append(f"[{resource['type']}] {resource['title']}")
        output.append(f"   Source: {resource['source']}")
        output.append(f"   Why: {resource['why']}")

    # Verification
    output.append("")
    output.append("✅ VERIFICATION")
    output.append("-" * 40)
    output.append(prescription.success_criteria)

    output.append("")
    output.append(f"⏱️  Estimated time: {prescription.estimated_time}")
    output.append("=" * 60)

    return "\n".join(output)


# ==================== USAGE EXAMPLE ====================

if __name__ == "__main__":
    engine = PrescriptionEngine()

    print("=== Prescription Engine Test ===\n")

    # Simulate a student failing eigenvalues
    wrong_answers = [
        {"question_id": "eig_1", "chosen": 0, "correct": 1, "is_correct": False},
        {"question_id": "eig_5", "chosen": 0, "correct": 1, "is_correct": False},
        {"question_id": "eig_3", "chosen": 1, "correct": 1, "is_correct": True},
    ]

    mastery_scores = {
        "vectors": 0.8,
        "matrix_ops": 0.7,
        "determinants": 0.5,  # Weak prerequisite!
        "inverse_matrix": 0.6,
        "eigenvalues": 0.3
    }

    prescription = engine.generate_prescription(
        failed_concept="eigenvalues",
        wrong_answers=wrong_answers,
        mastery_scores=mastery_scores,
        learning_style="visual"
    )

    print(format_prescription_for_display(prescription))

    # Also show JSON format for frontend
    print("\n\n📱 Frontend Format (JSON):")
    print("-" * 40)
    import json
    print(json.dumps(prescription.to_frontend_format(), indent=2))
