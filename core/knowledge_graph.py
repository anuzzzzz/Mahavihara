"""
Knowledge Graph - Manages concept dependency DAG.

Features:
    - Hierarchical concept structure (topic → subtopic → micro-concept)
    - Prerequisite relationships as directed edges
    - Root cause tracing for learning gaps
    - Mastery-based visualization
"""

import json
import networkx as nx
from pathlib import Path
from typing import List, Dict, Optional, Set


class KnowledgeGraph:
    """
    Directed Acyclic Graph of concepts with prerequisites.

    Structure:
        Topic (e.g., "Linear Algebra")
        └── Subtopic (e.g., "Vectors")
            └── Micro-concept (e.g., "Vector Magnitude")
    """

    def __init__(self, data_dir: str = "data/concepts"):
        """Load all concept files and build the graph."""
        self.data_dir = Path(data_dir)
        self.graph = nx.DiGraph()
        self.concepts: Dict[str, dict] = {}
        self.topics: Dict[str, List[str]] = {}  # topic_id -> [concept_ids]

        self._load_all_concepts()

    def _load_all_concepts(self):
        """Load concept data from all JSON files in data directory."""
        # Try new structure first
        if self.data_dir.exists():
            for topic_dir in self.data_dir.iterdir():
                if topic_dir.is_dir():
                    self._load_topic(topic_dir)

        # Fallback to old single-file structure
        old_file = Path("data/linear_algebra.json")
        if old_file.exists() and not self.concepts:
            self._load_legacy_file(old_file)

    def _load_topic(self, topic_dir: Path):
        """Load all concepts from a topic directory."""
        topic_id = topic_dir.name
        self.topics[topic_id] = []

        for concept_file in topic_dir.glob("*.json"):
            with open(concept_file, 'r') as f:
                data = json.load(f)

            if "concepts" in data:
                # File contains multiple concepts
                for concept in data["concepts"]:
                    self._add_concept(concept, topic_id)
            else:
                # Single concept file
                self._add_concept(data, topic_id)

    def _load_legacy_file(self, file_path: Path):
        """Load from old single-file format for backwards compatibility."""
        with open(file_path, 'r') as f:
            data = json.load(f)

        topic_id = data.get("chapter", "default").lower().replace(" ", "_")
        self.topics[topic_id] = []

        for concept in data.get("concepts", []):
            self._add_concept(concept, topic_id)

    def _add_concept(self, concept: dict, topic_id: str):
        """Add a concept to the graph."""
        cid = concept["id"]
        self.concepts[cid] = concept
        self.graph.add_node(cid, topic=topic_id)
        self.topics[topic_id].append(cid)

        # Add prerequisite edges
        for prereq in concept.get("prerequisites", []):
            self.graph.add_edge(prereq, cid)

    # ==================== Query Methods ====================

    def get_concept(self, concept_id: str) -> Optional[dict]:
        """Get full concept data by ID."""
        return self.concepts.get(concept_id)

    def get_all_concepts(self) -> List[str]:
        """Get all concept IDs in topological order."""
        return list(nx.topological_sort(self.graph))

    def get_prerequisites(self, concept_id: str) -> List[str]:
        """Get immediate prerequisites (one level up)."""
        return list(self.graph.predecessors(concept_id))

    def get_all_prerequisites(self, concept_id: str) -> Set[str]:
        """Get ALL prerequisites recursively."""
        return nx.ancestors(self.graph, concept_id)

    def get_dependents(self, concept_id: str) -> List[str]:
        """Get concepts that depend on this one (one level down)."""
        return list(self.graph.successors(concept_id))

    def get_all_dependents(self, concept_id: str) -> Set[str]:
        """Get ALL dependents recursively."""
        return nx.descendants(self.graph, concept_id)

    # ==================== Root Cause Analysis ====================

    def trace_root_cause(self, failed_concept: str, mastery: Dict[str, float],
                         threshold: float = 0.6) -> str:
        """
        Find the root cause of failure by tracing back through prerequisites.

        Returns the EARLIEST weak concept in the prerequisite chain.
        """
        ancestors = self.get_all_prerequisites(failed_concept)

        if not ancestors:
            return failed_concept

        # Get topological order (prerequisites first)
        topo_order = list(nx.topological_sort(self.graph))
        ancestors_sorted = [c for c in topo_order if c in ancestors]

        # Find first weak ancestor
        for concept_id in ancestors_sorted:
            if mastery.get(concept_id, 0.5) < threshold:
                return concept_id

        return failed_concept

    def get_learning_path(self, target_concept: str, mastery: Dict[str, float],
                          threshold: float = 0.6) -> List[str]:
        """
        Get ordered list of concepts to learn before reaching target.

        Only includes concepts with mastery below threshold.
        """
        all_prereqs = self.get_all_prerequisites(target_concept)
        all_prereqs.add(target_concept)

        # Filter to weak concepts
        weak = [c for c in all_prereqs if mastery.get(c, 0.5) < threshold]

        # Sort topologically
        topo_order = list(nx.topological_sort(self.graph))
        return [c for c in topo_order if c in weak]

    # ==================== Questions ====================

    def get_questions(self, concept_id: str, difficulty: Optional[int] = None) -> List[dict]:
        """Get questions for a concept, optionally filtered by difficulty."""
        concept = self.get_concept(concept_id)
        if not concept:
            return []

        questions = concept.get("questions", [])

        if difficulty is not None:
            return [q for q in questions if q.get("difficulty") == difficulty]

        return questions

    def get_unseen_questions(self, concept_id: str, asked_ids: List[str],
                             difficulty: Optional[int] = None) -> List[dict]:
        """Get questions that haven't been asked yet."""
        all_questions = self.get_questions(concept_id, difficulty)
        return [q for q in all_questions if q["id"] not in asked_ids]

    # ==================== Visualization ====================

    def get_graph_visualization(self, mastery: Dict[str, float]) -> dict:
        """Generate nodes and edges for frontend visualization."""
        nodes = []
        edges = []

        for concept_id, concept in self.concepts.items():
            score = mastery.get(concept_id, 0.5)

            if score < 0.4:
                color = "#ff6b6b"  # Red - weak
                status = "failed"
            elif score < 0.6:
                color = "#feca57"  # Yellow - learning
                status = "neutral"
            else:
                color = "#5cd85c"  # Green - mastered
                status = "mastered"

            nodes.append({
                "id": concept_id,
                "label": concept.get("name", concept_id),
                "color": color,
                "status": status,
                "score": score
            })

        for source, target in self.graph.edges():
            edges.append({
                "source": source,
                "target": target
            })

        return {"nodes": nodes, "edges": edges}

    # ==================== Statistics ====================

    def get_stats(self) -> dict:
        """Get graph statistics."""
        return {
            "total_concepts": len(self.concepts),
            "total_edges": self.graph.number_of_edges(),
            "topics": list(self.topics.keys()),
            "concepts_per_topic": {t: len(c) for t, c in self.topics.items()},
            "max_depth": nx.dag_longest_path_length(self.graph) if self.concepts else 0
        }
