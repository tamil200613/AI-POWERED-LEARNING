import requests
import json

# 1. Register a user
r = requests.post("http://127.0.0.1:8000/auth/register", json={
    "email": "test_assessment@test.com",
    "username": "test_assessment",
    "password": "password123!"
})
token = r.json().get("access_token")

# 2. Start test
r2 = requests.post("http://127.0.0.1:8000/assessment/adaptive/start", 
    json={"topic_id": "math_derivatives", "max_items": 10},
    headers={"Authorization": f"Bearer {token}"}
)
print("Start Test Status:", r2.status_code)
print("Start Test Response:", r2.text)
