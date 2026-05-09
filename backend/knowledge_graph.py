"""
Knowledge Graph Engine
======================
Manages the subject knowledge graph in Neo4j.
- Topics as nodes with metadata
- Prerequisite relationships as directed edges
- Graph traversal for learning path generation
- Betweenness centrality for topic importance
- Community detection for topic clustering
"""
from typing import List, Dict, Optional, Tuple
import logging
import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


# ─── Knowledge Graph Schema ───────────────────────────────────────────────────
#
# Node: Topic { id, name, subject, difficulty, estimated_minutes }
# Edge: PREREQUISITE { strength: 0-1, type: "hard|soft" }
# Edge: RELATED_TO   { similarity: 0-1 }
#
# Example queries:
#   MATCH (a:Topic)-[:PREREQUISITE]->(b:Topic) RETURN a,b
#   MATCH path = shortestPath((a:Topic)-[:PREREQUISITE*]->(b:Topic)) RETURN path


SAMPLE_KNOWLEDGE_GRAPH = {
    "mathematics": [
        {"id": "math_arithmetic", "name": "Arithmetic", "difficulty": 1, "minutes": 20, "prereqs": []},
        {"id": "math_fractions", "name": "Fractions & Decimals", "difficulty": 2, "minutes": 30, "prereqs": ["math_arithmetic"]},
        {"id": "math_algebra_basics", "name": "Algebra Basics", "difficulty": 2, "minutes": 40, "prereqs": ["math_arithmetic", "math_fractions"]},
        {"id": "math_linear_equations", "name": "Linear Equations", "difficulty": 3, "minutes": 45, "prereqs": ["math_algebra_basics"]},
        {"id": "math_quadratic", "name": "Quadratic Equations", "difficulty": 3, "minutes": 50, "prereqs": ["math_linear_equations"]},
        {"id": "math_functions", "name": "Functions & Graphs", "difficulty": 3, "minutes": 45, "prereqs": ["math_linear_equations"]},
        {"id": "math_trigonometry", "name": "Trigonometry", "difficulty": 4, "minutes": 60, "prereqs": ["math_functions", "math_quadratic"]},
        {"id": "math_calculus_limits", "name": "Limits & Continuity", "difficulty": 4, "minutes": 55, "prereqs": ["math_functions"]},
        {"id": "math_derivatives", "name": "Derivatives", "difficulty": 5, "minutes": 60, "prereqs": ["math_calculus_limits"]},
        {"id": "math_integrals", "name": "Integrals", "difficulty": 5, "minutes": 70, "prereqs": ["math_derivatives"]},
        {"id": "math_statistics", "name": "Statistics & Probability", "difficulty": 3, "minutes": 50, "prereqs": ["math_algebra_basics"]},
        {"id": "math_linear_algebra", "name": "Linear Algebra", "difficulty": 5, "minutes": 80, "prereqs": ["math_functions", "math_statistics"]},
    ],
    "computer_science": [
        {"id": "cs_intro", "name": "Intro to Programming", "difficulty": 1, "minutes": 30, "prereqs": []},
        {"id": "cs_variables", "name": "Variables & Data Types", "difficulty": 1, "minutes": 25, "prereqs": ["cs_intro"]},
        {"id": "cs_control_flow", "name": "Control Flow", "difficulty": 2, "minutes": 35, "prereqs": ["cs_variables"]},
        {"id": "cs_functions", "name": "Functions", "difficulty": 2, "minutes": 40, "prereqs": ["cs_control_flow"]},
        {"id": "cs_arrays", "name": "Arrays & Lists", "difficulty": 2, "minutes": 35, "prereqs": ["cs_variables", "cs_control_flow"]},
        {"id": "cs_oop", "name": "Object-Oriented Programming", "difficulty": 3, "minutes": 60, "prereqs": ["cs_functions", "cs_arrays"]},
        {"id": "cs_data_structures", "name": "Data Structures", "difficulty": 4, "minutes": 70, "prereqs": ["cs_oop", "cs_arrays"]},
        {"id": "cs_algorithms", "name": "Algorithms & Complexity", "difficulty": 4, "minutes": 80, "prereqs": ["cs_data_structures", "math_statistics"]},
        {"id": "cs_recursion", "name": "Recursion", "difficulty": 3, "minutes": 45, "prereqs": ["cs_functions"]},
        {"id": "cs_sorting", "name": "Sorting Algorithms", "difficulty": 3, "minutes": 50, "prereqs": ["cs_recursion", "cs_arrays"]},
        {"id": "cs_databases", "name": "Databases & SQL", "difficulty": 3, "minutes": 55, "prereqs": ["cs_oop"]},
        {"id": "cs_ml_basics", "name": "Machine Learning Basics", "difficulty": 5, "minutes": 90, "prereqs": ["cs_algorithms", "math_statistics", "math_linear_algebra"]},
    ],
    "physics": [
        {"id": "phys_kinematics", "name": "Kinematics", "difficulty": 2, "minutes": 45, "prereqs": ["math_algebra_basics"]},
        {"id": "phys_dynamics", "name": "Newton's Laws", "difficulty": 3, "minutes": 50, "prereqs": ["phys_kinematics"]},
        {"id": "phys_energy", "name": "Work, Energy & Power", "difficulty": 3, "minutes": 45, "prereqs": ["phys_dynamics"]},
        {"id": "phys_waves", "name": "Waves & Oscillations", "difficulty": 3, "minutes": 50, "prereqs": ["phys_dynamics", "math_trigonometry"]},
        {"id": "phys_electricity", "name": "Electricity & Magnetism", "difficulty": 4, "minutes": 70, "prereqs": ["phys_energy", "math_derivatives"]},
        {"id": "phys_quantum", "name": "Quantum Mechanics", "difficulty": 5, "minutes": 90, "prereqs": ["phys_waves", "phys_electricity", "math_integrals"]},
    ],
}


