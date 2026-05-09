import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from neo4j import AsyncGraphDatabase
from app.config import settings
from app.ai.knowledge_graph import knowledge_graph

async def seed():
    driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
    async with driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
        await knowledge_graph.seed_neo4j(session)
        r1 = await session.run("MATCH (t:Topic) RETURN count(t) as n")
        rec = await r1.single()
        print(f"Topics seeded: {rec['n']}")
    await driver.close()
    print("Neo4j knowledge graph seeded successfully")

if __name__ == "__main__":
    asyncio.run(seed())
