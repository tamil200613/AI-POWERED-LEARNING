import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to sys.path to allow imports from app
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from app.config import settings
    from app.ai.ai_tutor import ai_tutor
    import google.generativeai as genai
except ImportError as e:
    print(f"ERROR: Could not import required modules. {e}")
    sys.exit(1)

def test_gemini():
    print("--- Gemini Integration Diagnostic ---")
    
    # Check API key
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        print("❌ GOOGLE_API_KEY is not set in your .env file.")
        return
    
    print(f"[OK] GOOGLE_API_KEY found: {api_key[:5]}...{api_key[-5:]}")
    
    # Test genai configuration
    try:
        genai.configure(api_key=api_key)
        print("[OK] google.generativeai configured.")
    except Exception as e:
        print(f"[ERROR] Failed to configure google.generativeai: {e}")
        return

    # Test direct model call
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        response = model.generate_content("Hello, this is a diagnostic test. Reply with 'ACK' if you receive this.")
        print(f"[OK] Direct Gemini call successful. Response: {response.text.strip()}")
    except Exception as e:
        print(f"[ERROR] Gemini direct call failed: {e}")
        return

    # Test AITutor class
    print("\n--- Testing AITutor Class ---")
    try:
        messages = [{"role": "user", "content": "Explain derivatives in one sentence."}]
        profile = {
            "learning_style": "visual",
            "irt_ability": 0.0,
            "mastery_scores": {},
            "engagement_score": 0.5
        }
        response = ai_tutor.chat(messages=messages, student_profile=profile, topic="math_derivatives")
        print(f"[OK] AITutor.chat successful. Response preview: {response[:100]}...")
    except Exception as e:
        print(f"[ERROR] AITutor.chat failed: {e}")
        return

    print("\nALL TESTS PASSED! Your Gemini integration is correctly configured.")

if __name__ == "__main__":
    test_gemini()
