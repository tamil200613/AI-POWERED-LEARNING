import json
import logging
import os
from typing import List, Dict, Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

EDUCATIONAL_CONTENT = [
    {"id": "c1", "topic_id": "math_derivatives", "content": "Derivatives measure rate of change. Power rule: d/dx[x^n] = n*x^(n-1). Product rule: (fg)' = f'g + fg'. Chain rule: d/dx[f(g(x))] = f'(g(x)) * g'(x). Used for optimization, finding maxima/minima, and velocity calculations.", "difficulty": 4},
    {"id": "c2", "topic_id": "cs_oop", "content": "Object-Oriented Programming (OOP) has 4 pillars: 1) Encapsulation - bundle data and methods, hide internal state. 2) Inheritance - child classes inherit from parent. 3) Polymorphism - same interface, different implementations. 4) Abstraction - hide complexity. Example: class Dog(Animal): def speak(self): return 'Woof!'", "difficulty": 3},
    {"id": "c3", "topic_id": "phys_kinematics", "content": "Kinematics equations (constant acceleration): v = u + at, s = ut + (1/2)at^2, v^2 = u^2 + 2as. Projectile motion: horizontal (constant velocity) + vertical (gravity = -9.8 m/s^2). Range = v^2*sin(2theta)/g.", "difficulty": 2},
    {"id": "c4", "topic_id": "math_statistics", "content": "Statistics: Mean = sum/n, Median = middle value, Mode = most frequent. Standard deviation measures spread. Probability: P(A) = favorable/total. Bayes theorem: P(A|B) = P(B|A)*P(A)/P(B). Normal distribution: 68-95-99.7 rule.", "difficulty": 3},
    {"id": "c5", "topic_id": "cs_algorithms", "content": "Algorithm complexity Big-O: O(1) < O(log n) < O(n) < O(n log n) < O(n^2). Sorting: Bubble O(n^2), Merge Sort O(n log n) stable, Quick Sort O(n log n) average. Graph: BFS/DFS O(V+E), Dijkstra O((V+E)log V).", "difficulty": 4},
    {"id": "c6", "topic_id": "cs_data_structures", "content": "Data structures: Array O(1) access, O(n) search. Linked List O(n) access, O(1) insert. Stack/Queue LIFO/FIFO. Binary Search Tree O(log n) average. Hash Table O(1) average. Heap for priority queue.", "difficulty": 4},
    {"id": "c7", "topic_id": "math_algebra_basics", "content": "Algebra basics: Variables represent unknown values. Linear equations: ax + b = 0, solution x = -b/a. Simultaneous equations solved by substitution or elimination. Inequalities: flip sign when multiplying by negative.", "difficulty": 2},
    {"id": "c8", "topic_id": "math_statistics", "content": "Probability distributions: Binomial P(X=k) = C(n,k) * p^k * (1-p)^(n-k). Poisson for rare events. Normal distribution symmetric bell curve. Central Limit Theorem: sample means are normally distributed.", "difficulty": 3},
]

SYSTEM_PROMPT = """You are an expert AI tutor in an adaptive learning system. You personalize teaching based on the student's level.

Core principles:
- Meet the student where they are - match their vocabulary and level
- Use concrete examples BEFORE abstract concepts  
- Break complex ideas into digestible steps
- Ask Socratic questions to guide discovery
- Be encouraging and patient

Student Profile: {profile}
Current Topic: {topic}

Reference Material:
{context}

Remember: You are a helpful tutor. Give clear, educational responses."""


