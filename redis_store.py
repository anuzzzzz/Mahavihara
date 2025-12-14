"""
Redis Store - Session and mastery state management.

Key Structure:
    session:{session_id}:state   -> Hash (phase, root_cause, questions_asked)
    session:{session_id}:mastery -> Hash (concept_id -> score)
    session:{session_id}:answers -> List (JSON of each answer)
"""

import os
import json
import redis
from typing import Dict, Optional, List
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


class RedisStore:
    def __init__(self):
        """Connect to Redis using environment variables."""
        self.client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True  # Return strings instead of bytes
        )
        
        # Default mastery score for new concepts
        self.DEFAULT_MASTERY = 0.5
        
        # All concept IDs (must match differentiation.json)
        self.CONCEPTS = [
        "vectors",
        "matrix_ops",
        "determinants",
        "inverse_matrix",
        "eigenvalues"
        ]


    # ==================== Key Builders ====================

    def _state_key(self, session_id: str) -> str:
        """Redis key for session state."""
        return f"session:{session_id}:state"

    def _mastery_key(self, session_id: str) -> str:
        """Redis key for mastery scores."""
        return f"session:{session_id}:mastery"

    def _answers_key(self, session_id: str) -> str:
        """Redis key for answer history."""
        return f"session:{session_id}:answers"

    # ==================== Session Management ====================

    def create_session(self, session_id: str) -> Dict:
        """
        Initialize a new session with default values.
        
        Creates:
            - State hash (phase, questions_asked, root_cause)
            - Mastery hash (all concepts at 0.5)
            
        Args:
            session_id: Unique session identifier
            
        Returns:
            Dict with initial session state
        """
        state_key = self._state_key(session_id)
        mastery_key = self._mastery_key(session_id)
        
        # Initial state
        initial_state = {
            "phase": "diagnostic",
            "questions_asked": "0",
            "root_cause": ""
        }
        
        # Store state hash
        self.client.hset(state_key, mapping=initial_state)
        
        # Initialize mastery for all concepts at 0.5
        initial_mastery = {c: self.DEFAULT_MASTERY for c in self.CONCEPTS}
        self.client.hset(mastery_key, mapping=initial_mastery)
        
        return {
            "session_id": session_id,
            "state": initial_state,
            "mastery": initial_mastery
        }

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Retrieve full session state from Redis.
        
        Args:
            session_id: Session to retrieve
            
        Returns:
            Dict with state and mastery, or None if not found
        """
        state_key = self._state_key(session_id)
        mastery_key = self._mastery_key(session_id)
        
        # Check if session exists
        if not self.client.exists(state_key):
            return None
        
        # Get state
        state = self.client.hgetall(state_key)
        
        # Get mastery scores (convert string values to float)
        mastery_raw = self.client.hgetall(mastery_key)
        mastery = {k: float(v) for k, v in mastery_raw.items()}
        
        return {
            "session_id": session_id,
            "state": state,
            "mastery": mastery
        }

    def get_or_create_session(self, session_id: str) -> Dict:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data (existing or newly created)
        """
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)
        return session

    def delete_session(self, session_id: str):
        """
        Delete all data for a session (for testing/cleanup).
        
        Args:
            session_id: Session to delete
        """
        self.client.delete(
            self._state_key(session_id),
            self._mastery_key(session_id),
            self._answers_key(session_id)
        )

    # ==================== Mastery Management ====================

    def get_mastery(self, session_id: str) -> Dict[str, float]:
        """
        Get mastery scores for all concepts.
        
        Args:
            session_id: Session to query
            
        Returns:
            Dict of concept_id -> mastery score
        """
        mastery_key = self._mastery_key(session_id)
        mastery_raw = self.client.hgetall(mastery_key)
        return {k: float(v) for k, v in mastery_raw.items()}

    def update_mastery(self, session_id: str, concept_id: str, is_correct: bool) -> float:
        """
        Update mastery score based on answer correctness.
        
        Scoring:
            - Correct: +0.15
            - Wrong: -0.20 (punish harder to encourage learning)
            - Clamped between 0.0 and 1.0
            
        Args:
            session_id: Session to update
            concept_id: Concept that was tested
            is_correct: Whether the answer was correct
            
        Returns:
            New mastery score
        """
        mastery_key = self._mastery_key(session_id)
        
        # Get current score
        current = float(self.client.hget(mastery_key, concept_id) or self.DEFAULT_MASTERY)
        
        # Calculate new score
        if is_correct:
            new_score = current + 0.15
        else:
            new_score = current - 0.20
        
        # Clamp between 0 and 1
        new_score = max(0.0, min(1.0, new_score))
        
        # Store updated score
        self.client.hset(mastery_key, concept_id, new_score)
        
        return new_score

    # ==================== Answer Recording ====================

    def record_answer(self, session_id: str, question_id: str, concept_id: str, is_correct: bool):
        """
        Log an answer for analytics.
        
        Args:
            session_id: Session ID
            question_id: Question that was answered
            concept_id: Concept being tested
            is_correct: Whether answer was correct
        """
        answers_key = self._answers_key(session_id)
        
        answer_record = json.dumps({
            "question_id": question_id,
            "concept_id": concept_id,
            "is_correct": is_correct
        })
        
        # Append to list
        self.client.rpush(answers_key, answer_record)

    def get_answers(self, session_id: str) -> List[Dict]:
        """
        Get all recorded answers for a session.
        
        Args:
            session_id: Session to query
            
        Returns:
            List of answer records
        """
        answers_key = self._answers_key(session_id)
        answers_raw = self.client.lrange(answers_key, 0, -1)
        return [json.loads(a) for a in answers_raw]

    # ==================== Phase Management ====================

    def get_phase(self, session_id: str) -> str:
        """
        Get current phase of the session.
        
        Args:
            session_id: Session to query
            
        Returns:
            Current phase string
        """
        state_key = self._state_key(session_id)
        return self.client.hget(state_key, "phase") or "diagnostic"

    def set_phase(self, session_id: str, phase: str):
        """
        Update the current phase of the session.
        
        Phases: diagnostic -> analyzing -> teaching -> verifying -> complete
        
        Args:
            session_id: Session to update
            phase: New phase name
        """
        state_key = self._state_key(session_id)
        self.client.hset(state_key, "phase", phase)

    # ==================== Root Cause Management ====================

    def get_root_cause(self, session_id: str) -> str:
        """
        Get the identified root cause concept.
        
        Args:
            session_id: Session to query
            
        Returns:
            Root cause concept ID or empty string
        """
        state_key = self._state_key(session_id)
        return self.client.hget(state_key, "root_cause") or ""

    def set_root_cause(self, session_id: str, concept_id: str):
        """
        Store the identified root cause concept.
        
        Args:
            session_id: Session to update
            concept_id: The root cause concept ID
        """
        state_key = self._state_key(session_id)
        self.client.hset(state_key, "root_cause", concept_id)

    # ==================== Questions Counter ====================

    def get_questions_asked(self, session_id: str) -> int:
        """
        Get number of questions asked in session.
        
        Args:
            session_id: Session to query
            
        Returns:
            Count of questions asked
        """
        state_key = self._state_key(session_id)
        return int(self.client.hget(state_key, "questions_asked") or 0)

    def increment_questions_asked(self, session_id: str) -> int:
        """
        Increment and return the questions asked counter.

        Args:
            session_id: Session to update

        Returns:
            New count of questions asked
        """
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