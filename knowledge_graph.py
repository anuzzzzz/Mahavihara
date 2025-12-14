"""
Knowledge Graph - Manages the concept dependency graph and questions.

Uses networkx for graph operations:
- DAG traversal
- Prerequisite finding
- Root cause tracing
"""

import json
import random
import networkx as nx
from typing import List, Dict, Optional


class KnowledgeGraph:
    def __init__(self, data_path: str = "data/linear_algebra.json"):
        """Load JSON and build the graph."""
        with open(data_path, 'r') as f:
            self.data = json.load(f)
        
        # DiGraph = Directed Graph (arrows have direction)
        self.graph = nx.DiGraph()
        
        # Dictionary for quick lookup: concept_id -> full concept data
        self.concepts = {}
        
        self._build_graph()

    def _build_graph(self):
        """Create nodes and edges from concept data."""
        for concept in self.data["concepts"]:
            cid = concept["id"]
            self.concepts[cid] = concept
            self.graph.add_node(cid)
            
            # Add edges FROM prerequisites TO this concept
            for prereq in concept["prerequisites"]:
                self.graph.add_edge(prereq, cid)

    def get_concept(self, concept_id: str) -> Optional[Dict]:
        """
        Get full concept data by ID.
        
        Returns:
            Full concept dict with name, questions, lesson, etc.
            None if concept doesn't exist.
        """
        return self.concepts.get(concept_id, None)

    def get_prerequisites(self, concept_id: str) -> List[str]:
        """
        Get IMMEDIATE prerequisites only (one level up).
        
        Uses networkx predecessors() - returns nodes that have 
        edges pointing TO this node.
        """
        return list(self.graph.predecessors(concept_id))

    def get_all_ancestors(self, concept_id: str) -> List[str]:
        """
        Get ALL prerequisites recursively (entire chain up to root).
        
        Uses networkx ancestors() - finds all nodes that can 
        reach this node by following edges.
        """
        return list(nx.ancestors(self.graph, concept_id))

    def trace_root_cause(self, failed_concept: str, mastery: Dict[str, float]) -> str:
        """
        THE KEY ALGORITHM: Find the root cause of failure.
        
        When a student fails a concept, trace back through prerequisites
        to find the EARLIEST weak concept (lowest in the dependency chain).
        
        Args:
            failed_concept: The concept the student just failed
            mastery: Dict of concept_id -> mastery score (0.0 to 1.0)
            
        Returns:
            concept_id of the root cause (earliest weak prerequisite)
        """
        ancestors = self.get_all_ancestors(failed_concept)
        
        if not ancestors:
            return failed_concept
        
        # Topological sort: orders nodes so prerequisites come BEFORE dependents
        topo_order = list(nx.topological_sort(self.graph))
        
        # Filter to only ancestors, maintaining topological order
        ancestors_sorted = [c for c in topo_order if c in ancestors]
        
        # Find the FIRST (earliest) ancestor with weak mastery
        MASTERY_THRESHOLD = 0.6
        
        for concept_id in ancestors_sorted:
            if mastery.get(concept_id, 0.5) < MASTERY_THRESHOLD:
                return concept_id
        
        # If all ancestors are strong, the problem is the concept itself
        return failed_concept

    def get_questions(self, concept_id: str, difficulty: Optional[int] = None) -> List[Dict]:
        """
        Get questions for a concept, optionally filtered by difficulty.
        
        Args:
            concept_id: e.g., "derivatives"
            difficulty: 1 (easy), 2 (medium), 3 (hard), or None for all
            
        Returns:
            List of question dicts
        """
        concept = self.get_concept(concept_id)
        
        if not concept:
            return []
        
        questions = concept.get("questions", [])
        
        if difficulty is None:
            return questions
        
        return [q for q in questions if q["difficulty"] == difficulty]

    def get_unseen_questions(self, concept_id: str, asked_ids: List[str], difficulty: Optional[int] = None) -> List[Dict]:
        """
        Get questions that haven't been asked yet.
        
        Args:
            concept_id: The concept to get questions for
            asked_ids: List of question IDs already asked
            difficulty: Optional difficulty filter
            
        Returns:
            List of unseen questions
        """
        all_questions = self.get_questions(concept_id, difficulty)
        return [q for q in all_questions if q["id"] not in asked_ids]

    def get_random_unseen_question(self, concept_id: str, asked_ids: List[str], preferred_difficulty: int = 2) -> Optional[Dict]:
        """
        Get a random unseen question, with fallback logic.
        
        Priority:
        1. Unseen questions at preferred difficulty
        2. Unseen questions at any difficulty
        3. Any question (if all seen - rare)
        
        Args:
            concept_id: The concept to get questions for
            asked_ids: List of question IDs already asked
            preferred_difficulty: Preferred difficulty level
            
        Returns:
            A question dict, or None if no questions exist
        """
        # Try preferred difficulty first
        questions = self.get_unseen_questions(concept_id, asked_ids, preferred_difficulty)
        
        # Fallback to any unseen question
        if not questions:
            questions = self.get_unseen_questions(concept_id, asked_ids)
        
        # Fallback to any question (all seen)
        if not questions:
            questions = self.get_questions(concept_id)
        
        if questions:
            return random.choice(questions)
        
        return None

    def get_diagnostic_set(self) -> List[Dict]:
        """
        Get one MEDIUM difficulty question from each concept for initial diagnosis.
        
        Returns:
            List of 5 questions (one per concept) with concept_id attached
        """
        diagnostic_questions = []
        
        for concept_id, concept in self.concepts.items():
            medium_questions = self.get_questions(concept_id, difficulty=2)
            
            if medium_questions:
                question = medium_questions[0].copy()
                question["concept_id"] = concept_id
                diagnostic_questions.append(question)
        
        return diagnostic_questions

    def get_graph_visualization(self, mastery: Dict[str, float]) -> Dict:
        """
        Generate nodes and edges for visualization.
        
        Colors nodes based on mastery level:
        - RED (#ff6b6b): mastery < 0.4 (weak)
        - YELLOW (#feca57): 0.4 <= mastery < 0.7 (learning)
        - GREEN (#5cd85c): mastery >= 0.7 (strong)
        """
        nodes = []
        edges = []
        
        for concept_id, concept in self.concepts.items():
            score = mastery.get(concept_id, 0.5)
            
            if score < 0.4:
                color = "#ff6b6b"  # Red
            elif score < 0.7:
                color = "#feca57"  # Yellow
            else:
                color = "#5cd85c"  # Green
            
            nodes.append({
                "id": concept_id,
                "label": concept["name"],
                "color": color,
                "size": 30,
            })
        
        for source, target in self.graph.edges():
            edges.append({
                "source": source,
                "target": target,
            })
        
        return {"nodes": nodes, "edges": edges}

    def get_concept_order(self) -> List[str]:
        """Get concepts in topological order (prerequisites first)."""
        return list(nx.topological_sort(self.graph))