class RAGRetriever:
    """Retrieves relevant educational content."""
    
    def retrieve(self, query: str, topic_id: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """Simple keyword-based retrieval as fallback."""
        if topic_id:
            results = [c for c in EDUCATIONAL_CONTENT if c["topic_id"] == topic_id]
            if results:
                return [{"content": r["content"], "topic_id": r["topic_id"], "score": 1.0} for r in results[:top_k]]
        
        # Keyword search
        query_lower = query.lower()
        scored = []
        for c in EDUCATIONAL_CONTENT:
            score = sum(1 for word in query_lower.split() if word in c["content"].lower())
            if score > 0:
                scored.append({"content": c["content"], "topic_id": c["topic_id"], "score": score})
        
        scored.sort(key=lambda x: -x["score"])
        return scored[:top_k] if scored else [{"content": EDUCATIONAL_CONTENT[0]["content"], "topic_id": "general", "score": 0.1}]

    def seed_content(self):
        """Seed content into Qdrant if available."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct
            from sentence_transformers import SentenceTransformer
            from app.config import settings
            
            encoder = SentenceTransformer("all-MiniLM-L6-v2")
            client = QdrantClient(url=settings.QDRANT_URL, timeout=10)
            
            points = []
            for i, c in enumerate(EDUCATIONAL_CONTENT):
                vec = encoder.encode(c["content"], normalize_embeddings=True).tolist()
                points.append(PointStruct(
                    id=i,
                    vector=vec,
                    payload={"content_id": c["id"], "topic_id": c["topic_id"], "content": c["content"]}
                ))
            client.upsert(collection_name="content_embeddings", points=points)
            print(f"Seeded {len(points)} content items into Qdrant")
        except Exception as e:
            print(f"Qdrant seeding skipped (using in-memory fallback): {e}")


class AITutor:
    """RAG-powered AI tutor using Google Gemini 1.5 Flash."""
    
    def __init__(self):
        self.retriever = RAGRetriever()
        self._gemini_configured = False

    def _configure_gemini(self):
        """Configure Google Generative AI client."""
        if not self._gemini_configured:
            try:
                from app.config import settings
                if not settings.GOOGLE_API_KEY or settings.GOOGLE_API_KEY == "your-google-api-key-here":
                    return False
                genai.configure(api_key=settings.GOOGLE_API_KEY)
                self._gemini_configured = True
                return True
            except Exception as e:
                logger.error(f"Failed to configure Gemini: {e}")
                return False
        return True

    def chat(self, messages: List[Dict], student_profile: Dict, topic: str = "general", mode: str = "explain") -> str:
        """Multi-turn tutoring conversation."""
        query = messages[-1]["content"] if messages else ""
        
        # Retrieve relevant content from internal RAG
        retrieved = self.retriever.retrieve(query, topic_id=topic, top_k=3)
        context = "\n\n---\n\n".join([r["content"] for r in retrieved])
        
        profile_str = (
            f"Learning style: {student_profile.get('learning_style', 'visual')}, "
            f"IRT ability: {student_profile.get('irt_ability', 0.0):.2f}, "
            f"Topic mastery: {student_profile.get('mastery_scores', {}).get(topic, 0.0):.0%}"
        )
        
        system = SYSTEM_PROMPT.format(profile=profile_str, topic=topic, context=context or "No specific content found.")
        
        if mode == "solve":
            system += "\n\nIMPORTANT: Break down the solution step by step. Number each step clearly."
        elif mode == "quiz":
            system += "\n\nIMPORTANT: Generate ONE focused practice question at the student's level. Include the answer at the end."
        elif mode == "example":
            system += "\n\nIMPORTANT: Provide 2-3 concrete, memorable examples. Start simple, increase complexity."
        elif mode == "search":
            system += "\n\nIMPORTANT: You have AI Search (Google Search) enabled. If internal context is insufficient, use Google Search to find accurate, up-to-date educational information."

        if not self._configure_gemini():
            # Demo mode with educational content
            content_preview = retrieved[0]["content"] if retrieved else "No content available."
            current_api = "GOOGLE_API_KEY"
            return (
                f"[Demo Mode - API key not configured]\n\n"
                f"**Topic: {topic}**\n\n"
                f"Here's what I know about this topic:\n\n"
                f"{content_preview}\n\n"
                f"---\n"
                f"*To enable full AI tutoring: add your {current_api} to backend/.env and restart the server.*\n"
                f"*Get a free key at: https://aistudio.google.com/app/apikey*"
            )
        
        try:
            # Prepare tools for search mode
            tools = []
            if mode == "search":
                tools.append({"google_search_retrieval": {}})

            model = genai.GenerativeModel(
                model_name="gemini-flash-latest",
                system_instruction=system,
                tools=tools if tools else None
            )
            
            # Convert messages to Gemini format
            gemini_history = []
            for m in messages[:-1]:
                role = "user" if m["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [m["content"]]})
            
            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(messages[-1]["content"])
            
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            content_preview = retrieved[0]["content"] if retrieved else ""
            return (
                f"I encountered an AI error. Here's the educational content for **{topic}**:\n\n"
                f"{content_preview}\n\n"
                f"*Error details: {str(e)[:100]}*"
            )

    def evaluate_answer(self, student_answer: str, correct_answer: str) -> Dict:
        """Evaluate a student answer."""
        if self._configure_gemini():
            try:
                model = genai.GenerativeModel("gemini-flash-latest")
                prompt = (
                    f"Grade this student answer fairly.\n\n"
                    f"Correct answer: {correct_answer}\n"
                    f"Student answer: {student_answer}\n\n"
                    f"Respond ONLY with valid JSON (no markdown):\n"
                    f'{{"score": 0.8, "feedback": "Good attempt...", "key_concepts_missed": []}}'
                )
                response = model.generate_content(prompt)
                text = response.text.strip()
                # Remove markdown code blocks if present
                text = text.replace("```json", "").replace("```", "").strip()
                result = json.loads(text)
                return {
                    "score": float(result.get("score", 0.5)),
                    "feedback": result.get("feedback", "Answer evaluated."),
                    "key_concepts_missed": result.get("key_concepts_missed", []),
                }
            except Exception as e:
                logger.warning(f"LLM evaluation failed, using keyword matching: {e}")
        
        # Keyword-based fallback
        correct_words = set(correct_answer.lower().split())
        student_words = set(student_answer.lower().split())
        if len(correct_words) == 0:
            score = 0.5
        else:
            overlap = len(correct_words & student_words) / len(correct_words)
            score = min(overlap * 1.5, 1.0)
        
        return {
            "score": round(score, 3),
            "feedback": f"Your answer covered {score:.0%} of the key concepts." if score > 0 else "Try to include more relevant keywords.",
            "key_concepts_missed": [],
        }

    def generate_question(self, topic_id: str, difficulty: float = 0.5, q_type: str = "mcq", student_profile: Optional[Dict] = None) -> Dict:
        """Generate an AI assessment question."""
        difficulty_label = "easy" if difficulty < 0.4 else ("hard" if difficulty > 0.7 else "medium")
        
        if self._configure_gemini():
            try:
                model = genai.GenerativeModel("gemini-flash-latest")
                prompt = (
                    f"Generate a {difficulty_label} {q_type} question for the topic: {topic_id}.\n\n"
                    f"Requirements:\n"
                    f"- Difficulty: {difficulty_label} (score: {difficulty:.2f})\n"
                    f"- Type: {q_type}\n"
                    f"- If MCQ: provide exactly 4 options labeled A, B, C, D\n"
                    f"- If coding: clear problem statement with example input/output\n"
                    f"- If descriptive: ask for explanation or comparison\n\n"
                    f"Respond ONLY with valid JSON (no markdown):\n"
                    f'{{"question": "...", "type": "{q_type}", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_answer": "...", "explanation": "...", "difficulty": {difficulty:.2f}}}\n'
                    f'Note: set options to null if not MCQ.'
                )
                response = model.generate_content(prompt)
                text = response.text.strip()
                text = text.replace("```json", "").replace("```", "").strip()
                return json.loads(text)
            except Exception as e:
                logger.warning(f"Question generation failed: {e}")
        
        # Fallback questions by topic
        fallback_questions = {
            "math_derivatives": {
                "question": "What is the derivative of f(x) = 3xÂ² + 2x + 1?",
                "type": "mcq",
                "options": ["A. 6x + 2", "B. 3x + 2", "C. 6xÂ² + 2", "D. 3xÂ²"],
                "correct_answer": "A. 6x + 2",
                "explanation": "Using the power rule: d/dx[3xÂ²] = 6x, d/dx[2x] = 2, d/dx[1] = 0. So f'(x) = 6x + 2.",
                "difficulty": difficulty,
            },
            "cs_oop": {
                "question": "Which OOP principle allows a child class to use methods from a parent class?",
                "type": "mcq",
                "options": ["A. Encapsulation", "B. Inheritance", "C. Polymorphism", "D. Abstraction"],
                "correct_answer": "B. Inheritance",
                "explanation": "Inheritance allows a child class to inherit properties and methods from a parent class.",
                "difficulty": difficulty,
            },
            "phys_kinematics": {
                "question": "A car starts from rest and accelerates at 4 m/sÂ². What is its velocity after 5 seconds?",
                "type": "mcq",
                "options": ["A. 10 m/s", "B. 15 m/s", "C. 20 m/s", "D. 25 m/s"],
                "correct_answer": "C. 20 m/s",
                "explanation": "Using v = u + at: v = 0 + (4)(5) = 20 m/s.",
                "difficulty": difficulty,
            },
            "math_statistics": {
                "question": "What is the mean of the dataset: [2, 4, 6, 8, 10]?",
                "type": "mcq",
                "options": ["A. 4", "B. 5", "C. 6", "D. 7"],
                "correct_answer": "C. 6",
                "explanation": "Mean = (2+4+6+8+10)/5 = 30/5 = 6.",
                "difficulty": difficulty,
            },
            "cs_algorithms": {
                "question": "What is the time complexity of binary search?",
                "type": "mcq",
                "options": ["A. O(n)", "B. O(nÂ²)", "C. O(log n)", "D. O(n log n)"],
                "correct_answer": "C. O(log n)",
                "explanation": "Binary search halves the search space each iteration, giving O(log n) complexity.",
                "difficulty": difficulty,
            },
            "cs_data_structures": {
                "question": "Which data structure uses LIFO (Last In, First Out) order?",
                "type": "mcq",
                "options": ["A. Queue", "B. Stack", "C. Array", "D. Linked List"],
                "correct_answer": "B. Stack",
                "explanation": "A Stack uses LIFO - the last element pushed is the first one popped.",
                "difficulty": difficulty,
            },
        }
        
        return fallback_questions.get(topic_id, {
            "question": f"Explain the most important concept you know about {topic_id.replace('_', ' ')}.",
            "type": "descriptive",
            "options": None,
            "correct_answer": f"A clear explanation of the core concepts of {topic_id.replace('_', ' ')} including its definition, key properties, and practical applications.",
            "explanation": "Open-ended conceptual question.",
            "difficulty": difficulty,
        })


ai_tutor = AITutor()