"""
Core module - Knowledge modeling, adaptive testing, and prescription generation.

Components:
    - knowledge_graph: Concept dependency DAG with prerequisites
    - student_model: IRT-based ability estimation + forgetting curves
    - adaptive_tester: Computerized Adaptive Testing (CAT)
    - misconception_db: Wrong answer -> misconception mapping (legacy)
    - misconception_detector: Advanced misconception detection
    - prescription_engine: Learning prescription generation
"""

from .knowledge_graph import KnowledgeGraph
from .student_model import StudentModel
from .adaptive_tester import AdaptiveTester
from .misconception_db import MisconceptionDB
from .misconception_detector import MisconceptionDetector, Misconception, WrongAnswerAnalysis
from .prescription_engine import PrescriptionEngine, LearningPrescription

__all__ = [
    "KnowledgeGraph",
    "StudentModel",
    "AdaptiveTester",
    "MisconceptionDB",
    "MisconceptionDetector",
    "Misconception",
    "WrongAnswerAnalysis",
    "PrescriptionEngine",
    "LearningPrescription",
]
