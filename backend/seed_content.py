"""
scripts/seed_content.py — Seed Qdrant with educational content embeddings
Run: python scripts/seed_content.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.ai_tutor import RAGRetriever
from app.database import ensure_qdrant_collection


def seed():
    print("Ensuring Qdrant collections exist...")
    ensure_qdrant_collection()

    print("Seeding educational content into Qdrant...")
    retriever = RAGRetriever()
    retriever.seed_content()
    print("✅ Educational content seeded into Qdrant (content_embeddings collection)")

    # Test retrieval
    print("\nTesting RAG retrieval...")
    results = retriever.retrieve("how to find the derivative of a function", top_k=2)
    for r in results:
        print(f"  ✓ Retrieved: topic={r['topic_id']}, score={r['score']:.3f}")


if __name__ == "__main__":
    seed()
