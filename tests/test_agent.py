"""Tests for agent.py - Interactive test to see the full flow."""

import sys
sys.path.append(".")

from knowledge_graph import KnowledgeGraph
from redis_store import RedisStore
from agent import TutorAgent, diagnostic_node, analyze_node, AgentState
from langchain_core.messages import HumanMessage, AIMessage


def test_agent_flow():
    """Test the complete agent flow with simulated answers."""
    
    print("=" * 60)
    print("🧪 MAHAVIHARA AGENT TEST")
    print("=" * 60)
    
    # Initialize components
    store = RedisStore()
    kg = KnowledgeGraph()
    agent = TutorAgent()
    
    test_session = "test_agent_001"
    
    # Cleanup previous test
    store.delete_session(test_session)
    
    print("\n📍 Phase 1: Starting Session")
    print("-" * 40)
    
    # Start session - get first question
    result = agent.start_session(test_session)
    
    print(f"Phase: {result['phase']}")
    print(f"Mastery: {result['mastery']}")
    print(f"\nAgent says:")
    for msg in result['messages']:
        print(f"  {msg['content'][:100]}...")
    
    # Simulate diagnostic answers
    # We'll intentionally get some wrong to trigger root cause analysis
    print("\n📍 Phase 2: Diagnostic Questions")
    print("-" * 40)
    
    # Answers: some right, some wrong to create weak spots
    # This simulates a student weak in early concepts
    simulated_answers = [
        ("B", "limits - wrong"),        # Wrong - limits will be weak
        ("D", "continuity - wrong"),    # Wrong - continuity will be weak  
        ("B", "derivatives - correct"), # Correct
        ("B", "chain_rule - correct"),  # Correct
        ("A", "maxima_minima - wrong")  # Wrong
    ]
    
    for i, (answer, description) in enumerate(simulated_answers):
        print(f"\n  Question {i+1}: Answering '{answer}' ({description})")
        
        result = agent.process_message(test_session, answer)
        
        print(f"  Phase: {result['phase']}")
        
        # Show first response message
        if result['messages']:
            first_msg = result['messages'][0]['content']
            print(f"  Response: {first_msg[:80]}...")
    
    print("\n📍 Phase 3: Analysis & Root Cause")
    print("-" * 40)
    
    # Check what was identified
    root_cause = store.get_root_cause(test_session)
    mastery = store.get_mastery(test_session)
    phase = store.get_phase(test_session)
    
    print(f"Current Phase: {phase}")
    print(f"Root Cause Identified: {root_cause}")
    print(f"Mastery Scores:")
    for concept, score in mastery.items():
        status = "🟢" if score >= 0.6 else "🔴" if score < 0.4 else "🟡"
        print(f"  {status} {concept}: {score:.2f}")
    
    print("\n📍 Phase 4: Teaching Interaction")
    print("-" * 40)
    
    if phase == "teaching":
        # Simulate a teaching interaction
        teaching_response = "I think a limit is when x gets close to a value?"
        print(f"Student: {teaching_response}")
        
        result = agent.process_message(test_session, teaching_response)
        
        print(f"Phase: {result['phase']}")
        print("Agent response:")
        for msg in result['messages']:
            print(f"  {msg['content'][:150]}...")
    
    print("\n📍 Phase 5: Verification")
    print("-" * 40)
    
    phase = store.get_phase(test_session)
    
    if phase == "verifying":
        # Answer verification question correctly
        print("Answering verification question: 'C'")
        
        result = agent.process_message(test_session, "C")
        
        print(f"Phase: {result['phase']}")
        print("Agent response:")
        for msg in result['messages']:
            print(f"  {msg['content'][:150]}...")
    
    # Final state
    print("\n📍 Final State")
    print("-" * 40)
    
    final_mastery = store.get_mastery(test_session)
    final_phase = store.get_phase(test_session)
    answers = store.get_answers(test_session)
    
    print(f"Phase: {final_phase}")
    print(f"Total Answers Recorded: {len(answers)}")
    print(f"Final Mastery:")
    for concept, score in final_mastery.items():
        status = "🟢" if score >= 0.6 else "🔴" if score < 0.4 else "🟡"
        print(f"  {status} {concept}: {score:.2f}")
    
    # Cleanup
    store.delete_session(test_session)
    
    print("\n" + "=" * 60)
    print("✅ AGENT TEST COMPLETE")
    print("=" * 60)


def test_interactive():
    """
    Interactive test - actually chat with the agent!
    
    Run this to experience the full flow manually.
    """
    print("=" * 60)
    print("🎓 MAHAVIHARA - Interactive Test Mode")
    print("=" * 60)
    print("\nType your answers (A/B/C/D) or chat responses.")
    print("Type 'quit' to exit, 'reset' to start over.\n")
    
    store = RedisStore()
    agent = TutorAgent()
    session_id = "interactive_test"
    
    # Start fresh
    store.delete_session(session_id)
    
    # Start session
    result = agent.start_session(session_id)
    
    print("🤖 Agent:")
    for msg in result['messages']:
        print(f"   {msg['content']}\n")
    
    while True:
        user_input = input("👤 You: ").strip()
        
        if user_input.lower() == 'quit':
            print("\nGoodbye! 👋")
            break
        
        if user_input.lower() == 'reset':
            store.delete_session(session_id)
            result = agent.start_session(session_id)
            print("\n🔄 Session reset!\n")
            print("🤖 Agent:")
            for msg in result['messages']:
                print(f"   {msg['content']}\n")
            continue
        
        if not user_input:
            continue
        
        # Process message
        result = agent.process_message(session_id, user_input)
        
        print("\n🤖 Agent:")
        for msg in result['messages']:
            print(f"   {msg['content']}\n")
        
        # Show mastery after each interaction
        mastery = result['mastery']
        print("   📊 Mastery:", end=" ")
        for c, s in mastery.items():
            emoji = "🟢" if s >= 0.6 else "🔴" if s < 0.4 else "🟡"
            print(f"{emoji}{c[:3]}:{s:.0%}", end=" ")
        print("\n")
        
        # Check if complete
        if result['phase'] == 'complete':
            print("🎉 Session Complete! Type 'reset' to try again or 'quit' to exit.")
    
    # Cleanup
    store.delete_session(session_id)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        test_interactive()
    else:
        test_agent_flow()
        print("\n💡 Tip: Run 'python tests/test_agent.py --interactive' to chat with the agent!")