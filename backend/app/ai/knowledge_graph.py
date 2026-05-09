import numpy as np
import networkx as nx
from typing import List, Dict, Optional

SAMPLE_KNOWLEDGE_GRAPH = {
    "mathematics": [
        {"id":"math_arithmetic","name":"Arithmetic","difficulty":1,"minutes":20,"prereqs":[]},
        {"id":"math_fractions","name":"Fractions & Decimals","difficulty":2,"minutes":30,"prereqs":["math_arithmetic"]},
        {"id":"math_algebra_basics","name":"Algebra Basics","difficulty":2,"minutes":40,"prereqs":["math_arithmetic","math_fractions"]},
        {"id":"math_linear_equations","name":"Linear Equations","difficulty":3,"minutes":45,"prereqs":["math_algebra_basics"]},
        {"id":"math_quadratic","name":"Quadratic Equations","difficulty":3,"minutes":50,"prereqs":["math_linear_equations"]},
        {"id":"math_functions","name":"Functions & Graphs","difficulty":3,"minutes":45,"prereqs":["math_linear_equations"]},
        {"id":"math_trigonometry","name":"Trigonometry","difficulty":4,"minutes":60,"prereqs":["math_functions","math_quadratic"]},
        {"id":"math_calculus_limits","name":"Limits & Continuity","difficulty":4,"minutes":55,"prereqs":["math_functions"]},
        {"id":"math_derivatives","name":"Derivatives","difficulty":5,"minutes":60,"prereqs":["math_calculus_limits"]},
        {"id":"math_integrals","name":"Integrals","difficulty":5,"minutes":70,"prereqs":["math_derivatives"]},
        {"id":"math_statistics","name":"Statistics & Probability","difficulty":3,"minutes":50,"prereqs":["math_algebra_basics"]},
        {"id":"math_linear_algebra","name":"Linear Algebra","difficulty":5,"minutes":80,"prereqs":["math_functions","math_statistics"]},
    ],
    "computer_science": [
        {"id":"cs_intro","name":"Intro to Programming","difficulty":1,"minutes":30,"prereqs":[]},
        {"id":"cs_variables","name":"Variables & Data Types","difficulty":1,"minutes":25,"prereqs":["cs_intro"]},
        {"id":"cs_control_flow","name":"Control Flow","difficulty":2,"minutes":35,"prereqs":["cs_variables"]},
        {"id":"cs_functions","name":"Functions","difficulty":2,"minutes":40,"prereqs":["cs_control_flow"]},
        {"id":"cs_arrays","name":"Arrays & Lists","difficulty":2,"minutes":35,"prereqs":["cs_variables","cs_control_flow"]},
        {"id":"cs_oop","name":"Object-Oriented Programming","difficulty":3,"minutes":60,"prereqs":["cs_functions","cs_arrays"]},
        {"id":"cs_data_structures","name":"Data Structures","difficulty":4,"minutes":70,"prereqs":["cs_oop","cs_arrays"]},
        {"id":"cs_algorithms","name":"Algorithms & Complexity","difficulty":4,"minutes":80,"prereqs":["cs_data_structures","math_statistics"]},
        {"id":"cs_recursion","name":"Recursion","difficulty":3,"minutes":45,"prereqs":["cs_functions"]},
        {"id":"cs_sorting","name":"Sorting Algorithms","difficulty":3,"minutes":50,"prereqs":["cs_recursion","cs_arrays"]},
        {"id":"cs_databases","name":"Databases & SQL","difficulty":3,"minutes":55,"prereqs":["cs_oop"]},
        {"id":"cs_ml_basics","name":"Machine Learning Basics","difficulty":5,"minutes":90,"prereqs":["cs_algorithms","math_statistics","math_linear_algebra"]},
    ],
    "physics": [
        {"id":"phys_kinematics","name":"Kinematics","difficulty":2,"minutes":45,"prereqs":["math_algebra_basics"]},
        {"id":"phys_dynamics","name":"Newton Laws","difficulty":3,"minutes":50,"prereqs":["phys_kinematics"]},
        {"id":"phys_energy","name":"Work Energy Power","difficulty":3,"minutes":45,"prereqs":["phys_dynamics"]},
        {"id":"phys_waves","name":"Waves & Oscillations","difficulty":3,"minutes":50,"prereqs":["phys_dynamics","math_trigonometry"]},
        {"id":"phys_electricity","name":"Electricity & Magnetism","difficulty":4,"minutes":70,"prereqs":["phys_energy","math_derivatives"]},
        {"id":"phys_quantum","name":"Quantum Mechanics","difficulty":5,"minutes":90,"prereqs":["phys_waves","phys_electricity","math_integrals"]},
    ],
}

