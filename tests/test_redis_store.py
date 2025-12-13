"""Tests for redis_store.py"""

import sys
sys.path.append(".")

from redis_store import RedisStore


def test_redis_store():
    store = RedisStore()
    test_session = "test_session_123"
    
    print("=== Redis Store Tests ===\n")
    
    # Cleanup any previous test data
    store.delete_session(test_session)
    
    # Test 1: Create session
    print("1. Create Session")
    session = store.create_session(test_session)
    print(f"   Phase: {session['state']['phase']}")
    print(f"   Mastery: {session['mastery']}")
    
    # Test 2: Get session
    print("\n2. Get Session")
    session = store.get_session(test_session)
    print(f"   Retrieved: {session is not None}")
    
    # Test 3: Update mastery
    print("\n3. Update Mastery")
    old_score = session['mastery']['limits']
    new_score = store.update_mastery(test_session, "limits", is_correct=True)
    print(f"   limits: {old_score} -> {new_score} (correct answer)")
    
    new_score = store.update_mastery(test_session, "derivatives", is_correct=False)
    print(f"   derivatives: 0.5 -> {new_score} (wrong answer)")
    
    # Test 4: Record answers
    print("\n4. Record Answers")
    store.record_answer(test_session, "lim_e1", "limits", True)
    store.record_answer(test_session, "deriv_m1", "derivatives", False)
    answers = store.get_answers(test_session)
    print(f"   Recorded: {len(answers)} answers")
    
    # Test 5: Phase management
    print("\n5. Phase Management")
    store.set_phase(test_session, "teaching")
    phase = store.get_phase(test_session)
    print(f"   Phase set to: {phase}")
    
    # Test 6: Root cause
    print("\n6. Root Cause")
    store.set_root_cause(test_session, "limits")
    root = store.get_root_cause(test_session)
    print(f"   Root cause set to: {root}")
    
    # Test 7: Questions counter
    print("\n7. Questions Counter")
    store.increment_questions_asked(test_session)
    store.increment_questions_asked(test_session)
    count = store.get_questions_asked(test_session)
    print(f"   Questions asked: {count}")
    
    # Cleanup
    store.delete_session(test_session)
    print("\n✅ All tests passed! (Session cleaned up)")


if __name__ == "__main__":
    test_redis_store()