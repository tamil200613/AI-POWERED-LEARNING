"""
scripts/seed_knowledge_graph.py — Seed Neo4j with knowledge graph
Run: python scripts/seed_knowledge_graph.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import AsyncGraphDatabase
from app.config import settings
from app.ai.knowledge_graph import knowledge_graph


async def seed():
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    async with driver.session() as session:
        # Clear existing
        await session.run("MATCH (n) DETACH DELETE n")
        print("Cleared existing graph...")

        # Seed
        await knowledge_graph.seed_neo4j(session)
        print("✅ Neo4j knowledge graph seeded")

        # Verify
        result = await session.run("MATCH (t:Topic) RETURN count(t) as n")
        record = await result.single()
        print(f"   Topics in graph: {record['n']}")

        result = await session.run("MATCH ()-[r:PREREQUISITE]->() RETURN count(r) as n")
        record = await result.single()
        print(f"   Prerequisite edges: {record['n']}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(seed())
