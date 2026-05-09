"""
AI Tutor — RAG-Powered Gemini Tutor
==================================
Uses Google Gemini 1.5 Flash as the base LLM with:
- Retrieval Augmented Generation (RAG) from educational content DB
- Student profile-aware system prompts
- Multi-turn tutoring conversation management
- Step-by-step problem solving mode
- Concept explanation and example generation
- Answer evaluation using semantic similarity
"""
import google.generativeai as genai
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional, AsyncGenerator
import numpy as np
import logging
import json

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Content Database (seeded into Qdrant) ────────────────────────────────────

EDUCATIONAL_CONTENT = [
    {
        "id": "content_001",
        "topic_id": "math_derivatives",
        "content": """
        The derivative measures the rate of change of a function.
        For f(x) = x², the derivative f'(x) = 2x, meaning the slope at x=3 is 6.

        Key rules:
        - Power rule: d/dx[xⁿ] = n·xⁿ⁻¹
        - Sum rule: d/dx[f+g] = f' + g'
        - Product rule: d/dx[f·g] = f'g + fg'
        - Chain rule: d/dx[f(g(x))] = f'(g(x))·g'(x)

        Applications: Finding maxima/minima, velocity from position, optimization problems.
        """,
        "difficulty": 4,
    },
    {
        "id": "content_002",
        "topic_id": "cs_oop",
        "content": """
        Object-Oriented Programming (OOP) organizes code around objects that combine data and behavior.

        Four pillars:
        1. Encapsulation: Bundle data + methods; hide internal state
        2. Inheritance: Child classes inherit parent class properties
        3. Polymorphism: Same interface, different implementations
        4. Abstraction: Expose essential features, hide complexity

        Example in Python:
        class Animal:
            def speak(self): pass
        class Dog(Animal):
            def speak(self): return "Woof!"
        """,
        "difficulty": 3,
    },
    {
        "id": "content_003",
        "topic_id": "phys_kinematics",
        "content": """
        Kinematics describes motion without considering forces.

        Key equations (constant acceleration):
        - v = u + at              (velocity-time)
        - s = ut + ½at²           (displacement-time)
        - v² = u² + 2as           (velocity-displacement)
        - s = (u+v)t/2            (average velocity)

        Where: u=initial velocity, v=final velocity, a=acceleration, t=time, s=displacement.

        Projectile motion: horizontal (constant velocity) + vertical (gravity = -9.8 m/s²)
        """,
        "difficulty": 2,
    },
    {
        "id": "content_004",
        "topic_id": "math_statistics",
        "content": """
        Statistics helps us understand data patterns and make inferences.

        Descriptive statistics:
        - Mean: average value
        - Median: middle value
        - Mode: most frequent value
        - Standard deviation: spread around mean

        Probability basics:
        - P(A) = favorable outcomes / total outcomes
        - P(A∪B) = P(A) + P(B) - P(A∩B)
        - Conditional probability: P(A|B) = P(A∩B)/P(B)
        - Bayes theorem: P(A|B) = P(B|A)·P(A)/P(B)

        Normal distribution: 68-95-99.7 rule (1σ, 2σ, 3σ from mean)
        """,
        "difficulty": 3,
    },
    {
        "id": "content_005",
        "topic_id": "cs_algorithms",
        "content": """
        Algorithm complexity analysis using Big-O notation.

        Common complexities (best to worst):
        O(1) < O(log n) < O(n) < O(n log n) < O(n²) < O(2ⁿ) < O(n!)

        Sorting algorithms:
        - Bubble Sort: O(n²) — simple but slow
        - Merge Sort: O(n log n) — divide and conquer, stable
        - Quick Sort: O(n log n) average, O(n²) worst — in-place
        - Heap Sort: O(n log n) — uses heap data structure

        Graph algorithms:
        - BFS: O(V+E), shortest path in unweighted graphs
        - DFS: O(V+E), topological sort, cycle detection
        - Dijkstra: O((V+E)log V), shortest path weighted graphs
        """,
        "difficulty": 4,
    },
]


# ─── RAG Retriever ────────────────────────────────────────────────────────────

