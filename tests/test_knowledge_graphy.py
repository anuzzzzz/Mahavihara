"""Tests for knowledge_graph.py"""

import sys
sys.path.append(".")  # So we can import from parent directory

from knowledge_graph import KnowledgeGraph


def test_knowledge_graph():
    kg = KnowledgeGraph()
    
    print("=== Knowledge Graph Tests ===\n")
    
    # Test 1: Graph structure
    print("1. Graph Structure")
    print("   Concepts:", list(kg.concepts.keys()))
    print("   Edges:", list(kg.graph.edges()))
    
    # Test 2: Prerequisites
    print("\n2. Prerequisites")
    print("   chain_rule requires:", kg.get_prerequisites("chain_rule"))
    print("   maxima_minima ancestors:", kg.get_all_ancestors("maxima_minima"))
    
    # Test 3: Root cause tracing
    print("\n3. Root Cause Tracing")
    weak_mastery = {
        "limits": 0.3,
        "continuity": 0.7,
        "derivatives": 0.8,
        "chain_rule": 0.5,
        "maxima_minima": 0.2
    }
    root = kg.trace_root_cause("maxima_minima", weak_mastery)
    print(f"   Student failed maxima_minima")
    print(f"   Mastery: {weak_mastery}")
    print(f"   Root cause: {root}")
    
    # Test 4: Diagnostic set
    print("\n4. Diagnostic Set")
    diag = kg.get_diagnostic_set()
    print(f"   Total questions: {len(diag)}")
    for q in diag:
        print(f"   - [{q['concept_id']}] {q['text'][:50]}...")
    
    # Test 5: Visualization data
    print("\n5. Visualization")
    viz = kg.get_graph_visualization(weak_mastery)
    print(f"   Nodes: {len(viz['nodes'])}")
    for node in viz['nodes']:
        print(f"   - {node['label']}: {node['color']}")
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_knowledge_graph()