class KnowledgeGraphEngine:
    """
    Knowledge graph management using Neo4j for storage and NetworkX for algorithms.
    """

    def __init__(self, neo4j_driver=None):
        self.driver = neo4j_driver
        self.nx_graph = self._build_networkx_graph()
        logger.info(f"KnowledgeGraph: {self.nx_graph.number_of_nodes()} nodes, {self.nx_graph.number_of_edges()} edges")

    def _build_networkx_graph(self) -> nx.DiGraph:
        """Build in-memory NetworkX graph for fast algorithms."""
        G = nx.DiGraph()
        for subject, topics in SAMPLE_KNOWLEDGE_GRAPH.items():
            for topic in topics:
                G.add_node(
                    topic["id"],
                    name=topic["name"],
                    subject=subject,
                    difficulty=topic["difficulty"],
                    minutes=topic["minutes"],
                )
                for prereq in topic["prereqs"]:
                    G.add_edge(prereq, topic["id"], type="prerequisite", strength=1.0)
        return G

    async def seed_neo4j(self, session):
        """Seed Neo4j with the knowledge graph data."""
        for subject, topics in SAMPLE_KNOWLEDGE_GRAPH.items():
            for topic in topics:
                await session.run(
                    """
                    MERGE (t:Topic {id: $id})
                    SET t.name = $name,
                        t.subject = $subject,
                        t.difficulty = $difficulty,
                        t.estimated_minutes = $minutes
                    """,
                    id=topic["id"],
                    name=topic["name"],
                    subject=subject,
                    difficulty=topic["difficulty"],
                    minutes=topic["minutes"],
                )
            for topic in topics:
                for prereq_id in topic["prereqs"]:
                    await session.run(
                        """
                        MATCH (a:Topic {id: $from_id}), (b:Topic {id: $to_id})
                        MERGE (a)-[:PREREQUISITE {strength: 1.0, type: 'hard'}]->(b)
                        """,
                        from_id=prereq_id,
                        to_id=topic["id"],
                    )
        logger.info("Neo4j seeded with knowledge graph")

    def get_prerequisites(self, topic_id: str, depth: int = 3) -> List[str]:
        """Get all prerequisites up to given depth using BFS."""
        if topic_id not in self.nx_graph:
            return []
        prereqs = set()
        queue = [topic_id]
        visited = set()
        current_depth = 0
        while queue and current_depth < depth:
            next_queue = []
            for node in queue:
                if node in visited:
                    continue
                visited.add(node)
                preds = list(self.nx_graph.predecessors(node))
                prereqs.update(preds)
                next_queue.extend(preds)
            queue = next_queue
            current_depth += 1
        return list(prereqs - {topic_id})

    def get_learning_path(
        self,
        start_topic: str,
        target_topic: str,
        mastery_scores: Dict[str, float],
        mastery_threshold: float = 0.7,
    ) -> List[str]:
        """
        Find optimal learning path from start to target.
        Skips topics where mastery > threshold.
        Returns ordered list of topics to study.
        """
        if not nx.has_path(self.nx_graph, start_topic, target_topic):
            # Try to find any path via topological ordering
            topo = list(nx.topological_sort(self.nx_graph))
            all_prereqs = self.get_prerequisites(target_topic, depth=10)
            path = [t for t in topo if t in all_prereqs or t == target_topic]
            return path

        try:
            path = nx.shortest_path(self.nx_graph, start_topic, target_topic)
        except nx.NetworkXNoPath:
            return [target_topic]

        # Filter out already-mastered topics
        return [
            t for t in path
            if mastery_scores.get(t, 0.0) < mastery_threshold or t == target_topic
        ]

    def get_next_recommended_topics(
        self,
        mastery_scores: Dict[str, float],
        n: int = 5,
        mastery_threshold: float = 0.7,
    ) -> List[Dict]:
        """
        Recommend next topics based on:
        - Prerequisites all met (mastery > threshold)
        - Not yet mastered
        - Ordered by difficulty (easier first)
        """
        recommendations = []
        for topic_id in self.nx_graph.nodes():
            mastery = mastery_scores.get(topic_id, 0.0)
            if mastery >= mastery_threshold:
                continue  # Already mastered

            prereqs = list(self.nx_graph.predecessors(topic_id))
            prereqs_met = all(mastery_scores.get(p, 0.0) >= mastery_threshold for p in prereqs)

            if prereqs_met:
                node_data = self.nx_graph.nodes[topic_id]
                recommendations.append({
                    "topic_id": topic_id,
                    "name": node_data.get("name", topic_id),
                    "subject": node_data.get("subject", ""),
                    "difficulty": node_data.get("difficulty", 3),
                    "estimated_minutes": node_data.get("minutes", 30),
                    "current_mastery": mastery,
                    "prereqs_met": True,
                })

        # Sort by difficulty, then by mastery gap (biggest gap first)
        recommendations.sort(key=lambda x: (x["difficulty"], -(1 - x["current_mastery"])))
        return recommendations[:n]

    def compute_topic_importance(self) -> Dict[str, float]:
        """Betweenness centrality as topic importance score."""
        centrality = nx.betweenness_centrality(self.nx_graph, normalized=True)
        return dict(sorted(centrality.items(), key=lambda x: x[1], reverse=True))

    def detect_topic_clusters(self) -> Dict[str, int]:
        """Community detection using weakly connected components."""
        undirected = self.nx_graph.to_undirected()
        clusters = {}
        for cluster_id, component in enumerate(nx.connected_components(undirected)):
            for node in component:
                clusters[node] = cluster_id
        return clusters

    def get_knowledge_gap_subgraph(
        self, mastery_scores: Dict[str, float], threshold: float = 0.6
    ) -> Dict:
        """
        Return subgraph of knowledge gaps with dependency context.
        """
        gap_nodes = [t for t, m in mastery_scores.items() if m < threshold and t in self.nx_graph]
        subgraph = self.nx_graph.subgraph(gap_nodes)
        return {
            "nodes": [
                {
                    "id": n,
                    "name": self.nx_graph.nodes[n].get("name", n),
                    "mastery": mastery_scores.get(n, 0.0),
                    "difficulty": self.nx_graph.nodes[n].get("difficulty", 3),
                }
                for n in subgraph.nodes()
            ],
            "edges": [
                {"from": u, "to": v}
                for u, v in subgraph.edges()
            ],
        }

    def get_all_topics(self) -> List[Dict]:
        """Return all topics with metadata."""
        return [
            {
                "id": n,
                **{k: v for k, v in self.nx_graph.nodes[n].items()},
                "prerequisite_count": len(list(self.nx_graph.predecessors(n))),
                "dependent_count": len(list(self.nx_graph.successors(n))),
            }
            for n in self.nx_graph.nodes()
        ]


# Singleton
knowledge_graph = KnowledgeGraphEngine()
