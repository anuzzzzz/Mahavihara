"""
Redis Store - Session and mastery state management.

Key Structure:
    session:{session_id}:state   -> Hash (phase, root_cause, questions_asked, teaching_turns, weak_concepts_queue)
    session:{session_id}:mastery -> Hash (concept_id -> score)
    session:{session_id}:answers -> List (JSON of each answer)
"""

import os
import json
import redis
from typing import Dict, Optional, List
from dotenv import load_dotenv

load_dotenv()


class RedisStore:
    def __init__(self):
        """Connect to Redis using environment variables."""
        self.client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True
        )
        
        self.DEFAULT_MASTERY = 0.5
        
        self.CONCEPTS = [
            "vectors",
            "matrix_ops",
            "determinants",
            "inverse_matrix",
            "eigenvalues"
        ]

    # ==================== Key Builders ====================

    def _state_key(self, session_id: str) -> str:
        return f"session:{session_id}:state"

    def _mastery_key(self, session_id: str) -> str:
        return f"session:{session_id}:mastery"

    def _answers_key(self, session_id: str) -> str:
        return f"session:{session_id}:answers"

    # ==================== Session Management ====================

    def create_session(self, session_id: str) -> Dict:
        """Initialize a new session with default values."""
        state_key = self._state_key(session_id)
        mastery_key = self._mastery_key(session_id)
        
        initial_state = {
            "phase": "diagnostic",
            "questions_asked": "0",
            "root_cause": "",
            "teaching_turns": "0",
            "weak_concepts_queue": ""
        }
        
        self.client.hset(state_key, mapping=initial_state)
        
        initial_mastery = {c: self.DEFAULT_MASTERY for c in self.CONCEPTS}
        self.client.hset(mastery_key, mapping=initial_mastery)
        
        return {
            "session_id": session_id,
            "state": initial_state,
            "mastery": initial_mastery
        }

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve full session state from Redis."""
        state_key = self._state_key(session_id)
        mastery_key = self._mastery_key(session_id)
        
        if not self.client.exists(state_key):
            return None
        
        state = self.client.hgetall(state_key)
        mastery_raw = self.client.hgetall(mastery_key)
        mastery = {k: float(v) for k, v in mastery_raw.items()}
        
        return {
            "session_id": session_id,
            "state": state,
            "mastery": mastery
        }

    def get_or_create_session(self, session_id: str) -> Dict:
        """Get existing session or create new one."""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)
        return session

    def delete_session(self, session_id: str):
        """Delete all data for a session."""
        self.client.delete(
            self._state_key(session_id),
            self._mastery_key(session_id),
            self._answers_key(session_id)
        )

    # ==================== Mastery Management ====================

    def get_mastery(self, session_id: str) -> Dict[str, float]:
        """Get mastery scores for all concepts."""
        mastery_key = self._mastery_key(session_id)
        mastery_raw = self.client.hgetall(mastery_key)
        return {k: float(v) for k, v in mastery_raw.items()}

    def update_mastery(self, session_id: str, concept_id: str, is_correct: bool) -> float:
        """
        Update mastery score based on answer correctness.
        Correct: +0.15, Wrong: -0.20
        """
        mastery_key = self._mastery_key(session_id)
        current = float(self.client.hget(mastery_key, concept_id) or self.DEFAULT_MASTERY)
        
        if is_correct:
            new_score = current + 0.15
        else:
            new_score = current - 0.20
        
        new_score = max(0.0, min(1.0, new_score))
        self.client.hset(mastery_key, concept_id, new_score)
        
        return new_score

    # ==================== Answer Recording ====================

    def record_answer(self, session_id: str, question_id: str, concept_id: str, is_correct: bool):
        """Log an answer for analytics."""
        answers_key = self._answers_key(session_id)
        
        answer_record = json.dumps({
            "question_id": question_id,
            "concept_id": concept_id,
            "is_correct": is_correct
        })
        
        self.client.rpush(answers_key, answer_record)

    def get_answers(self, session_id: str) -> List[Dict]:
        """Get all recorded answers for a session."""
        answers_key = self._answers_key(session_id)
        answers_raw = self.client.lrange(answers_key, 0, -1)
        return [json.loads(a) for a in answers_raw]

    def get_asked_questions(self, session_id: str) -> List[str]:
        """Get list of question IDs already asked."""
        answers = self.get_answers(session_id)
        return [a["question_id"] for a in answers]

    # ==================== Phase Management ====================

    def get_phase(self, session_id: str) -> str:
        """Get current phase of the session."""
        state_key = self._state_key(session_id)
        return self.client.hget(state_key, "phase") or "diagnostic"

    def set_phase(self, session_id: str, phase: str):
        """Update the current phase."""
        state_key = self._state_key(session_id)
        self.client.hset(state_key, "phase", phase)

    # ==================== Root Cause Management ====================

    def get_root_cause(self, session_id: str) -> str:
        """Get the identified root cause concept."""
        state_key = self._state_key(session_id)
        return self.client.hget(state_key, "root_cause") or ""

    def set_root_cause(self, session_id: str, concept_id: str):
        """Store the identified root cause concept."""
        state_key = self._state_key(session_id)
        self.client.hset(state_key, "root_cause", concept_id)

    # ==================== Questions Counter ====================

    def get_questions_asked(self, session_id: str) -> int:
        """Get number of diagnostic questions asked."""
        state_key = self._state_key(session_id)
        return int(self.client.hget(state_key, "questions_asked") or 0)

    def increment_questions_asked(self, session_id: str) -> int:
        """Increment and return questions asked counter."""
        state_key = self._state_key(session_id)
        return self.client.hincrby(state_key, "questions_asked", 1)

    # ==================== Teaching Turns Management ====================

    def get_teaching_turns(self, session_id: str) -> int:
        """Get number of teaching turns."""
        state_key = self._state_key(session_id)
        return int(self.client.hget(state_key, "teaching_turns") or 0)

    def increment_teaching_turns(self, session_id: str) -> int:
        """Increment and return teaching turns counter."""
        state_key = self._state_key(session_id)
        return self.client.hincrby(state_key, "teaching_turns", 1)

    def reset_teaching_turns(self, session_id: str):
        """Reset teaching turns to 0."""
        state_key = self._state_key(session_id)
        self.client.hset(state_key, "teaching_turns", 0)

    # ==================== Weak Concepts Queue ====================

    def get_weak_concepts_queue(self, session_id: str) -> List[str]:
        """Get the queue of concepts to teach."""
        state_key = self._state_key(session_id)
        queue = self.client.hget(state_key, "weak_concepts_queue") or ""
        return [c for c in queue.split(",") if c]  # Filter empty strings

    def set_weak_concepts_queue(self, session_id: str, concepts: List[str]):
        """Set the queue of concepts to teach."""
        state_key = self._state_key(session_id)
        self.client.hset(state_key, "weak_concepts_queue", ",".join(concepts))

    # ==================== Verification Progress ====================

    def get_verify_progress(self, session_id: str) -> dict:
        """Get verification progress for current concept."""
        state_key = self._state_key(session_id)
        asked = int(self.client.hget(state_key, "verify_questions_asked") or 0)
        correct = int(self.client.hget(state_key, "verify_correct") or 0)
        return {"asked": asked, "correct": correct}

    def update_verify_progress(self, session_id: str, is_correct: bool):
        """Update verification progress."""
        state_key = self._state_key(session_id)
        self.client.hincrby(state_key, "verify_questions_asked", 1)
        if is_correct:
            self.client.hincrby(state_key, "verify_correct", 1)

    def reset_verify_progress(self, session_id: str):
        """Reset verification progress for new concept."""
        state_key = self._state_key(session_id)
        self.client.hset(state_key, "verify_questions_asked", 0)
        self.client.hset(state_key, "verify_correct", 0)