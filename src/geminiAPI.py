"""
Gemini API Client
Encapsulates logic for interacting with Google Gemini LLM.
"""

import os
import time
import google.generativeai as genai

class GeminiClient:
    def __init__(self, api_key: str = None, model_name: str = 'gemini-2.0-flash-exp'):
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("No Gemini API key found. Please set GOOGLE_API_KEY environment variable.")

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)
            print(f"✓ Gemini initialized (Model: {model_name})")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Gemini: {e}")

    def generate_content(self, prompt: str, max_retries: int = 5) -> str:
        """Call Gemini with retry logic for rate limits"""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                if "429" in str(e) or "ResourceExhausted" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"    ⏳ Rate limit hit. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                print(f"    ⚠ Gemini call failed: {e}")
                # Wait a bit before retry even for other errors
                time.sleep(2)
        return None