class RAGRetriever:
    """Retrieves relevant educational content using semantic search."""

    def __init__(self):
        self.encoder = None  # Lazy load to speed up startup
        self.qdrant = QdrantClient(url=settings.QDRANT_URL)
        self.collection = "content_embeddings"

    def _get_encoder(self):
        if self.encoder is None:
            self.encoder = SentenceTransformer("all-mpnet-base-v2")
        return self.encoder

    def encode_content(self, text: str) -> List[float]:
        encoder = self._get_encoder()
        return encoder.encode(text, normalize_embeddings=True).tolist()

    def retrieve(
        self,
        query: str,
        topic_id: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict]:
        """Retrieve top-k relevant content chunks."""
        query_embedding = self.encode_content(query)

        search_filter = None
        if topic_id:
            search_filter = Filter(
                must=[FieldCondition(key="topic_id", match=MatchValue(value=topic_id))]
            )

        try:
            results = self.qdrant.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k,
                with_payload=True,
            )
            return [
                {
                    "content": r.payload.get("content", ""),
                    "topic_id": r.payload.get("topic_id", ""),
                    "score": r.score,
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}, using fallback")
            # Fallback: return relevant content from in-memory store
            if topic_id:
                return [
                    {"content": c["content"], "topic_id": c["topic_id"], "score": 1.0}
                    for c in EDUCATIONAL_CONTENT
                    if c["topic_id"] == topic_id
                ][:top_k]
            return [
                {"content": c["content"], "topic_id": c["topic_id"], "score": 0.5}
                for c in EDUCATIONAL_CONTENT[:top_k]
            ]

    def seed_content(self):
        """Index all educational content into Qdrant."""
        from qdrant_client.models import PointStruct
        points = []
        for i, item in enumerate(EDUCATIONAL_CONTENT):
            embedding = self.encode_content(item["content"])
            points.append(PointStruct(
                id=i,
                vector=embedding,
                payload={
                    "content_id": item["id"],
                    "topic_id": item["topic_id"],
                    "content": item["content"],
                    "difficulty": item["difficulty"],
                },
            ))
        self.qdrant.upsert(collection_name=self.collection, points=points)
        logger.info(f"Seeded {len(points)} content items into Qdrant")


# ─── AI Tutor ─────────────────────────────────────────────────────────────────

TUTOR_SYSTEM_PROMPT = """You are an expert AI tutor in an adaptive learning system. You personalize your teaching to each student's level, learning style, and knowledge gaps.

Your tutoring principles:
1. Meet the student where they are — use vocabulary appropriate to their level
2. Use concrete examples before abstract concepts
3. Break complex ideas into digestible steps
4. Ask Socratic questions to guide discovery
5. Celebrate progress and normalize mistakes
6. Connect new concepts to things the student already knows
7. If a student is struggling, try a completely different explanation approach

When given retrieved educational context, use it as your primary reference. Always be encouraging, patient, and adaptive.

Student profile: {student_profile}
Current topic: {topic}
Retrieved context: {context}
"""


class AITutor:
    """
    RAG-powered AI tutor using Gemini 1.5 Flash.
    Supports: concept explanation, Q&A, step-by-step tutoring, example generation.
    """

    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model_name = "gemini-1.5-flash"
        self.retriever = RAGRetriever()
        
        # Generation configuration
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1500,
        }

    def _build_system_prompt(
        self,
        student_profile: Dict,
        topic: str,
        query: str,
    ) -> str:
        """Build context-aware system prompt with RAG."""
        # Retrieve relevant content
        retrieved = self.retriever.retrieve(query, topic_id=topic, top_k=3)
        context_text = "\n\n---\n\n".join([r["content"] for r in retrieved]) or "No specific content found."

        profile_summary = (
            f"Learning style: {student_profile.get('learning_style', 'unknown')}, "
            f"IRT ability: {student_profile.get('irt_ability', 0.0):.2f}, "
            f"Topic mastery: {student_profile.get('mastery_scores', {}).get(topic, 0.0):.2f}, "
            f"Engagement: {student_profile.get('engagement_score', 0.5):.2f}"
        )

        return TUTOR_SYSTEM_PROMPT.format(
            student_profile=profile_summary,
            topic=topic,
            context=context_text,
        )

    def chat(
        self,
        messages: List[Dict],
        student_profile: Dict,
        topic: str = "general",
        mode: str = "explain",  # explain / solve / quiz / example
    ) -> str:
        """
        Multi-turn tutoring with Gemini.
        """
        latest_query = messages[-1]["content"] if messages else ""
        system_instruction = self._build_system_prompt(student_profile, topic, latest_query)

        if mode == "solve":
            system_instruction += "\n\nIMPORTANT: Break down the solution step by step. Show your working clearly. Number each step."
        elif mode == "quiz":
            system_instruction += "\n\nIMPORTANT: Generate one focused practice question appropriate to the student's level. Include hints if needed."
        elif mode == "example":
            system_instruction += "\n\nIMPORTANT: Provide 2-3 concrete, memorable examples. Start simple and increase complexity."

        # Initialize model with system instruction
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_instruction,
            generation_config=self.generation_config,
        )

        # Convert history for Gemini
        # Gemini expects roles to be 'user' or 'model'
        history = []
        for msg in messages[:-1]:  # All but the latest
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        try:
            chat_session = model.start_chat(history=history)
            response = chat_session.send_message(latest_query)
            return response.text
        except Exception as e:
            logger.error(f"Gemini AI Tutor error: {e}")
            return self._fallback_response(latest_query, topic, mode)

    def _fallback_response(self, query: str, topic: str, mode: str) -> str:
        """Fallback response when API is unavailable."""
        retrieved = self.retriever.retrieve(query, topic_id=topic, top_k=2)
        if retrieved:
            context = retrieved[0]["content"]
            return f"[Demo mode — configure GOOGLE_API_KEY for full AI responses]\n\nHere's what I know about {topic}:\n{context.strip()}"
        return f"[Demo mode] I'd be happy to help you learn about {topic}! Please configure your GOOGLE_API_KEY in the .env file to enable the full AI tutor."

    def evaluate_answer(self, student_answer: str, correct_answer: str) -> Dict:
        """
        Evaluate a student's descriptive answer using LLM semantic evaluation.
        """
        eval_prompt = f"""You are grading a student's answer. Be fair but thorough.

Correct answer: {correct_answer}
Student's answer: {student_answer}

Provide:
1. Score (0.0 to 1.0) — how correct/complete is the answer?
2. Brief feedback (1-2 sentences) on what was right and what to improve.

Respond in JSON format only:
{{"score": 0.8, "feedback": "...", "key_concepts_missed": []}}"""

        try:
            model = genai.GenerativeModel(model_name=self.model_name)
            response = model.generate_content(
                eval_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text)
            return {
                "score": float(result.get("score", 0.5)),
                "feedback": result.get("feedback", ""),
                "key_concepts_missed": result.get("key_concepts_missed", []),
            }
        except Exception as e:
            logger.warning(f"Evaluation failed: {e}")
            # Simple keyword matching fallback
            correct_words = set(correct_answer.lower().split())
            student_words = set(student_answer.lower().split())
            overlap = len(correct_words & student_words) / max(len(correct_words), 1)
            return {
                "score": min(overlap * 1.5, 1.0),
                "feedback": "Answer evaluated using keyword matching (API error).",
                "key_concepts_missed": [],
            }

    def generate_question(
        self,
        topic_id: str,
        difficulty: float = 0.5,
        q_type: str = "mcq",
        student_profile: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate an AI assessment question for a topic.
        """
        difficulty_label = "easy" if difficulty < 0.4 else ("hard" if difficulty > 0.7 else "medium")

        prompt = f"""Generate a {difficulty_label} {q_type} question for topic: {topic_id}.

Requirements:
- Difficulty: {difficulty_label} (difficulty score: {difficulty:.2f})
- Type: {q_type}
- If MCQ: provide 4 options (A/B/C/D) and indicate the correct one
- If coding: provide a clear problem statement with example input/output
- If conceptual: ask for explanation or comparison

Respond in JSON ONLY:
{{
  "question": "...",
  "type": "{q_type}",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "correct_answer": "...",
  "explanation": "...",
  "difficulty": {difficulty:.2f}
}}"""

        try:
            model = genai.GenerativeModel(model_name=self.model_name)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            logger.warning(f"Question generation fallback: {e}")
            return {
                "question": f"Explain the key concept of {topic_id} in your own words.",
                "type": "descriptive",
                "options": None,
                "correct_answer": f"A clear explanation of {topic_id} covering its definition, applications, and key properties.",
                "explanation": "Open-ended question for conceptual understanding.",
                "difficulty": difficulty,
            }


# Singleton
ai_tutor = AITutor()
