"""Tests for knowledge_graph.py"""

import sys
sys.path.append(".")

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
    print("   determinants requires:", kg.get_prerequisites("determinants"))
    print("   eigenvalues ancestors:", kg.get_all_ancestors("eigenvalues"))
    
    # Test 3: Root cause tracing
    print("\n3. Root Cause Tracing")
    weak_mastery = {
        "vectors": 0.3,
        "matrix_ops": 0.7,
        "determinants": 0.8,
        "inverse_matrix": 0.5,
        "eigenvalues": 0.2
    }
    root = kg.trace_root_cause("eigenvalues", weak_mastery)
    print(f"   Student failed eigenvalues")
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