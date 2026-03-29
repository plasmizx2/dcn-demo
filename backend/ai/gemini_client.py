"""
Gemini API helper — one simple function to generate text.
"""

import os
import hashlib
import requests
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-2.5-flash"


def generate_text(prompt: str) -> str:
    """Send a prompt to Gemini (with optional external caching) and return response."""
    # Hash prompt for caching
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache_base_url = os.getenv("DCN_CACHE_URL")
    
    # 1. Try Cache
    if cache_base_url:
        try:
            lookup_res = requests.post(
                f"{cache_base_url}/tasks/cache/lookup",
                json={"prompt_hash": prompt_hash},
                timeout=2
            )
            if lookup_res.status_code == 200:
                data = lookup_res.json()
                if data.get("hit"):
                    print(f"[cache hit] {prompt_hash[:8]}")
                    return data["response_text"]
        except Exception as e:
            print(f"[cache lookup disabled or error: {e}]")

    # 2. Call Gemini
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )
    result = response.text

    # 3. Store in Cache
    if cache_base_url:
        try:
            requests.post(
                f"{cache_base_url}/tasks/cache/store",
                json={"prompt_hash": prompt_hash, "response_text": result},
                timeout=2
            )
        except Exception:
            pass

    return result
