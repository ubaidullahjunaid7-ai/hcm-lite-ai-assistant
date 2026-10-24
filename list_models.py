import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
c = genai.Client(api_key=os.getenv("AI_API_KEY"))
for m in c.models.list():
    if "gemini" in m.name and "flash" in m.name:
        print(m.name)