import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print(f"API Key: {api_key[:10]}...")

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Hi")
    print(f"Response: {response.text}")
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
