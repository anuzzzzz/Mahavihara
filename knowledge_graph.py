import json
import networkx as nx
from typing import List, Dict, Optional


class KnowledgeGraph:
    def __init__(self, data_path: str = "data/linear_algebra.json"):
        """Load JSON and build the graph."""
        with open(data_path, 'r') as f:
            self.data = json.load(f)
        
        self.graph = nx.DiGraph()
        self.concepts = {}  # id -> concept data
        
        # Build the graph
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
        
        Args:
            concept_id: e.g., "derivatives"
            
        Returns:
            Full concept dict with name, questions, etc.
            None if concept doesn't exist.
            
        Example:
            >>> kg.get_concept("limits")
            {"id": "limits", "name": "Limits", "prerequisites": [], ...}
        """
        return self.concepts.get(concept_id, None)

    def get_prerequisites(self, concept_id: str) -> List[str]:
        """
        Get IMMEDIATE prerequisites only (one level up).
        
        Uses networkx predecessors() - returns nodes that have 
        edges pointing TO this node.
        
        Args:
            concept_id: e.g., "chain_rule"
            
        Returns:
            List of immediate prerequisite IDs
            
        Example:
            >>> kg.get_prerequisites("chain_rule")
            ["derivatives"]  # Just the direct parent
        """
        return list(self.graph.predecessors(concept_id))

    def get_all_ancestors(self, concept_id: str) -> List[str]:
        """
        Get ALL prerequisites recursively (entire chain up to root).
        
        Uses networkx ancestors() - finds all nodes that can 
        reach this node by following edges.
        
        Args:
            concept_id: e.g., "maxima_minima"
            
        Returns:
            List of ALL ancestor concept IDs
            
        Example:
            >>> kg.get_all_ancestors("maxima_minima")
            ["chain_rule", "derivatives", "continuity", "limits"]
        """
        return list(nx.ancestors(self.graph, concept_id))
    
    def trace_root_cause(self, failed_concept: str, mastery: Dict[str, float]) -> str:
        """
        THE KEY ALGORITHM: Find the root cause of failure.
        
        When a student fails a concept, trace back through prerequisites
        to find the EARLIEST weak concept (lowest in the dependency chain).
        
        Logic:
        1. Get all ancestors of the failed concept
        2. Sort them in topological order (roots first)
        3. Find the first one with low mastery (< 0.6)
        4. That's the root cause!
        
        Args:
            failed_concept: The concept the student just failed
            mastery: Dict of concept_id -> mastery score (0.0 to 1.0)
            
        Returns:
            concept_id of the root cause (earliest weak prerequisite)
            
        Example:
            Student fails "maxima_minima" with mastery:
            {"limits": 0.3, "continuity": 0.5, "derivatives": 0.4, ...}
            
            Returns: "limits" (the earliest weak concept)
        """
        # Get all ancestors (prerequisites) of the failed concept
        ancestors = self.get_all_ancestors(failed_concept)
        
        # If no ancestors, the failed concept itself is the root cause
        if not ancestors:
            return failed_concept
        
        # Topological sort: orders nodes so prerequisites come BEFORE dependents
        # Example: [limits, continuity, derivatives, chain_rule, maxima_minima]
        topo_order = list(nx.topological_sort(self.graph))
        
        # Filter to only ancestors, maintaining topological order
        # This gives us ancestors from root → failed concept
        ancestors_sorted = [c for c in topo_order if c in ancestors]
        
        # Find the FIRST (earliest) ancestor with weak mastery
        MASTERY_THRESHOLD = 0.6  # Below this = weak understanding
        
        for concept_id in ancestors_sorted:
            if mastery.get(concept_id, 0.5) < MASTERY_THRESHOLD:
                # Found it! This is the root cause
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
            
        Example:
            >>> kg.get_questions("limits", difficulty=1)
            [{"id": "lim_e1", "text": "...", ...}, {"id": "lim_e2", ...}]
        """
        concept = self.get_concept(concept_id)
        
        if not concept:
            return []
        
        questions = concept.get("questions", [])
        
        # If no difficulty filter, return all questions
        if difficulty is None:
            return questions
        
        # Filter by difficulty level
        return [q for q in questions if q["difficulty"] == difficulty]

    def get_diagnostic_set(self) -> List[Dict]:
        """
        Get one MEDIUM difficulty question from each concept for initial diagnosis.
        
        This creates a balanced 5-question diagnostic test that covers
        all concepts without being too easy or too hard.
        
        Returns:
            List of 5 questions (one per concept) with concept_id attached
            
        Example:
            >>> kg.get_diagnostic_set()
            [
                {"concept_id": "limits", "id": "lim_m1", "text": "...", ...},
                {"concept_id": "continuity", "id": "cont_m1", ...},
                ...
            ]
        """
        diagnostic_questions = []
        
        # Get one medium question from each concept
        for concept_id, concept in self.concepts.items():
            # Get medium difficulty questions (difficulty = 2)
            medium_questions = self.get_questions(concept_id, difficulty=2)
            
            if medium_questions:
                # Take the first medium question
                question = medium_questions[0].copy()  # Copy to avoid mutating original
                
                # Attach concept_id so we know which concept this tests
                question["concept_id"] = concept_id
                
                diagnostic_questions.append(question)
        
        return diagnostic_questions

    def get_graph_visualization(self, mastery: Dict[str, float]) -> Dict:
        """
        Generate nodes and edges for streamlit-agraph visualization.
        
        Colors nodes based on mastery level:
        - RED (#ff6b6b): mastery < 0.4 (weak)
        - YELLOW (#feca57): 0.4 <= mastery < 0.7 (learning)
        - GREEN (#5cd85c): mastery >= 0.7 (strong)
        
        Args:
            mastery: Dict of concept_id -> mastery score (0.0 to 1.0)
            
        Returns:
            Dict with "nodes" and "edges" lists for streamlit-agraph
            
        Example:
            >>> kg.get_graph_visualization({"limits": 0.8, "continuity": 0.3, ...})
            {
                "nodes": [
                    {"id": "limits", "label": "Limits", "color": "#5cd85c"},
                    {"id": "continuity", "label": "Continuity", "color": "#ff6b6b"},
                    ...
                ],
                "edges": [
                    {"source": "limits", "target": "continuity"},
                    ...
                ]
            }
        """
        nodes = []
        edges = []
        
        # Create nodes with colors based on mastery
        for concept_id, concept in self.concepts.items():
            # Get mastery score, default to 0.5 if not yet assessed
            score = mastery.get(concept_id, 0.5)
            
            # Determine color based on mastery level
            if score < 0.4:
                color = "#ff6b6b"  # Red - weak
            elif score < 0.7:
                color = "#feca57"  # Yellow - learning
            else:
                color = "#5cd85c"  # Green - strong
            
            nodes.append({
                "id": concept_id,
                "label": concept["name"],
                "color": color,
                "size": 30,  # Node size for visibility
            })
        
        # Create edges from the graph
        for source, target in self.graph.edges():
            edges.append({
                "source": source,
                "target": target,
            })
        
        return {"nodes": nodes, "edges": edges}