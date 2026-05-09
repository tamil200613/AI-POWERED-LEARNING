import asyncio
from app.database import get_db
from app.models.user import User
from app.routers.assessment import start_adaptive_test, StartTestRequest
from sqlalchemy import select

async def main():
    async for db in get_db():
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        req = StartTestRequest(topic_id="math_derivatives")
        try:
            res = await start_adaptive_test(req, user)
            print("SUCCESS:", res)
        except Exception as e:
            print("ERROR:", str(e))
        break

asyncio.run(main())
