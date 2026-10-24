import os, requests
from dotenv import load_dotenv
load_dotenv()

g = os.getenv("GEMINI_API_KEY")
q = os.getenv("GROQ_API_KEY")
print("Gemini key mili:", bool(g))
print("Groq key mili:", bool(q))

# Groq test
r = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {q}"},
    json={"model": "llama-3.1-8b-instant",
          "messages": [{"role": "user", "content": "Say hi in 3 words"}]},
)
print("Groq:", r.status_code, r.text[:150])

# Gemini test
r = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={g}",
    json={"contents": [{"parts": [{"text": "Say hi in 3 words"}]}]},
)
print("Gemini:", r.status_code, r.text[:150])