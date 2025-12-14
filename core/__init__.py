"""
Core module - Knowledge modeling, adaptive testing, and misconception detection.

Components:
    - knowledge_graph: Concept dependency DAG with prerequisites
    - student_model: IRT-based ability estimation + forgetting curves
    - adaptive_tester: Computerized Adaptive Testing (CAT)
    - misconception_db: Wrong answer -> misconception mapping (legacy)
    - misconception_detector: Advanced misconception detection

Note: PrescriptionEngine has moved to teaching/ module.
"""

from .knowledge_graph import KnowledgeGraph
from .student_model import StudentModel
from .adaptive_tester import AdaptiveTester
from .misconception_db import MisconceptionDB
from .misconception_detector import MisconceptionDetector, Misconception, WrongAnswerAnalysis

__all__ = [
    "KnowledgeGraph",
    "StudentModel",
    "AdaptiveTester",
    "MisconceptionDB",
    "MisconceptionDetector",
    "Misconception",
    "WrongAnswerAnalysis",
]
