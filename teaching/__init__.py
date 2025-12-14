"""
Teaching module - Socratic tutoring, resource curation, and prescriptions.

Components:
    - socratic_tutor: LLM-based Socratic dialogue
    - resource_curator: External resource discovery (YouTube, articles, Tavily search)
    - prescription_engine: Frontend-friendly prescription generation
"""

from .socratic_tutor import SocraticTutor, TutorContext
from .resource_curator import ResourceCurator, LearningResource
from .prescription_engine import PrescriptionEngine, LearningPrescription, format_prescription_for_display

__all__ = [
    "SocraticTutor",
    "TutorContext",
    "ResourceCurator",
    "LearningResource",
    "PrescriptionEngine",
    "LearningPrescription",
    "format_prescription_for_display",
]