class KnowledgeGraphEngine:
    def __init__(self):
        self.nx_graph = self._build()

    def _build(self):
        G = nx.DiGraph()
        for subject, topics in SAMPLE_KNOWLEDGE_GRAPH.items():
            for t in topics:
                G.add_node(t["id"], name=t["name"], subject=subject, difficulty=t["difficulty"], minutes=t["minutes"])
                for p in t["prereqs"]:
                    G.add_edge(p, t["id"], type="prerequisite")
        return G

    async def seed_neo4j(self, session):
        for subject, topics in SAMPLE_KNOWLEDGE_GRAPH.items():
            for t in topics:
                await session.run("MERGE (n:Topic {id:$id}) SET n.name=$name,n.subject=$subject,n.difficulty=$diff,n.estimated_minutes=$mins",
                    id=t["id"],name=t["name"],subject=subject,diff=t["difficulty"],mins=t["minutes"])
            for t in topics:
                for p in t["prereqs"]:
                    await session.run("MATCH (a:Topic{id:$a}),(b:Topic{id:$b}) MERGE (a)-[:PREREQUISITE]->(b)",a=p,b=t["id"])

    def get_prerequisites(self, topic_id, depth=3):
        if topic_id not in self.nx_graph: return []
        prereqs=set(); queue=[topic_id]; visited=set()
        for _ in range(depth):
            nxt=[]
            for n in queue:
                if n in visited: continue
                visited.add(n)
                preds=list(self.nx_graph.predecessors(n)); prereqs.update(preds); nxt.extend(preds)
            queue=nxt
        return list(prereqs-{topic_id})

    def get_next_recommended_topics(self, mastery_scores, n=5, threshold=0.7):
        recs=[]
        for tid in self.nx_graph.nodes():
            if mastery_scores.get(tid,0.0)>=threshold: continue
            prereqs=list(self.nx_graph.predecessors(tid))
            if all(mastery_scores.get(p,0.0)>=threshold for p in prereqs):
                nd=self.nx_graph.nodes[tid]
                recs.append({"topic_id":tid,"name":nd.get("name",tid),"subject":nd.get("subject",""),
                    "difficulty":nd.get("difficulty",3),"estimated_minutes":nd.get("minutes",30),
                    "current_mastery":mastery_scores.get(tid,0.0),"prereqs_met":True})
        recs.sort(key=lambda x:(x["difficulty"],-(1-x["current_mastery"])))
        return recs[:n]

    def compute_topic_importance(self):
        return nx.betweenness_centrality(self.nx_graph, normalized=True)

    def get_knowledge_gap_subgraph(self, mastery_scores, threshold=0.6):
        gap=[t for t,m in mastery_scores.items() if m<threshold and t in self.nx_graph]
        sub=self.nx_graph.subgraph(gap)
        return {"nodes":[{"id":n,"name":self.nx_graph.nodes[n].get("name",n),"mastery":mastery_scores.get(n,0.0),"difficulty":self.nx_graph.nodes[n].get("difficulty",3)} for n in sub.nodes()],
                "edges":[{"from":u,"to":v} for u,v in sub.edges()]}

    def get_all_topics(self):
        return [{"id":n,**{k:v for k,v in self.nx_graph.nodes[n].items()},"prerequisite_count":len(list(self.nx_graph.predecessors(n))),"dependent_count":len(list(self.nx_graph.successors(n)))} for n in self.nx_graph.nodes()]

knowledge_graph = KnowledgeGraphEngine()
