import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import ensure_qdrant_collection
from app.ai.ai_tutor import RAGRetriever

def seed():
    print("Ensuring Qdrant collections...")
    ensure_qdrant_collection()
    print("Seeding educational content...")
    retriever = RAGRetriever()
    retriever.seed_content()
    print("Content seeded. Testing retrieval...")
    results = retriever.retrieve("how to find derivative of a function", top_k=2)
    for r in results:
        print(f"  Retrieved: topic={r['topic_id']}, score={r['score']:.3f}")
    print("Done!")

if __name__ == "__main__":
    seed()
